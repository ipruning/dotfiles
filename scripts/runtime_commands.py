"""Bounded commands, atomic files, and pinned plugin verification."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import urllib.request
from dataclasses import replace
from pathlib import Path
from typing import cast

from .process import run_process_group
from .runtime_models import AtomicWriter, RuntimeSpec


def guarded_activation(spec: RuntimeSpec, output: str) -> str:
    """Keep cached activation bound to its selected executable at consumption."""
    if spec.tool != "mise" or not spec.name.startswith("function."):
        return output
    executable = spec.command[0]
    if spec.name == "function.mise-nu":
        # Mise's Nushell template has no load-time PATH capture, so supply the
        # one the Bash/Zsh templates perform when sourced.
        guard = (
            f"if not ({json.dumps(executable, ensure_ascii=False)} | path exists) {{ return }}\n"
            'if "__MISE_ORIG_PATH" not-in $env { '
            "$env.__MISE_ORIG_PATH = ($env.PATH | str join (char esep)) }\n"
        )
    else:
        guard = f"if [ ! -x {shlex.quote(executable)} ]; then return 1; fi\n"
    return guard + output


def inspect_plugin(spec: RuntimeSpec, home: Path) -> bool:
    """Inspect tracked state; never discard local edits to a generated clone."""
    assert spec.target is not None
    status_spec = replace(
        spec,
        command=(
            "git",
            "-C",
            str(spec.target),
            "status",
            "--porcelain=v1",
            "--untracked-files=no",
        ),
        environment=(*spec.environment, ("GIT_OPTIONAL_LOCKS", "0")),
    )
    status = _run_command(status_spec, home, capture_output=True)
    if status.returncode != 0:
        raise RuntimeError(_command_failure_reason(status))
    if status.stdout.strip():
        raise RuntimeError(
            f"plugin tracked files have local changes: {spec.target}; inspect them before refreshing"
        )
    return (
        _read_revision(spec, spec.target, home) == spec.revision
        and spec.entrypoint is not None
        and (spec.target / spec.entrypoint).is_file()
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
        # Presence suppresses Mise's generation-time PATH snapshot, which would
        # otherwise bake the generating process's PATH (for example a project's
        # tools under `mise run`) into every consuming shell. Each shell
        # captures PATH when sourced instead; see guarded_activation for Nu.
        environment["__MISE_ORIG_PATH"] = ""
    return environment


def _run_command(
    spec: RuntimeSpec,
    home: Path,
    *,
    capture_output: bool,
) -> subprocess.CompletedProcess[str]:
    generator = spec.name.startswith(("function.", "completion."))
    return run_process_group(
        spec.command,
        cwd=home,
        capture_output=True,
        output_limit_chars=None if generator else 8192,
        inherit_output=not capture_output,
        timeout_seconds=spec.timeout_seconds,
        env=_command_environment(spec, home),
        on_progress=lambda elapsed: print(
            f"[{spec.name}] STILL RUNNING elapsed={int(elapsed)}s",
            file=sys.stderr,
            flush=True,
        ),
        progress_interval_seconds=30,
    )


def _timeout_reason(spec: RuntimeSpec, error: subprocess.TimeoutExpired) -> str:
    reason = f"timed out after {spec.timeout_seconds}s"
    detail = error.stderr
    if isinstance(detail, bytes):
        detail = detail.decode(errors="replace")
    return (
        f"{reason}: {detail[-8192:].strip()}" if detail and detail.strip() else reason
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
    if spec.entrypoint is not None and not (directory / spec.entrypoint).is_file():
        raise RuntimeError(
            f"pinned plugin entrypoint is missing: {directory / spec.entrypoint}"
        )


def _download(source: str, timeout_seconds: int) -> bytes:
    request = urllib.request.Request(source, headers={"User-Agent": "dotfiles-runtime"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return cast("bytes", response.read())
