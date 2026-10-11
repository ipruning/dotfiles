"""Regenerate the generated/ shell state owned by this repository."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
from dataclasses import replace
from pathlib import Path

from .generate_commands import (
    atomic_install,
    checkout_revision,
    command_failure_reason,
    download_url,
    emit_command_output,
    guarded_activation,
    inspect_plugin,
    read_revision,
    run_command,
    timeout_reason,
)
from .generate_models import (
    AtomicWriter,
    Downloader,
    GenerateAction,
    GenerateReport,
    GenerateResult,
    GenerateSpec,
    ShellInitSpec,
    StepCallback,
)
from .generate_render import (
    announce_generate_step,
    generate_document,
    generate_next_commands,
    render_generate,
)
from .generate_specs import (
    COMPLETION_SPECS,
    FUNCTION_SPECS,
    OWNED_GENERATED_DIRECTORIES,
    PLUGIN_SPECS,
    WASM_SPECS,
)
from .host_policy import HostPolicyError, mutation_allowed, require_mutation_allowed
from .mise import canonical_mise_executable, canonical_mise_path
from .models import ExecutableFinder, Status
from .render import emit_error

__all__ = [
    "COMPLETION_SPECS",
    "FUNCTION_SPECS",
    "OWNED_GENERATED_DIRECTORIES",
    "PLUGIN_SPECS",
    "WASM_SPECS",
    "AtomicWriter",
    "Downloader",
    "GenerateAction",
    "GenerateReport",
    "GenerateResult",
    "GenerateSpec",
    "ShellInitSpec",
    "StepCallback",
    "execute_generate",
    "file_sha256",
    "generate_next_commands",
    "plan_generate",
    "render_generate",
    "shim_aware_finder",
]


def _symlinked_generated_directory(generated_root: Path) -> Path | None:
    for directory in (
        generated_root,
        *(generated_root / name for name in OWNED_GENERATED_DIRECTORIES),
    ):
        if directory.is_symlink():
            return directory
    return None


def _symlinked_directory_reason(directory: Path) -> str:
    return (
        f"generated directory is a symlink ({os.readlink(directory)}); "
        "remove it before refreshing"
    )


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _mise_shims_dir() -> Path:
    data_dir = os.environ.get("MISE_DATA_DIR")
    base = Path(data_dir) if data_dir else Path.home() / ".local/share/mise"
    return base / "shims"


def shim_aware_finder(executable_finder: ExecutableFinder) -> ExecutableFinder:
    """Resolve tools from PATH while rejecting stale mise shims."""
    shims_dir = _mise_shims_dir()
    shim_health: dict[str, bool] = {}

    def shim_is_healthy(tool: str) -> bool:
        cached = shim_health.get(tool)
        if cached is not None:
            return cached
        mise_executable = executable_finder("mise")
        healthy = False
        if mise_executable:
            try:
                completed = subprocess.run(
                    (mise_executable, "which", tool),
                    check=False,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    timeout=30,
                )
                healthy = completed.returncode == 0
            except OSError, subprocess.TimeoutExpired:
                healthy = False
        shim_health[tool] = healthy
        return healthy

    def find(tool: str) -> str | None:
        found = executable_finder(tool)
        if found and Path(found).parent == shims_dir and not shim_is_healthy(tool):
            found = None
            if executable_finder is shutil.which:
                search_path = os.pathsep.join(
                    directory
                    for directory in os.get_exec_path()
                    if Path(directory).absolute() != shims_dir.absolute()
                )
                found = shutil.which(tool, path=search_path)
        if found:
            return found
        return None

    return find


def _generator_result(
    spec: GenerateSpec,
    *,
    executable_finder: ExecutableFinder,
) -> GenerateResult:
    assert spec.tool is not None
    assert spec.target is not None
    if executable := executable_finder(spec.tool):
        spec = replace(spec, command=(executable, *spec.command[1:]))
        return GenerateResult(spec, Status.PLANNED, GenerateAction.GENERATE)
    if spec.target.exists() or spec.target.is_symlink():
        return GenerateResult(
            spec,
            Status.PLANNED,
            GenerateAction.REMOVE,
            f"{spec.tool} is not available; remove stale owned output",
        )
    return GenerateResult(
        spec,
        Status.SKIPPED,
        GenerateAction.GENERATE,
        f"{spec.tool} is not available on PATH",
    )


def plan_generate(
    repo_root: Path,
    home: Path,
    *,
    executable_finder: ExecutableFinder = shutil.which,
    network: bool = True,
) -> GenerateReport:
    """Return the exact generate plan without changing files."""
    generated_root = repo_root / "generated"
    if symlinked_directory := _symlinked_generated_directory(generated_root):
        relative_name = (
            symlinked_directory.relative_to(repo_root).as_posix().replace("/", ".")
        )
        spec = GenerateSpec(
            name=f"directory.{relative_name}",
            tool=None,
            target=symlinked_directory,
        )
        return GenerateReport(
            apply=False,
            results=(
                GenerateResult(
                    spec,
                    Status.FAILED,
                    GenerateAction.VALIDATE,
                    _symlinked_directory_reason(symlinked_directory),
                ),
            ),
            generated_root=generated_root,
            network=network,
        )
    executable_finder = shim_aware_finder(executable_finder)
    functions_dir = generated_root / "functions"
    completions_dir = generated_root / "completions"
    plugins_dir = generated_root / "plugins"
    results = []
    for function_spec in FUNCTION_SPECS:
        tool = function_spec.tool
        command = function_spec.command
        generator_finder = executable_finder
        if tool == "mise":
            mise_executable = canonical_mise_executable(home)
            command = (str(canonical_mise_path(home)), *command[1:])
            generator_finder = {tool: mise_executable}.get
        spec = GenerateSpec(
            name=f"function.{function_spec.name}",
            tool=tool,
            target=functions_dir / function_spec.filename,
            command=command,
        )
        results.append(_generator_result(spec, executable_finder=generator_finder))
    for name, tool, command, filename, environment in COMPLETION_SPECS:
        spec = GenerateSpec(
            name=f"completion.{name}",
            tool=tool,
            target=completions_dir / filename,
            command=command,
            environment=environment,
        )
        if name == "llm" and not network:
            results.append(
                GenerateResult(
                    spec,
                    Status.SKIPPED,
                    GenerateAction.GENERATE,
                    "LLM completion needs package resolution; run generate without --offline",
                )
            )
            continue
        results.append(_generator_result(spec, executable_finder=executable_finder))
    git_available = executable_finder("git") is not None
    for name, source, revision, entrypoint in PLUGIN_SPECS:
        target = plugins_dir / name
        git_directory = target / ".git"
        # A symlink here would point outside repository-owned generated state;
        # `(target / ".git")` follows it, so an UPDATE would `git pull` inside
        # that external checkout. Never treat a symlink as an updatable clone.
        is_symlink = target.is_symlink()
        git_directory_is_symlink = git_directory.is_symlink()
        action = (
            GenerateAction.UPDATE
            if not is_symlink
            and not git_directory_is_symlink
            and git_directory.is_dir()
            else GenerateAction.CLONE
        )
        spec = GenerateSpec(
            name=f"plugin.{name}",
            tool="git",
            target=target,
            source=source,
            revision=revision,
            entrypoint=entrypoint,
            command=(
                (
                    "git",
                    "-C",
                    str(target),
                    "fetch",
                    "--depth=1",
                    "origin",
                    revision,
                )
                if action is GenerateAction.UPDATE
                else (
                    "git",
                    "clone",
                    "--filter=blob:none",
                    "--no-checkout",
                    source,
                    str(target),
                )
            ),
        )
        if is_symlink:
            results.append(
                GenerateResult(
                    spec,
                    Status.FAILED,
                    action,
                    f"plugin target is a symlink ({os.readlink(target)}); "
                    "remove it before refreshing",
                ),
            )
        elif git_directory_is_symlink:
            results.append(
                GenerateResult(
                    spec,
                    Status.FAILED,
                    action,
                    f"plugin Git metadata is a symlink "
                    f"({os.readlink(git_directory)}); remove it before refreshing",
                ),
            )
        elif action is GenerateAction.UPDATE and git_available:
            try:
                current = inspect_plugin(spec, home)
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                results.append(GenerateResult(spec, Status.FAILED, action, str(error)))
            else:
                results.append(
                    GenerateResult(
                        spec,
                        Status.UNCHANGED,
                        action,
                        "pinned revision and tracked files are current",
                    )
                    if current
                    else GenerateResult(spec, Status.PLANNED, action)
                    if network
                    else GenerateResult(
                        spec,
                        Status.SKIPPED,
                        action,
                        "network refresh is disabled",
                    )
                )
        elif not network:
            results.append(
                GenerateResult(
                    spec,
                    Status.SKIPPED,
                    action,
                    "network refresh is disabled",
                ),
            )
        elif target.exists() and action is GenerateAction.CLONE:
            results.append(
                GenerateResult(
                    spec,
                    Status.FAILED,
                    action,
                    "target exists but is not a Git checkout",
                ),
            )
        elif git_available:
            results.append(GenerateResult(spec, Status.PLANNED, action))
        else:
            results.append(
                GenerateResult(
                    spec,
                    Status.SKIPPED,
                    action,
                    "git is not available on PATH",
                ),
            )
    for name, source, sha256 in WASM_SPECS:
        target = plugins_dir / f"{name}.wasm"
        spec = GenerateSpec(
            name=f"wasm.{name}",
            tool=None,
            target=target,
            source=source,
            sha256=sha256,
            timeout_seconds=60,
        )
        if file_sha256(target) == sha256:
            results.append(
                GenerateResult(
                    spec,
                    Status.UNCHANGED,
                    GenerateAction.DOWNLOAD,
                    "checksum is current",
                ),
            )
        elif network:
            results.append(
                GenerateResult(spec, Status.PLANNED, GenerateAction.DOWNLOAD),
            )
        else:
            results.append(
                GenerateResult(
                    spec,
                    Status.SKIPPED,
                    GenerateAction.DOWNLOAD,
                    "network refresh is disabled",
                ),
            )
    bat_spec = GenerateSpec(
        name="bat.cache",
        tool="bat",
        command=("bat", "cache", "--build"),
    )
    results.append(
        GenerateResult(bat_spec, Status.PLANNED, GenerateAction.RUN)
        if executable_finder("bat")
        else GenerateResult(
            bat_spec,
            Status.SKIPPED,
            GenerateAction.RUN,
            "bat is not available on PATH",
        ),
    )
    compdumps = tuple(sorted(home.glob(".zcompdump*")))
    compdump_spec = GenerateSpec(
        name="zsh.compdump",
        tool=None,
        target=home / ".zcompdump*",
    )
    results.append(
        GenerateResult(
            compdump_spec,
            Status.PLANNED,
            GenerateAction.REMOVE,
            "invalidate only if completion outputs change",
        )
        if compdumps
        else GenerateResult(
            compdump_spec,
            Status.SKIPPED,
            GenerateAction.REMOVE,
            "no zcompdump files exist",
        ),
    )
    return GenerateReport(
        apply=False,
        results=tuple(results),
        generated_root=generated_root,
        network=network,
    )


def execute_generate(
    plan: GenerateReport,
    home: Path,
    *,
    downloader: Downloader = download_url,
    on_start: StepCallback | None = None,
    capture_output: bool = True,
) -> GenerateReport:
    """Execute a previously rendered generate plan."""
    require_mutation_allowed(home)
    results = []
    for planned in plan.results:
        spec = planned.spec
        if planned.status is not Status.PLANNED:
            results.append(planned)
            continue
        if spec.name == "zsh.compdump" and not any(
            result.status is Status.SUCCEEDED
            and result.spec.name.startswith("completion.")
            for result in results
        ):
            results.append(
                GenerateResult(
                    spec,
                    Status.UNCHANGED,
                    planned.action,
                    "completion outputs are unchanged",
                )
            )
            continue
        if on_start:
            on_start(spec, planned.action)
        exit_code: int | None = None
        try:
            if plan.generated_root is not None and (
                symlinked_directory := _symlinked_generated_directory(
                    plan.generated_root
                )
            ):
                raise RuntimeError(_symlinked_directory_reason(symlinked_directory))
            command_directory = (
                spec.target if planned.action is GenerateAction.UPDATE else None
            )
            if command_directory is not None and command_directory.is_symlink():
                raise RuntimeError(
                    "generated command directory is a symlink "
                    f"({os.readlink(command_directory)}); refusing to execute outside "
                    "generated state",
                )
            if command_directory is not None:
                command_git_directory = command_directory / ".git"
                if command_git_directory.is_symlink():
                    raise RuntimeError(
                        "generated command Git metadata is a symlink "
                        f"({os.readlink(command_git_directory)}); refusing to execute "
                        "outside generated state",
                    )
                if not command_git_directory.is_dir():
                    raise RuntimeError(
                        "generated command Git metadata is not a directory; refusing "
                        "to execute outside generated state",
                    )
            if planned.action is GenerateAction.GENERATE:
                completed = run_command(spec, home, capture_output=True)
                exit_code = completed.returncode
                emit_command_output(spec, completed.stderr)
                if completed.returncode != 0:
                    raise RuntimeError(command_failure_reason(completed))
                if not completed.stdout:
                    raise RuntimeError("generator produced empty output")
                assert spec.target is not None
                output = guarded_activation(spec, completed.stdout)
                if (
                    spec.target.is_file()
                    and not spec.target.is_symlink()
                    and spec.target.read_bytes() == output.encode()
                ):
                    results.append(
                        GenerateResult(
                            spec,
                            Status.UNCHANGED,
                            planned.action,
                            "generated content is unchanged",
                            exit_code,
                        )
                    )
                    continue

                def write_generated_output(
                    temporary: Path,
                    output: str = output,
                ) -> None:
                    temporary.write_text(output)

                atomic_install(spec.target, write_generated_output)
            elif planned.action in {
                GenerateAction.CLONE,
                GenerateAction.UPDATE,
                GenerateAction.RUN,
            }:
                staging: Path | None = None
                command_spec = spec
                target = spec.target
                if planned.action is GenerateAction.CLONE:
                    assert target is not None
                    target.parent.mkdir(parents=True, exist_ok=True)
                    staging = Path(
                        tempfile.mkdtemp(
                            dir=target.parent,
                            prefix=f".{target.name}.clone-",
                        )
                    )
                    staging.rmdir()
                    command_spec = replace(
                        spec,
                        command=(*spec.command[:-1], str(staging)),
                    )
                try:
                    completed = run_command(
                        command_spec,
                        home,
                        capture_output=capture_output,
                    )
                    exit_code = completed.returncode
                    if capture_output:
                        emit_command_output(spec, completed.stdout)
                        emit_command_output(spec, completed.stderr)
                    if completed.returncode != 0:
                        raise RuntimeError(command_failure_reason(completed))
                    if spec.revision is not None:
                        checkout_directory = staging or target
                        assert checkout_directory is not None
                        checkout_revision(
                            spec,
                            checkout_directory,
                            home,
                            capture_output=capture_output,
                        )
                    if staging is not None:
                        assert target is not None
                        staging.rename(target)
                finally:
                    if staging is not None:
                        shutil.rmtree(staging, ignore_errors=True)
            elif planned.action is GenerateAction.DOWNLOAD:
                assert spec.source is not None
                assert spec.sha256 is not None
                assert spec.target is not None
                content = downloader(spec.source, spec.timeout_seconds)
                digest = hashlib.sha256(content).hexdigest()
                if digest != spec.sha256:
                    raise RuntimeError(
                        f"checksum mismatch: expected {spec.sha256}, received {digest}",
                    )

                def write_downloaded_content(
                    temporary: Path,
                    downloaded: bytes = content,
                ) -> None:
                    temporary.write_bytes(downloaded)

                atomic_install(spec.target, write_downloaded_content)
                exit_code = None
            elif planned.action is GenerateAction.REMOVE:
                if spec.name == "zsh.compdump":
                    for file_path in home.glob(".zcompdump*"):
                        file_path.unlink(missing_ok=True)
                else:
                    assert spec.target is not None
                    spec.target.unlink(missing_ok=True)
                exit_code = None
            else:
                raise RuntimeError(f"unsupported generate action: {planned.action}")
        except (
            OSError,
            RuntimeError,
            subprocess.TimeoutExpired,
            urllib.error.URLError,
        ) as error:
            reason = (
                timeout_reason(spec, error)
                if isinstance(error, subprocess.TimeoutExpired)
                else str(error)
            )
            if (
                planned.action is GenerateAction.UPDATE
                and spec.name.startswith("plugin.")
                and spec.revision is not None
                and spec.target is not None
            ):
                try:
                    actual_revision = read_revision(spec, spec.target, home)
                except OSError, RuntimeError, subprocess.TimeoutExpired:
                    actual_revision = "unavailable"
                reason = (
                    f"{reason}; target revision: {spec.revision}; actual revision: "
                    f"{actual_revision}; path: {spec.target}; action: inspect the plugin "
                    "checkout and rerun generate"
                )
            failed = GenerateResult(
                spec,
                Status.FAILED,
                planned.action,
                reason,
                exit_code,
            )
            results.append(failed)
            continue
        succeeded = GenerateResult(
            spec,
            Status.SUCCEEDED,
            planned.action,
            exit_code=exit_code,
        )
        results.append(succeeded)
    return GenerateReport(
        apply=True,
        results=tuple(results),
        generated_root=plan.generated_root,
        network=plan.network,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate the generated/ shell state owned by this repository.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the planned generated changes (default: preview only)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="skip steps that need network access",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit the report as JSON on stdout",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root that owns generated/ (default: this checkout)",
    )
    args = parser.parse_args(argv)
    home = Path.home()
    try:
        apply_allowed = mutation_allowed(home)
        if args.apply:
            require_mutation_allowed(home)
        report = plan_generate(
            args.repo_root,
            home,
            network=not args.offline,
        )
        if args.apply:
            report = execute_generate(
                report,
                home,
                on_start=None if args.as_json else announce_generate_step,
                capture_output=args.as_json,
            )
    except HostPolicyError as error:
        emit_error(
            "generate",
            str(error),
            as_json=args.as_json,
            apply=args.apply,
            code=error.code,
        )
        return 1
    if args.as_json:
        print(
            json.dumps(
                generate_document(report, apply_allowed=apply_allowed),
                indent=2,
                sort_keys=True,
            ),
        )
        for result in report.results:
            if result.status is Status.FAILED:
                print(
                    f"[{result.spec.name}] FAIL {result.reason}",
                    file=sys.stderr,
                )
    else:
        render_generate(report, apply_allowed=apply_allowed)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
