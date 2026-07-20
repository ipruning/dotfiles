"""Refresh generated shell runtime owned by this repository."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

from .models import ExecutableFinder

Downloader = Callable[[str, int], bytes]
AtomicWriter = Callable[[Path], object]


class RuntimeStatus(StrEnum):
    PLANNED = "planned"
    SKIPPED = "skipped"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RuntimeAction(StrEnum):
    GENERATE = "generate"
    CLONE = "clone"
    UPDATE = "update"
    RUN = "run"
    DOWNLOAD = "download"
    REMOVE = "remove"
    BUILD = "build"


@dataclass(frozen=True)
class RuntimeSpec:
    name: str
    tool: str | None
    target: Path | None = None
    command: tuple[str, ...] = ()
    source: str | None = None
    sha256: str | None = None
    working_directory: Path | None = None
    artifact: Path | None = None
    depends_on: str | None = None
    environment: tuple[tuple[str, str], ...] = ()
    timeout_seconds: int = 120


@dataclass(frozen=True)
class RuntimeResult:
    spec: RuntimeSpec
    status: RuntimeStatus
    action: RuntimeAction
    reason: str | None = None
    exit_code: int | None = None


StepCallback = Callable[[RuntimeSpec, RuntimeAction], None]


@dataclass(frozen=True)
class RuntimeReport:
    apply: bool
    results: tuple[RuntimeResult, ...]

    @property
    def ok(self) -> bool:
        return all(result.status is not RuntimeStatus.FAILED for result in self.results)


FUNCTION_SPECS = (
    ("mise", ("mise", "activate", "zsh"), "_mise.zsh"),
    ("starship", ("starship", "init", "zsh"), "_starship.zsh"),
    ("atuin", ("atuin", "init", "zsh", "--disable-up-arrow"), "_atuin.zsh"),
)

COMPLETION_SPECS = (
    ("bootdev", "bootdev", ("bootdev", "completion", "zsh"), "_bootdev", ()),
    ("ov", "ov", ("ov", "--completion", "zsh"), "_ov", ()),
    ("just", "just", ("just", "--completions", "zsh"), "_just", ()),
    ("codex", "codex", ("codex", "completion", "zsh"), "_codex", ()),
    ("jj", "jj", ("jj", "util", "completion", "zsh"), "_jj", ()),
    ("linear", "linear", ("linear", "completions", "zsh"), "_linear", ()),
    ("sesh", "sesh", ("sesh", "completion", "zsh"), "_sesh", ()),
    ("op", "op", ("op", "completion", "zsh"), "_op", ()),
    (
        "llm",
        "uvx",
        ("uvx", "llm"),
        "_llm",
        (("_LLM_COMPLETE", "zsh_source"),),
    ),
)

PLUGIN_SPECS = (
    (
        "fzf-tab",
        "https://github.com/Aloxaf/fzf-tab",
        "fzf-tab.plugin.zsh",
    ),
    (
        "zsh-autosuggestions",
        "https://github.com/zsh-users/zsh-autosuggestions",
        "zsh-autosuggestions.zsh",
    ),
    (
        "fast-syntax-highlighting",
        "https://github.com/zdharma-continuum/fast-syntax-highlighting",
        "fast-syntax-highlighting.plugin.zsh",
    ),
)

WASM_SPECS = (
    (
        "zellij-sessionizer",
        "https://github.com/laperlej/zellij-sessionizer/releases/download/v0.5.0/zellij-sessionizer.wasm",
        "c41841c023e74e81f99a0fd8d95e0504ed202df2cdb92604df51c9e4ea0ba05b",
    ),
    (
        "zjstatus",
        "https://github.com/dj95/zjstatus/releases/download/v0.23.0/zjstatus.wasm",
        "e006901223524239db618021e4cc5d17f82dc4bfae5432895ba41f03f13861ff",
    ),
)

LOCAL_BINARY_SPECS = (
    (
        "atuin",
        "https://github.com/ipruning/atuin.git",
        ("cargo", "build", "--release", "-p", "atuin", "--locked"),
        Path("target/release/atuin"),
    ),
    (
        "op-cache",
        "https://github.com/craftzdog/op-cache.git",
        ("cargo", "build", "--release", "--locked"),
        Path("target/release/op-cache"),
    ),
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


def repo_aware_finder(
    repo_root: Path,
    executable_finder: ExecutableFinder,
) -> ExecutableFinder:
    """Resolve tools from PATH or from the repository's own built binaries.

    Task environments do not expose generated/bin, so gating on PATH alone
    would treat self-built tools (atuin) as absent and remove their owned
    runtime files. A mise shim only proves a tool was installed at some
    point; after a configuration change the shim can outlive its tool, so
    shim hits are validated with `mise which` before they count as present.
    """
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
        owned = repo_root / "generated/bin" / tool
        if owned.is_file() and os.access(owned, os.X_OK):
            return str(owned)
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
    build: bool = False,
) -> RuntimeReport:
    """Return the exact generated runtime refresh without changing files."""
    executable_finder = repo_aware_finder(repo_root, executable_finder)
    functions_dir = repo_root / "generated/functions"
    completions_dir = repo_root / "generated/completions"
    plugins_dir = repo_root / "generated/plugins"
    results = []
    for tool, command, filename in FUNCTION_SPECS:
        spec = RuntimeSpec(
            name=f"function.{tool}",
            tool=tool,
            target=functions_dir / filename,
            command=command,
        )
        results.append(_generator_result(spec, executable_finder=executable_finder))
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
    for name, source, _entrypoint in PLUGIN_SPECS:
        target = plugins_dir / name
        action = (
            RuntimeAction.UPDATE if (target / ".git").is_dir() else RuntimeAction.CLONE
        )
        spec = RuntimeSpec(
            name=f"plugin.{name}",
            tool="git",
            target=target,
            source=source,
            command=(
                ("git", "-C", str(target), "pull", "--ff-only")
                if action is RuntimeAction.UPDATE
                else ("git", "clone", "--depth=1", source, str(target))
            ),
        )
        if not network:
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
    legacy_try_rs = completions_dir / "_try-rs"
    legacy_try_rs_spec = RuntimeSpec(
        name="completion.try-rs-legacy",
        tool=None,
        target=legacy_try_rs,
    )
    if legacy_try_rs.exists() or legacy_try_rs.is_symlink():
        results.append(
            RuntimeResult(
                legacy_try_rs_spec,
                RuntimeStatus.PLANNED,
                RuntimeAction.REMOVE,
            ),
        )
    compdumps = tuple(sorted(home.glob(".zcompdump*")))
    compdump_spec = RuntimeSpec(
        name="zsh.compdump",
        tool=None,
        target=home / ".zcompdump*",
    )
    results.append(
        RuntimeResult(compdump_spec, RuntimeStatus.PLANNED, RuntimeAction.REMOVE)
        if compdumps
        else RuntimeResult(
            compdump_spec,
            RuntimeStatus.SKIPPED,
            RuntimeAction.REMOVE,
            "no zcompdump files exist",
        ),
    )
    if build:
        sources_dir = repo_root / "generated/sources"
        cargo_available = executable_finder("cargo") is not None
        for name, source, build_command, artifact_relative in LOCAL_BINARY_SPECS:
            source_dir = sources_dir / name
            source_action = (
                RuntimeAction.UPDATE
                if (source_dir / ".git").is_dir()
                else RuntimeAction.CLONE
            )
            source_spec = RuntimeSpec(
                name=f"source.{name}",
                tool="git",
                target=source_dir,
                source=source,
                command=(
                    ("git", "-C", str(source_dir), "pull", "--ff-only")
                    if source_action is RuntimeAction.UPDATE
                    else ("git", "clone", "--depth=1", source, str(source_dir))
                ),
            )
            if not network:
                results.append(
                    RuntimeResult(
                        source_spec,
                        RuntimeStatus.SKIPPED,
                        source_action,
                        "network refresh is disabled",
                    ),
                )
            elif source_dir.exists() and source_action is RuntimeAction.CLONE:
                results.append(
                    RuntimeResult(
                        source_spec,
                        RuntimeStatus.FAILED,
                        source_action,
                        "source target exists but is not a Git checkout",
                    ),
                )
            elif git_available:
                results.append(
                    RuntimeResult(source_spec, RuntimeStatus.PLANNED, source_action),
                )
            else:
                results.append(
                    RuntimeResult(
                        source_spec,
                        RuntimeStatus.SKIPPED,
                        source_action,
                        "git is not available on PATH",
                    ),
                )
            binary_spec = RuntimeSpec(
                name=f"binary.{name}",
                tool="cargo",
                target=repo_root / "generated/bin" / name,
                command=(
                    (*build_command, "--offline") if not network else build_command
                ),
                source=source,
                working_directory=source_dir,
                artifact=source_dir / artifact_relative,
                depends_on=f"source.{name}",
                timeout_seconds=1800,
            )
            source_is_checkout = (source_dir / ".git").is_dir()
            source_will_exist = (
                source_is_checkout and (not network or git_available)
            ) or (not source_dir.exists() and network and git_available)
            if cargo_available and source_will_exist:
                results.append(
                    RuntimeResult(
                        binary_spec,
                        RuntimeStatus.PLANNED,
                        RuntimeAction.BUILD,
                    ),
                )
            else:
                if not cargo_available:
                    missing = "cargo"
                elif network and not git_available:
                    missing = "git"
                else:
                    missing = "build source"
                results.append(
                    RuntimeResult(
                        binary_spec,
                        RuntimeStatus.SKIPPED,
                        RuntimeAction.BUILD,
                        f"{missing} is not available",
                    ),
                )
    return RuntimeReport(apply=False, results=tuple(results))


def _atomic_install(target: Path, writer: AtomicWriter) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    try:
        writer(temporary)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def _command_environment(spec: RuntimeSpec, home: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    owned_root = spec.target if spec.target is not None else spec.working_directory
    if spec.command and owned_root is not None:
        # Command subprocesses must resolve self-built tools that exist
        # only under the repository's generated/bin sibling directory.
        owned_bin = owned_root.parent.parent / "bin"
        environment["PATH"] = f"{owned_bin}{os.pathsep}{environment.get('PATH', '')}"
    environment.update(dict(spec.environment))
    if spec.name == "function.mise":
        for name in (
            "__MISE_DIFF",
            "__MISE_SESSION",
            "__MISE_ORIG_PATH",
            "MISE_SHELL",
            "__MISE_ZSH_PRECMD_RUN",
        ):
            environment.pop(name, None)
    return environment


def _run_command(
    spec: RuntimeSpec,
    home: Path,
    *,
    capture_output: bool,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        spec.command,
        cwd=spec.working_directory or home,
        check=False,
        stdin=subprocess.DEVNULL,
        capture_output=capture_output,
        text=True,
        timeout=spec.timeout_seconds,
        env=_command_environment(spec, home),
    )


def _emit_command_output(spec: RuntimeSpec, output: str | None) -> None:
    for line in (output or "").splitlines():
        print(f"[{spec.name}] {line}", file=sys.stderr)


def _command_failure_reason(completed: subprocess.CompletedProcess[str]) -> str:
    reason = f"command exited {completed.returncode}"
    detail = (completed.stderr or "").strip()
    return f"{reason}: {detail}" if detail else reason


def _download(source: str, timeout_seconds: int) -> bytes:
    request = urllib.request.Request(source, headers={"User-Agent": "dotfiles-runtime"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def execute_runtime(
    plan: RuntimeReport,
    home: Path,
    *,
    downloader: Downloader = _download,
    on_start: StepCallback | None = None,
    capture_output: bool = True,
) -> RuntimeReport:
    """Execute a previously rendered runtime plan."""
    results = []
    completed_steps: dict[str, RuntimeResult] = {}
    for planned in plan.results:
        if planned.status is not RuntimeStatus.PLANNED:
            results.append(planned)
            completed_steps[planned.spec.name] = planned
            continue
        spec = planned.spec
        if spec.depends_on:
            dependency = completed_steps.get(spec.depends_on)
            if dependency and dependency.status is RuntimeStatus.FAILED:
                blocked = RuntimeResult(
                    spec,
                    RuntimeStatus.SKIPPED,
                    planned.action,
                    f"{spec.depends_on} failed; refusing to use stale input",
                )
                results.append(blocked)
                completed_steps[spec.name] = blocked
                continue
        if on_start:
            on_start(spec, planned.action)
        exit_code: int | None = None
        try:
            if planned.action is RuntimeAction.GENERATE:
                completed = _run_command(spec, home, capture_output=True)
                exit_code = completed.returncode
                _emit_command_output(spec, completed.stderr)
                if completed.returncode != 0:
                    raise RuntimeError(_command_failure_reason(completed))
                if not completed.stdout:
                    raise RuntimeError("generator produced empty output")
                assert spec.target is not None
                _atomic_install(
                    spec.target,
                    lambda temporary: temporary.write_text(completed.stdout),
                )
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
                    if staging is not None:
                        assert target is not None
                        staging.rename(target)
                finally:
                    if staging is not None:
                        shutil.rmtree(staging, ignore_errors=True)
            elif planned.action is RuntimeAction.BUILD:
                artifact = spec.artifact
                assert artifact is not None
                assert spec.target is not None
                completed = _run_command(
                    spec,
                    home,
                    capture_output=capture_output,
                )
                exit_code = completed.returncode
                if capture_output:
                    _emit_command_output(spec, completed.stdout)
                    _emit_command_output(spec, completed.stderr)
                if completed.returncode != 0:
                    raise RuntimeError(_command_failure_reason(completed))
                if not artifact.is_file():
                    raise RuntimeError(f"build artifact is missing: {artifact}")
                _atomic_install(
                    spec.target,
                    lambda temporary: shutil.copy2(artifact, temporary),
                )
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
                _atomic_install(
                    spec.target,
                    lambda temporary: temporary.write_bytes(content),
                )
                exit_code = None
            elif planned.action is RuntimeAction.REMOVE:
                if spec.name == "zsh.compdump":
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
                f"timed out after {spec.timeout_seconds}s"
                if isinstance(error, subprocess.TimeoutExpired)
                else str(error)
            )
            failed = RuntimeResult(
                spec,
                RuntimeStatus.FAILED,
                planned.action,
                reason,
                exit_code,
            )
            results.append(failed)
            completed_steps[spec.name] = failed
            continue
        succeeded = RuntimeResult(
            spec,
            RuntimeStatus.SUCCEEDED,
            planned.action,
            exit_code=exit_code,
        )
        results.append(succeeded)
        completed_steps[spec.name] = succeeded
    return RuntimeReport(apply=True, results=tuple(results))


def _summary(report: RuntimeReport) -> dict[str, int]:
    return {
        status.value: count
        for status in (
            RuntimeStatus.PLANNED,
            RuntimeStatus.SUCCEEDED,
            RuntimeStatus.SKIPPED,
            RuntimeStatus.FAILED,
        )
        if (count := sum(result.status is status for result in report.results))
    }


def _document(report: RuntimeReport) -> dict[str, object]:
    return {
        "schema_version": 1,
        "operation": "runtime",
        "apply": report.apply,
        "ok": report.ok,
        "next": list(_next_commands(report)),
        "shell_restart_required": _shell_restart_required(report),
        "steps": [
            {
                "name": result.spec.name,
                "action": result.action.value,
                "status": result.status.value,
                "tool": result.spec.tool,
                "target": str(result.spec.target) if result.spec.target else None,
                "command": list(result.spec.command),
                "source": result.spec.source,
                "sha256": result.spec.sha256,
                "working_directory": (
                    str(result.spec.working_directory)
                    if result.spec.working_directory
                    else None
                ),
                "artifact": (
                    str(result.spec.artifact) if result.spec.artifact else None
                ),
                "reason": result.reason,
                "exit_code": result.exit_code,
            }
            for result in report.results
        ],
        "summary": _summary(report),
    }


def _next_commands(report: RuntimeReport) -> tuple[str, ...]:
    if not report.apply:
        return (
            ("mise run runtime -- --apply",)
            if report.ok
            and any(result.status is RuntimeStatus.PLANNED for result in report.results)
            else ()
        )
    if not report.ok:
        return ()
    if any(result.status is RuntimeStatus.SUCCEEDED for result in report.results):
        return ("mise run check", "mise run diff")
    return ()


def _shell_restart_required(report: RuntimeReport) -> bool:
    return any(
        result.status is RuntimeStatus.SUCCEEDED
        and (
            result.spec.name.startswith(("function.", "completion.", "plugin."))
            or result.spec.name == "zsh.compdump"
        )
        for result in report.results
    )


def _step_detail(spec: RuntimeSpec, action: RuntimeAction) -> str:
    command = shlex.join(spec.command) if spec.command else ""
    if action is RuntimeAction.GENERATE:
        return f"{command} -> {spec.target}"
    if action is RuntimeAction.BUILD:
        return f"{command} (in {spec.working_directory}) -> {spec.target}"
    if command:
        return command
    if action is RuntimeAction.DOWNLOAD:
        return f"download {spec.source} -> {spec.target}"
    if action is RuntimeAction.REMOVE:
        return f"remove {spec.target}"
    return str(spec.target or action)


def _render(report: RuntimeReport) -> None:
    for result in report.results:
        if result.status is RuntimeStatus.FAILED:
            print(
                f"[{result.spec.name}] FAIL {result.reason}",
                file=sys.stderr,
            )
            continue
        detail = (
            _step_detail(result.spec, result.action)
            if result.status in {RuntimeStatus.PLANNED, RuntimeStatus.SKIPPED}
            else result.action.value
        )
        print(f"{result.status.value.upper():7} {result.spec.name}: {detail}")
        if result.reason:
            print(f"        {result.reason}")
    summary = _summary(report)
    rendered = ", ".join(f"{count} {status}" for status, count in summary.items())
    print(f"Summary: {rendered or 'no steps'}")
    if not report.apply:
        if summary.get(RuntimeStatus.PLANNED.value, 0):
            print("No files changed. Re-run with --apply to refresh the runtime.")
        else:
            print("No runtime refresh steps are available on this host.")
        return
    if _shell_restart_required(report):
        print("Refreshed Zsh runtime is not active in the current shell.")
        print("Open a new Zsh or run `exec zsh` to load it.")
    if not report.ok:
        return
    if _next_commands(report):
        print("Next:")
        for command in _next_commands(report):
            print(f"  {command}")


def _announce_step(spec: RuntimeSpec, action: RuntimeAction) -> None:
    print(f"RUN {spec.name}: {_step_detail(spec, action)}", flush=True)


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
        "--build",
        action="store_true",
        help="include self-built tool steps",
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
    report = plan_runtime(
        args.repo_root,
        Path.home(),
        network=not args.offline,
        build=args.build,
    )
    if args.apply:
        report = execute_runtime(
            report,
            Path.home(),
            on_start=None if args.as_json else _announce_step,
            capture_output=args.as_json,
        )
    if args.as_json:
        print(json.dumps(_document(report), indent=2, sort_keys=True))
        for result in report.results:
            if result.status is RuntimeStatus.FAILED:
                print(
                    f"[{result.spec.name}] FAIL {result.reason}",
                    file=sys.stderr,
                )
    else:
        _render(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
