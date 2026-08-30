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

from .host_policy import HostPolicyError, mutation_allowed, require_mutation_allowed
from .mise import canonical_mise_executable, canonical_mise_path
from .models import ExecutableFinder
from .render import emit_error

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
    VALIDATE = "validate"


@dataclass(frozen=True)
class RuntimeSpec:
    name: str
    tool: str | None
    target: Path | None = None
    command: tuple[str, ...] = ()
    source: str | None = None
    revision: str | None = None
    sha256: str | None = None
    environment: tuple[tuple[str, str], ...] = ()
    timeout_seconds: int = 120


@dataclass(frozen=True)
class ShellInitSpec:
    name: str
    tool: str
    shell: str
    command: tuple[str, ...]
    filename: str


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
    generated_root: Path | None = None
    network: bool = True

    @property
    def ok(self) -> bool:
        return all(result.status is not RuntimeStatus.FAILED for result in self.results)


FUNCTION_SPECS = (
    ShellInitSpec("mise", "mise", "zsh", ("mise", "activate", "zsh"), "_mise.zsh"),
    ShellInitSpec(
        "starship", "starship", "zsh", ("starship", "init", "zsh"), "_starship.zsh"
    ),
    ShellInitSpec(
        "atuin",
        "atuin",
        "zsh",
        ("atuin", "init", "zsh", "--disable-up-arrow"),
        "_atuin.zsh",
    ),
    ShellInitSpec(
        "zoxide",
        "zoxide",
        "zsh",
        ("zoxide", "init", "zsh", "--cmd", "j"),
        "_zoxide.zsh",
    ),
    ShellInitSpec("tv", "tv", "zsh", ("tv", "init", "zsh"), "_tv.zsh"),
    ShellInitSpec(
        "try-rs",
        "try-rs",
        "zsh",
        ("try-rs", "--setup-stdout", "zsh"),
        "_try-rs.zsh",
    ),
    ShellInitSpec(
        "starship-bash",
        "starship",
        "bash",
        ("starship", "init", "bash"),
        "_starship.bash",
    ),
    ShellInitSpec(
        "atuin-bash",
        "atuin",
        "bash",
        ("atuin", "init", "bash", "--disable-up-arrow"),
        "_atuin.bash",
    ),
    ShellInitSpec(
        "zoxide-bash",
        "zoxide",
        "bash",
        ("zoxide", "init", "bash", "--cmd", "j"),
        "_zoxide.bash",
    ),
    ShellInitSpec(
        "mise-bash", "mise", "bash", ("mise", "activate", "bash"), "_mise.bash"
    ),
    ShellInitSpec("mise-nu", "mise", "nu", ("mise", "activate", "nu"), "_mise.nu"),
    ShellInitSpec(
        "zoxide-nu",
        "zoxide",
        "nu",
        ("zoxide", "init", "nushell"),
        "_zoxide.nu",
    ),
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
    # Keep the resolver inputs exact: this generator is an explicit runtime
    # refresh boundary, not a request to execute the latest PyPI release.
    (
        "llm",
        "uvx",
        ("uvx", "--with", "httpx==0.28.1", "llm==0.33"),
        "_llm",
        (("_LLM_COMPLETE", "zsh_source"),),
    ),
)

PLUGIN_SPECS = (
    (
        "fzf-tab",
        "https://github.com/Aloxaf/fzf-tab",
        "24105b15714bfec37989ed5c5b6e60f572253019",
        "fzf-tab.plugin.zsh",
    ),
    (
        "zsh-autosuggestions",
        "https://github.com/zsh-users/zsh-autosuggestions",
        "85919cd1ffa7d2d5412f6d3fe437ebdbeeec4fc5",
        "zsh-autosuggestions.zsh",
    ),
    (
        "fast-syntax-highlighting",
        "https://github.com/zdharma-continuum/fast-syntax-highlighting",
        "3d574ccf48804b10dca52625df13da5edae7f553",
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

OWNED_GENERATED_DIRECTORIES = ("functions", "completions", "plugins")


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
    for name, source, revision, _entrypoint in PLUGIN_SPECS:
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
        RuntimeResult(compdump_spec, RuntimeStatus.PLANNED, RuntimeAction.REMOVE)
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


def _atomic_install(target: Path, writer: AtomicWriter) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    try:
        writer(temporary)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def _command_environment(spec: RuntimeSpec, home: Path) -> dict[str, str]:
    if spec.name == "completion.llm":
        # LLM completion generation only needs a resolver path and temporary
        # directory. Do not expose the user's API keys or other shell state to
        # the downloaded package environment.
        environment = {
            "HOME": str(home),
            "PATH": os.environ.get("PATH", os.defpath),
        }
        for name in ("TMPDIR", "TMP", "TEMP", "LANG", "LC_ALL"):
            if value := os.environ.get(name):
                environment[name] = value
        environment.update(dict(spec.environment))
        return environment

    environment = os.environ.copy()
    environment["HOME"] = str(home)
    environment.update(dict(spec.environment))
    if spec.tool == "mise" and spec.name.startswith("function."):
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
        cwd=home,
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


def _read_revision(
    spec: RuntimeSpec,
    directory: Path,
    home: Path,
) -> str:
    verify_spec = replace(
        spec,
        command=("git", "-C", str(directory), "rev-parse", "HEAD"),
    )
    verified = _run_command(verify_spec, home, capture_output=True)
    if verified.returncode != 0:
        raise RuntimeError(_command_failure_reason(verified))
    return verified.stdout.strip()


def _set_revision(
    spec: RuntimeSpec,
    directory: Path,
    revision: str,
    home: Path,
    *,
    capture_output: bool,
) -> None:
    checkout_spec = replace(
        spec,
        command=("git", "-C", str(directory), "checkout", "--detach", revision),
    )
    checkout = _run_command(checkout_spec, home, capture_output=capture_output)
    if capture_output:
        _emit_command_output(spec, checkout.stdout)
        _emit_command_output(spec, checkout.stderr)
    if checkout.returncode != 0:
        raise RuntimeError(_command_failure_reason(checkout))

    actual_revision = _read_revision(spec, directory, home)
    if actual_revision != revision:
        raise RuntimeError(
            f"revision mismatch: expected {revision}, received {actual_revision}",
        )


def _checkout_revision(
    spec: RuntimeSpec,
    directory: Path,
    home: Path,
    *,
    capture_output: bool,
) -> None:
    assert spec.revision is not None
    _set_revision(
        spec,
        directory,
        spec.revision,
        home,
        capture_output=capture_output,
    )


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

                def write_generated_output(
                    temporary: Path,
                    output: str = completed.stdout,
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


def _document(
    report: RuntimeReport,
    *,
    apply_allowed: bool = True,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "operation": "runtime",
        "apply": report.apply,
        "ok": report.ok,
        "next": list(_next_commands(report, apply_allowed=apply_allowed)),
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
                "revision": result.spec.revision,
                "sha256": result.spec.sha256,
                "reason": result.reason,
                "exit_code": result.exit_code,
            }
            for result in report.results
        ],
        "summary": _summary(report),
    }


def _next_commands(
    report: RuntimeReport,
    *,
    apply_allowed: bool = True,
) -> tuple[str, ...]:
    if not report.apply:
        if (
            not apply_allowed
            or not report.ok
            or not any(
                result.status is RuntimeStatus.PLANNED for result in report.results
            )
        ):
            return ()
        arguments = ["mise", "run", "runtime", "--"]
        if report.generated_root is not None:
            arguments.extend(("--repo-root", str(report.generated_root.parent)))
        if not report.network:
            arguments.append("--offline")
        arguments.append("--apply")
        return (shlex.join(arguments),)
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
    revision = f" [revision={spec.revision}]" if spec.revision else ""
    if action is RuntimeAction.GENERATE:
        return f"{command} -> {spec.target}"
    if command:
        return f"{command}{revision}"
    if action is RuntimeAction.DOWNLOAD:
        return f"download {spec.source} -> {spec.target}"
    if action is RuntimeAction.REMOVE:
        return f"remove {spec.target}"
    return str(spec.target or action)


def _render(report: RuntimeReport, *, apply_allowed: bool = True) -> None:
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
            if apply_allowed:
                print("No files changed. Re-run with --apply to refresh the runtime.")
                print("Next:")
                for command in _next_commands(report):
                    print(f"  {command}")
            else:
                print("No files changed. Host policy disables runtime apply.")
        else:
            print("No runtime refresh steps are available on this host.")
        return
    if _shell_restart_required(report):
        print("Refreshed shell runtime is not active in existing shells.")
        print(
            "Restart the affected shell; for Zsh, open a new shell or run `exec zsh`."
        )
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
