"""Refresh generated shell runtime owned by this repository."""

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

from .host_policy import HostPolicyError, mutation_allowed, require_mutation_allowed
from .mise import canonical_mise_executable, canonical_mise_path
from .models import ExecutableFinder
from .render import emit_error
from .runtime_commands import (
    _atomic_install,
    _checkout_revision,
    _command_failure_reason,
    _download,
    _emit_command_output,
    _read_revision,
    _run_command,
    _timeout_reason,
    guarded_activation,
    inspect_plugin,
)
from .runtime_models import (
    AtomicWriter,
    Downloader,
    RuntimeAction,
    RuntimeReport,
    RuntimeResult,
    RuntimeSpec,
    RuntimeStatus,
    ShellInitSpec,
    StepCallback,
)
from .runtime_render import _announce_step, _document, _next_commands, _render
from .runtime_specs import (
    COMPLETION_SPECS,
    FUNCTION_SPECS,
    OWNED_GENERATED_DIRECTORIES,
    PLUGIN_SPECS,
    WASM_SPECS,
)

__all__ = [
    "COMPLETION_SPECS",
    "FUNCTION_SPECS",
    "OWNED_GENERATED_DIRECTORIES",
    "PLUGIN_SPECS",
    "WASM_SPECS",
    "AtomicWriter",
    "Downloader",
    "RuntimeAction",
    "RuntimeReport",
    "RuntimeResult",
    "RuntimeSpec",
    "RuntimeStatus",
    "ShellInitSpec",
    "StepCallback",
    "_next_commands",
    "_render",
    "execute_runtime",
    "file_sha256",
    "plan_runtime",
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
        f"generated runtime directory is a symlink ({os.readlink(directory)}); "
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
    """Resolve tools from PATH while rejecting stale Mise shims."""
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
        if found:
            return found
        return None

    return find


def _generator_result(
    spec: RuntimeSpec,
    *,
    executable_finder: ExecutableFinder,
) -> RuntimeResult:
    assert spec.tool is not None
    assert spec.target is not None
    if executable_finder(spec.tool):
        return RuntimeResult(spec, RuntimeStatus.PLANNED, RuntimeAction.GENERATE)
    if spec.target.exists() or spec.target.is_symlink():
        return RuntimeResult(
            spec,
            RuntimeStatus.PLANNED,
            RuntimeAction.REMOVE,
            f"{spec.tool} is not available; remove stale owned output",
        )
    return RuntimeResult(
        spec,
        RuntimeStatus.SKIPPED,
        RuntimeAction.GENERATE,
        f"{spec.tool} is not available on PATH",
    )


def plan_runtime(
    repo_root: Path,
    home: Path,
    *,
    executable_finder: ExecutableFinder = shutil.which,
    network: bool = True,
) -> RuntimeReport:
    """Return the exact generated runtime refresh without changing files."""
    generated_root = repo_root / "generated"
    if symlinked_directory := _symlinked_generated_directory(generated_root):
        relative_name = (
            symlinked_directory.relative_to(repo_root).as_posix().replace("/", ".")
        )
        spec = RuntimeSpec(
            name=f"directory.{relative_name}",
            tool=None,
            target=symlinked_directory,
        )
        return RuntimeReport(
            apply=False,
            results=(
                RuntimeResult(
                    spec,
                    RuntimeStatus.FAILED,
                    RuntimeAction.VALIDATE,
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
        spec = RuntimeSpec(
            name=f"function.{function_spec.name}",
            tool=tool,
            target=functions_dir / function_spec.filename,
            command=command,
        )
        results.append(_generator_result(spec, executable_finder=generator_finder))
    for name, tool, command, filename, environment in COMPLETION_SPECS:
        effective_command = (
            (command[0], "--offline", *command[1:])
            if tool == "uvx" and not network
            else command
        )
        spec = RuntimeSpec(
            name=f"completion.{name}",
            tool=tool,
            target=completions_dir / filename,
            command=effective_command,
            environment=environment,
        )
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
            RuntimeAction.UPDATE
            if not is_symlink
            and not git_directory_is_symlink
            and git_directory.is_dir()
            else RuntimeAction.CLONE
        )
        spec = RuntimeSpec(
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
                if action is RuntimeAction.UPDATE
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
                RuntimeResult(
                    spec,
                    RuntimeStatus.FAILED,
                    action,
                    f"plugin target is a symlink ({os.readlink(target)}); "
                    "remove it before refreshing",
                ),
            )
        elif git_directory_is_symlink:
            results.append(
                RuntimeResult(
                    spec,
                    RuntimeStatus.FAILED,
                    action,
                    f"plugin Git metadata is a symlink "
                    f"({os.readlink(git_directory)}); remove it before refreshing",
                ),
            )
        elif action is RuntimeAction.UPDATE and git_available:
            try:
                current = inspect_plugin(spec, home)
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                results.append(
                    RuntimeResult(spec, RuntimeStatus.FAILED, action, str(error))
                )
            else:
                results.append(
                    RuntimeResult(
                        spec,
                        RuntimeStatus.SKIPPED,
                        action,
                        "pinned revision and tracked files are current",
                    )
                    if current
                    else RuntimeResult(spec, RuntimeStatus.PLANNED, action)
                    if network
                    else RuntimeResult(
                        spec,
                        RuntimeStatus.SKIPPED,
                        action,
                        "network refresh is disabled",
                    )
                )
        elif not network:
            results.append(
                RuntimeResult(
                    spec,
                    RuntimeStatus.SKIPPED,
                    action,
                    "network refresh is disabled",
                ),
            )
        elif target.exists() and action is RuntimeAction.CLONE:
            results.append(
                RuntimeResult(
                    spec,
                    RuntimeStatus.FAILED,
                    action,
                    "target exists but is not a Git checkout",
                ),
            )
        elif git_available:
            results.append(RuntimeResult(spec, RuntimeStatus.PLANNED, action))
        else:
            results.append(
                RuntimeResult(
                    spec,
                    RuntimeStatus.SKIPPED,
                    action,
                    "git is not available on PATH",
                ),
            )
    for name, source, sha256 in WASM_SPECS:
        target = plugins_dir / f"{name}.wasm"
        spec = RuntimeSpec(
            name=f"wasm.{name}",
            tool=None,
            target=target,
            source=source,
            sha256=sha256,
            timeout_seconds=60,
        )
        if file_sha256(target) == sha256:
            results.append(
                RuntimeResult(
                    spec,
                    RuntimeStatus.SKIPPED,
                    RuntimeAction.DOWNLOAD,
                    "checksum is current",
                ),
            )
        elif network:
            results.append(
                RuntimeResult(spec, RuntimeStatus.PLANNED, RuntimeAction.DOWNLOAD),
            )
        else:
            results.append(
                RuntimeResult(
                    spec,
                    RuntimeStatus.SKIPPED,
                    RuntimeAction.DOWNLOAD,
                    "network refresh is disabled",
                ),
            )
    bat_spec = RuntimeSpec(
        name="bat.cache",
        tool="bat",
        command=("bat", "cache", "--build"),
    )
    results.append(
        RuntimeResult(bat_spec, RuntimeStatus.PLANNED, RuntimeAction.RUN)
        if executable_finder("bat")
        else RuntimeResult(
            bat_spec,
            RuntimeStatus.SKIPPED,
            RuntimeAction.RUN,
            "bat is not available on PATH",
        ),
    )
    compdumps = tuple(sorted(home.glob(".zcompdump*")))
    compdump_spec = RuntimeSpec(
        name="zsh.compdump",
        tool=None,
        target=home / ".zcompdump*",
    )
    results.append(
        RuntimeResult(
            compdump_spec,
            RuntimeStatus.PLANNED,
            RuntimeAction.REMOVE,
            "invalidate only if completion outputs change",
        )
        if compdumps
        else RuntimeResult(
            compdump_spec,
            RuntimeStatus.SKIPPED,
            RuntimeAction.REMOVE,
            "no zcompdump files exist",
        ),
    )
    return RuntimeReport(
        apply=False,
        results=tuple(results),
        generated_root=generated_root,
        network=network,
    )


def execute_runtime(
    plan: RuntimeReport,
    home: Path,
    *,
    downloader: Downloader = _download,
    on_start: StepCallback | None = None,
    capture_output: bool = True,
) -> RuntimeReport:
    """Execute a previously rendered runtime plan."""
    require_mutation_allowed(home)
    results = []
    for planned in plan.results:
        spec = planned.spec
        if planned.status is not RuntimeStatus.PLANNED:
            results.append(planned)
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
                spec.target if planned.action is RuntimeAction.UPDATE else None
            )
            if command_directory is not None and command_directory.is_symlink():
                raise RuntimeError(
                    "runtime command directory is a symlink "
                    f"({os.readlink(command_directory)}); refusing to execute outside "
                    "generated state",
                )
            if command_directory is not None:
                command_git_directory = command_directory / ".git"
                if command_git_directory.is_symlink():
                    raise RuntimeError(
                        "runtime command Git metadata is a symlink "
                        f"({os.readlink(command_git_directory)}); refusing to execute "
                        "outside generated state",
                    )
                if not command_git_directory.is_dir():
                    raise RuntimeError(
                        "runtime command Git metadata is not a directory; refusing "
                        "to execute outside generated state",
                    )
            if planned.action is RuntimeAction.GENERATE:
                completed = _run_command(spec, home, capture_output=True)
                exit_code = completed.returncode
                _emit_command_output(spec, completed.stderr)
                if completed.returncode != 0:
                    raise RuntimeError(_command_failure_reason(completed))
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
                        RuntimeResult(
                            spec,
                            RuntimeStatus.SKIPPED,
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

                _atomic_install(spec.target, write_generated_output)
            elif planned.action in {
                RuntimeAction.CLONE,
                RuntimeAction.UPDATE,
                RuntimeAction.RUN,
            }:
                staging: Path | None = None
                command_spec = spec
                target = spec.target
                if planned.action is RuntimeAction.CLONE:
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
                    completed = _run_command(
                        command_spec,
                        home,
                        capture_output=capture_output,
                    )
                    exit_code = completed.returncode
                    if capture_output:
                        _emit_command_output(spec, completed.stdout)
                        _emit_command_output(spec, completed.stderr)
                    if completed.returncode != 0:
                        raise RuntimeError(_command_failure_reason(completed))
                    if spec.revision is not None:
                        checkout_directory = staging or target
                        assert checkout_directory is not None
                        _checkout_revision(
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
            elif planned.action is RuntimeAction.DOWNLOAD:
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

                _atomic_install(spec.target, write_downloaded_content)
                exit_code = None
            elif planned.action is RuntimeAction.REMOVE:
                if spec.name == "zsh.compdump":
                    if not any(
                        result.status is RuntimeStatus.SUCCEEDED
                        and result.spec.name.startswith("completion.")
                        for result in results
                    ):
                        results.append(
                            RuntimeResult(
                                spec,
                                RuntimeStatus.SKIPPED,
                                planned.action,
                                "completion outputs are unchanged",
                            )
                        )
                        continue
                    for file_path in home.glob(".zcompdump*"):
                        file_path.unlink(missing_ok=True)
                else:
                    assert spec.target is not None
                    spec.target.unlink(missing_ok=True)
                exit_code = None
            else:
                raise RuntimeError(f"unsupported runtime action: {planned.action}")
        except (
            OSError,
            RuntimeError,
            subprocess.TimeoutExpired,
            urllib.error.URLError,
        ) as error:
            reason = (
                _timeout_reason(spec, error)
                if isinstance(error, subprocess.TimeoutExpired)
                else str(error)
            )
            if (
                planned.action is RuntimeAction.UPDATE
                and spec.name.startswith("plugin.")
                and spec.revision is not None
                and spec.target is not None
            ):
                try:
                    actual_revision = _read_revision(spec, spec.target, home)
                except OSError, RuntimeError, subprocess.TimeoutExpired:
                    actual_revision = "unavailable"
                reason = (
                    f"{reason}; target revision: {spec.revision}; actual revision: "
                    f"{actual_revision}; path: {spec.target}; action: inspect the plugin "
                    "checkout and rerun the runtime update"
                )
            failed = RuntimeResult(
                spec,
                RuntimeStatus.FAILED,
                planned.action,
                reason,
                exit_code,
            )
            results.append(failed)
            continue
        succeeded = RuntimeResult(
            spec,
            RuntimeStatus.SUCCEEDED,
            planned.action,
            exit_code=exit_code,
        )
        results.append(succeeded)
    return RuntimeReport(
        apply=True,
        results=tuple(results),
        generated_root=plan.generated_root,
        network=plan.network,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Refresh generated shell runtime owned by this repository.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the planned runtime changes (default: preview only)",
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
        help="repository root that owns the runtime (default: this checkout)",
    )
    args = parser.parse_args(argv)
    home = Path.home()
    try:
        apply_allowed = mutation_allowed(home)
        if args.apply:
            require_mutation_allowed(home)
        report = plan_runtime(
            args.repo_root,
            home,
            network=not args.offline,
        )
        if args.apply:
            report = execute_runtime(
                report,
                home,
                on_start=None if args.as_json else _announce_step,
                capture_output=args.as_json,
            )
    except HostPolicyError as error:
        emit_error(
            "runtime",
            str(error),
            as_json=args.as_json,
            apply=args.apply,
            code=error.code,
        )
        return 1
    if args.as_json:
        print(
            json.dumps(
                _document(report, apply_allowed=apply_allowed),
                indent=2,
                sort_keys=True,
            ),
        )
        for result in report.results:
            if result.status is RuntimeStatus.FAILED:
                print(
                    f"[{result.spec.name}] FAIL {result.reason}",
                    file=sys.stderr,
                )
    else:
        _render(report, apply_allowed=apply_allowed)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
