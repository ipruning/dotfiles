"""Update installed host tools with explicit preview and apply modes."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import cast

from .host_policy import (
    HostPolicyError,
    configured_mise_path,
    mutation_allowed,
    require_mutation_allowed,
)
from .mise import (
    canonical_mise_environment,
    canonical_mise_executable,
    canonical_mise_path,
)
from .models import ExecutableFinder
from .process import run_process_group
from .render import emit_error

StepCallback = Callable[["UpdateStep"], None]
NEXT_COMMANDS = ("mise run check",)
MISE_TOOLS_NOTE = (
    "mise.tools consumes the shared lock without changing declarations; "
    "use upgrade-tools explicitly to advance the shared baseline."
)
PREVIEW_NOTE = (
    "planned means the updater command is available; each updater determines "
    "whether an update exists during apply."
)
MISE_REF_PREFIXES = ("branch:", "ref:", "rev:", "tag:")
PROGRESS_INTERVAL_SECONDS = 30


class UpdateStatus(StrEnum):
    PLANNED = "planned"
    SKIPPED = "skipped"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class UpdateStep:
    name: str
    tool: str
    command: tuple[str, ...]
    timeout_seconds: int
    path_prepend: tuple[Path, ...] = ()
    environment: tuple[tuple[str, str], ...] = ()
    stdin_text: str | None = None
    failure_note: str | None = None
    cwd: Path | None = None


@dataclass(frozen=True)
class UpdateResult:
    step: UpdateStep
    status: UpdateStatus
    exit_code: int | None = None
    duration_ms: int | None = None
    reason: str | None = None
    stdout_tail: str | None = None
    stderr_tail: str | None = None


@dataclass(frozen=True)
class UpdateReport:
    apply: bool
    results: tuple[UpdateResult, ...]
    runtime: dict[str, object] | None = None

    @property
    def ok(self) -> bool:
        return all(
            result.status is not UpdateStatus.FAILED for result in self.results
        ) and (self.runtime is None or bool(self.runtime["ok"]))


def _emit_failure(step: UpdateStep, reason: str) -> None:
    print(f"[{step.name}] FAIL {reason}", file=sys.stderr)


def _failure_reason(step: UpdateStep, reason: str) -> str:
    return f"{reason}; {step.failure_note}" if step.failure_note else reason


def _run_with_progress(
    step: UpdateStep,
    *,
    env: dict[str, str] | None,
    progress_interval_seconds: float,
    inherit_output: bool = False,
    announce_start: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run an updater with progress and a process-group timeout."""
    if announce_start:
        print(
            f"[{step.name}] RUN {_display_command(step)}", file=sys.stderr, flush=True
        )

    def progress(elapsed: float) -> None:
        print(
            f"[{step.name}] STILL RUNNING elapsed={round(elapsed)}s "
            f"timeout={step.timeout_seconds}s",
            file=sys.stderr,
            flush=True,
        )

    started_at = time.monotonic()
    completed = run_process_group(
        step.command,
        env=env,
        cwd=step.cwd,
        timeout_seconds=step.timeout_seconds,
        capture_output=True,
        output_limit_chars=8192,
        inherit_output=inherit_output,
        stdin_text=step.stdin_text,
        on_progress=progress,
        progress_interval_seconds=progress_interval_seconds,
    )
    print(
        f"[{step.name}] DONE exit={completed.returncode} "
        f"elapsed={round(time.monotonic() - started_at)}s",
        file=sys.stderr,
        flush=True,
    )
    return completed


def _installed_mise_tools(home: Path, mise_executable: str) -> tuple[str, ...]:
    """Return installed identities, including versions older than the current lock."""
    command = (
        mise_executable,
        "ls",
        "--installed",
        "--json",
        "-C",
        str(home),
    )
    try:
        completed = run_process_group(
            command,
            env=canonical_mise_environment(home),
            timeout_seconds=120,
            capture_output=True,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("mise tool inventory timed out after 120s") from error
    except OSError as error:
        raise RuntimeError(
            f"could not inspect installed mise tools: {error}"
        ) from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        reason = f"mise tool inventory exited {completed.returncode}"
        raise RuntimeError(f"{reason}: {detail}" if detail else reason)
    try:
        document = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"mise tool inventory returned invalid JSON: {error}"
        ) from error
    if not isinstance(document, dict):
        raise RuntimeError("mise tool inventory must be a JSON object")

    installed: list[str] = []
    for name, raw_versions in document.items():
        if not isinstance(name, str) or not isinstance(raw_versions, list):
            raise RuntimeError("mise tool inventory has an invalid tool entry")
        for raw_version in raw_versions:
            if not isinstance(raw_version, dict):
                raise RuntimeError(f"mise tool inventory for {name} is invalid")
            version = raw_version.get("version")
            if not isinstance(version, str) or not version:
                raise RuntimeError(f"mise tool inventory for {name} has no version")
            installed.append(name)
    return tuple(sorted(set(installed)))


def inspect_shared_mise_tools(
    repo_root: Path, home: Path, executable: str
) -> tuple[tuple[str, ...], dict[str, object]]:
    """核对共享声明的唯一归属，返回已安装工具名称与原始版本请求。"""
    from .mise_sync import _loaded_global_configs, _same_config_file, _tool_declaration

    reference = repo_root / "reference/.config/mise/config.toml"
    live = home / ".config/mise/config.toml"
    installed_names = set(_installed_mise_tools(home, executable))
    extra_configs = tuple(
        str(path)
        for path in _loaded_global_configs(home, executable)
        if not _same_config_file(path, live)
    )
    if extra_configs:
        raise RuntimeError(
            "shared mise declaration is not the sole live owner; "
            "preview `mise run mise-sync` before updating: " + ", ".join(extra_configs)
        )
    with reference.open("rb") as stream:
        reference_document = tomllib.load(stream)
    with live.open("rb") as stream:
        live_document = tomllib.load(stream)
    if any(
        reference_document.get(section) != live_document.get(section)
        for section in ("tools", "tool_alias", "alias")
    ):
        raise RuntimeError(
            "live mise versions or options differ from reference; preview mise-sync"
        )
    shared, aliases = _tool_declaration(
        reference, required=True, document=reference_document
    )
    with reference.with_name("mise.lock").open("rb") as stream:
        reference_lock = tomllib.load(stream)
    with live.with_name("mise.lock").open("rb") as stream:
        live_lock = tomllib.load(stream)
    if reference_lock != live_lock:
        raise RuntimeError("live mise lock differs from reference; preview mise-sync")
    installed = tuple(
        sorted(
            name
            for name in shared
            if name in installed_names or aliases.get(name) in installed_names
        )
    )
    return installed, cast(dict[str, object], reference_document.get("tools", {}))


def _update_steps(home: Path) -> tuple[UpdateStep, ...]:
    mise_executable = str(canonical_mise_path(home))
    mise_path = (canonical_mise_path(home).parent,)
    return (
        UpdateStep("brew.metadata", "brew", ("brew", "update"), 900),
        # Package-mutating steps get transaction-scale timeouts: killing brew or
        # mise mid-upgrade leaves partial kegs, stale locks, or half-written
        # tool state, which is worse than waiting out a slow upgrade.
        UpdateStep(
            "brew.packages",
            "brew",
            ("brew", "upgrade", "--formula"),
            3600,
            environment=(("HOMEBREW_NO_INSTALL_CLEANUP", "1"),),
        ),
        UpdateStep(
            "mise.self",
            "mise",
            (mise_executable, "self-update", "--yes", "--no-plugins"),
            900,
            path_prepend=mise_path,
        ),
        UpdateStep(
            "mise.tools",
            "mise",
            (mise_executable, "install", "--locked", "--yes", "-C", str(home)),
            1800,
            path_prepend=mise_path,
        ),
        UpdateStep(
            "mise.shims",
            "mise",
            (mise_executable, "reshim", "-C", str(home)),
            120,
            path_prepend=mise_path,
        ),
        UpdateStep(
            "gh.extensions",
            "gh",
            ("gh", "extension", "upgrade", "--all"),
            300,
        ),
        UpdateStep("tldr.pages", "tldr", ("tldr", "--update"), 300),
        UpdateStep("yazi.packages", "ya", ("ya", "pkg", "upgrade"), 300),
        UpdateStep(
            "sprite.version",
            "sprite",
            ("sprite", "upgrade"),
            300,
            # `sprite upgrade` treats a declined/closed prompt as exit 0. An
            # explicit update --apply is the operator's confirmation, so feed
            # the affirmative response instead of reporting a no-op as success.
            stdin_text="y\n",
        ),
        UpdateStep("amp", "amp", ("amp", "update"), 300),
        UpdateStep(
            "claude",
            "claude",
            ("claude", "update"),
            # Let Claude's updater own its download deadline and report its
            # actual error instead of killing a valid slow download at 5m.
            1800,
            failure_note=(
                "retry `claude update`; failed downloads may remain under "
                f"{home}/.cache/claude/staging and "
                f"{home}/.local/share/claude/versions and are not cleaned "
                "automatically"
            ),
        ),
        UpdateStep("tigris", "tigris", ("tigris", "update"), 300),
        UpdateStep("herdr", "herdr", ("herdr", "update"), 900),
        UpdateStep("pi", "pi", ("pi", "update"), 1800),
        UpdateStep(
            "pi.extensions",
            "pi",
            ("pi", "update", "--extensions"),
            300,
        ),
    )


def plan_updates(
    home: Path,
    *,
    executable_finder: ExecutableFinder = shutil.which,
    repo_root: Path | None = None,
) -> UpdateReport:
    """Return the exact available update plan without running commands."""
    results = []
    mise_executable = canonical_mise_executable(home)
    for step in _update_steps(home):
        step = replace(step, cwd=home)
        if step.name == "mise.self" and configured_mise_path(home) is not None:
            results.append(
                UpdateResult(
                    step=step,
                    status=UpdateStatus.SKIPPED,
                    reason="host-selected mise is updated by its host owner",
                ),
            )
            continue
        resolved = (
            executable_finder(step.tool) if step.tool != "mise" else mise_executable
        )
        if resolved and step.tool in {
            "amp",
            "claude",
            "pi",
            "tigris",
            "sprite",
            "herdr",
        }:
            path = Path(resolved)
            target = path.resolve()
            mise_root = home / ".local/share/mise"
            manager_owned = (
                target.is_relative_to(mise_root)
                or path.is_relative_to(mise_root)
                or target.is_relative_to(Path("/opt/homebrew"))
                or "Cellar" in target.parts
                or target.is_relative_to(Path("/usr/bin"))
            )
            native_roots = {
                "amp": (home / ".amp/bin",),
                "claude": (home / ".local/share/claude/versions",),
                "pi": (home / ".pi/agent/install", home / ".pi/agent/bin"),
                "tigris": (home / ".local/bin",),
                "sprite": (home / ".local/bin",),
                "herdr": (home / ".local/bin",),
            }
            native = any(
                target.is_relative_to(root) for root in native_roots[step.tool]
            )
            if step.tool == "herdr":
                native = target == home.resolve() / ".local/bin/herdr"
            if not manager_owned and not native:
                results.append(
                    UpdateResult(
                        step,
                        UpdateStatus.SKIPPED,
                        reason=f"{path} has no verified native owner; inspect its installation before self-update",
                    )
                )
                continue
            if manager_owned:
                results.append(
                    UpdateResult(
                        step,
                        UpdateStatus.SKIPPED,
                        reason=f"{path} is package-manager owned; native self-update is skipped",
                    )
                )
                continue
            step = replace(step, command=(str(path), *step.command[1:]))
        available = (
            mise_executable is not None
            if step.tool == "mise"
            else executable_finder(step.tool) is not None
        )
        if available and step.name == "mise.tools":
            assert mise_executable is not None
            try:
                installed, _declaration = inspect_shared_mise_tools(
                    repo_root or Path(__file__).resolve().parents[1],
                    home,
                    mise_executable,
                )
            except (RuntimeError, OSError, ValueError) as error:
                results.append(
                    UpdateResult(
                        step=step,
                        status=UpdateStatus.FAILED
                        if mutation_allowed(home)
                        else UpdateStatus.SKIPPED,
                        reason=str(error),
                    ),
                )
                continue
            if not installed:
                results.append(
                    UpdateResult(
                        step=step,
                        status=UpdateStatus.SKIPPED,
                        reason="no active mise tools are installed",
                    ),
                )
                continue
            step = replace(step, command=(*step.command, *installed))
        results.append(
            UpdateResult(
                step=step,
                status=UpdateStatus.PLANNED if available else UpdateStatus.SKIPPED,
                reason=(
                    None
                    if available
                    else (
                        f"{canonical_mise_path(home)} is missing, broken, or not executable"
                        if step.tool == "mise"
                        else f"{step.tool} is not available on PATH"
                    )
                ),
            ),
        )
    return UpdateReport(apply=False, results=tuple(results))


def execute_updates(
    home: Path,
    *,
    executable_finder: ExecutableFinder = shutil.which,
    capture_output: bool = False,
    on_start: StepCallback | None = None,
    progress_interval_seconds: float = PROGRESS_INTERVAL_SECONDS,
    repo_root: Path | None = None,
) -> UpdateReport:
    """Run every available updater and retain independent failure results."""
    require_mutation_allowed(home)
    plan = plan_updates(home, executable_finder=executable_finder, repo_root=repo_root)
    if not plan.ok:
        return UpdateReport(
            True,
            tuple(
                replace(
                    result,
                    status=UpdateStatus.SKIPPED,
                    reason="ownership preflight failed; no updater commands run",
                )
                if result.status is UpdateStatus.PLANNED
                else result
                for result in plan.results
            ),
        )
    results = []
    for planned in plan.results:
        # Carry through anything the preflight already resolved (SKIPPED, or a
        # FAILED mise inventory). Only PLANNED steps run: executing a FAILED
        # mise.tools step would run `mise upgrade` with no tool arguments and
        # upgrade every installed tool — the exact outcome the preflight avoids.
        if planned.status is not UpdateStatus.PLANNED:
            results.append(planned)
            continue
        if on_start:
            on_start(planned.step)
        started_at = time.monotonic()
        try:
            environment = None
            if planned.step.path_prepend:
                environment = canonical_mise_environment(home)
            elif planned.step.environment:
                environment = os.environ.copy()
            if environment is not None:
                environment.update(planned.step.environment)
            completed = _run_with_progress(
                planned.step,
                env=environment,
                progress_interval_seconds=progress_interval_seconds,
                inherit_output=not capture_output,
                announce_start=on_start is None,
            )
        except subprocess.TimeoutExpired as error:
            reason = _failure_reason(
                planned.step,
                f"timed out after {planned.step.timeout_seconds}s",
            )
            if capture_output:
                _emit_failure(planned.step, reason)
            results.append(
                UpdateResult(
                    step=planned.step,
                    status=UpdateStatus.FAILED,
                    duration_ms=round((time.monotonic() - started_at) * 1000),
                    reason=reason,
                    stdout_tail=error.output if isinstance(error.output, str) else None,
                    stderr_tail=error.stderr if isinstance(error.stderr, str) else None,
                ),
            )
            continue
        except OSError as error:
            reason = _failure_reason(planned.step, str(error))
            if capture_output:
                _emit_failure(planned.step, reason)
            results.append(
                UpdateResult(
                    step=planned.step,
                    status=UpdateStatus.FAILED,
                    duration_ms=round((time.monotonic() - started_at) * 1000),
                    reason=reason,
                ),
            )
            continue
        failure_reason = _failure_reason(
            planned.step,
            f"command exited {completed.returncode}",
        )
        if capture_output and completed.returncode != 0:
            _emit_failure(
                planned.step,
                failure_reason,
            )
        results.append(
            UpdateResult(
                step=planned.step,
                status=(
                    UpdateStatus.SUCCEEDED
                    if completed.returncode == 0
                    else UpdateStatus.FAILED
                ),
                exit_code=completed.returncode,
                duration_ms=round((time.monotonic() - started_at) * 1000),
                reason=(None if completed.returncode == 0 else failure_reason),
                stdout_tail=completed.stdout or None,
                stderr_tail=completed.stderr or None,
            ),
        )
    return UpdateReport(apply=True, results=tuple(results))


def _summary(report: UpdateReport) -> dict[str, int]:
    return {
        status.value: count
        for status in (
            UpdateStatus.PLANNED,
            UpdateStatus.SUCCEEDED,
            UpdateStatus.SKIPPED,
            UpdateStatus.FAILED,
        )
        if (count := sum(result.status is status for result in report.results))
    }


def _next_commands(
    report: UpdateReport,
    *,
    apply_allowed: bool = True,
) -> tuple[str, ...]:
    if not report.apply:
        return (
            ("mise run update -- --apply",)
            if apply_allowed
            and any(result.status is UpdateStatus.PLANNED for result in report.results)
            else ()
        )
    if not any(result.status is UpdateStatus.SUCCEEDED for result in report.results):
        return ()
    return NEXT_COMMANDS


def _notes(report: UpdateReport) -> tuple[str, ...]:
    notes = []
    if not report.apply:
        notes.append(PREVIEW_NOTE)
    if any(
        result.step.name == "mise.tools" and result.status is not UpdateStatus.SKIPPED
        for result in report.results
    ):
        notes.append(MISE_TOOLS_NOTE)
    return tuple(notes)


def _document(
    report: UpdateReport,
    *,
    apply_allowed: bool = True,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "operation": "update",
        "apply": report.apply,
        "ok": report.ok,
        "steps": [
            {
                "name": result.step.name,
                "tool": result.step.tool,
                "command": list(result.step.command),
                "environment": {
                    "PATH_prepend": [
                        str(directory) for directory in result.step.path_prepend
                    ],
                    "variables": dict(result.step.environment),
                },
                "stdin": result.step.stdin_text,
                "cwd": str(result.step.cwd) if result.step.cwd else None,
                "attention": None,
                "status": result.status.value,
                "exit_code": result.exit_code,
                "duration_ms": result.duration_ms,
                "reason": result.reason,
                "stdout_tail": result.stdout_tail,
                "stderr_tail": result.stderr_tail,
                "retry": _display_command(result.step)
                if result.status is UpdateStatus.FAILED
                else None,
            }
            for result in report.results
        ],
        "runtime": report.runtime,
        "summary": _summary(report),
        "notes": list(_notes(report)),
        "next": list(_next_commands(report, apply_allowed=apply_allowed)),
    }


def _display_command(step: UpdateStep) -> str:
    command = shlex.join(step.command)
    prefixes = []
    if step.path_prepend:
        path = ":".join(str(directory) for directory in step.path_prepend)
        prefixes.append(f'PATH={shlex.quote(path)}:"$PATH"')
    prefixes.extend(f"{key}={shlex.quote(value)}" for key, value in step.environment)
    command = " ".join((*prefixes, command))
    if step.stdin_text is not None:
        command = f"printf '%s' {shlex.quote(step.stdin_text)} | {command}"
    if step.cwd is not None:
        command = f"cd -- {shlex.quote(str(step.cwd))} && {command}"
    return command


def _render(report: UpdateReport, *, apply_allowed: bool = True) -> None:
    def duration(result: UpdateResult) -> str:
        return (
            f" ({result.duration_ms / 1000:.1f}s)"
            if result.duration_ms is not None
            else ""
        )

    for result in report.results:
        label = result.status.value.upper()
        if result.status is UpdateStatus.PLANNED:
            print(f"{label:7} {result.step.name}: {_display_command(result.step)}")
        elif result.status is UpdateStatus.SUCCEEDED:
            print(f"{label:7} {result.step.name}{duration(result)}")
        elif result.status is UpdateStatus.SKIPPED:
            print(f"{label:7} {result.step.name}: {result.reason}")
        else:
            print(
                f"{label:7} {result.step.name}{duration(result)}: {result.reason}",
                file=sys.stderr,
            )
            for output in (result.stdout_tail, result.stderr_tail):
                if output:
                    print(output.rstrip(), file=sys.stderr)
            print(f"Retry: {_display_command(result.step)}", file=sys.stderr)
    summary = _summary(report)
    rendered = ", ".join(f"{count} {status}" for status, count in summary.items())
    print(f"Summary: {rendered or 'no steps'}")
    for note in _notes(report):
        print(f"Note: {note}")
    if not report.apply:
        if not apply_allowed and any(
            result.status is UpdateStatus.PLANNED for result in report.results
        ):
            print("No commands run. Host policy disables update apply.")
        elif _next_commands(report):
            print("No commands run. Re-run with --apply to update host tools.")
        else:
            print("No update commands are available on this host.")
        return
    if not report.ok:
        print(
            "Update incomplete. Resolve the reported failures; runtime has its own result."
        )
    if report.runtime is not None:
        print(f"Runtime: {'SUCCEEDED' if report.runtime['ok'] else 'FAILED'}")
    next_commands = _next_commands(report)
    if not next_commands:
        if report.ok:
            print("No update commands ran.")
        return
    print("Next:")
    for command in next_commands:
        print(f"  {command}")


def _announce_step(step: UpdateStep) -> None:
    print(f"RUN {step.name}: {_display_command(step)}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Update installed tools with explicit preview and apply modes.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="run the available updaters (default: preview only)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit the report as JSON on stdout",
    )
    args = parser.parse_args(argv)
    home = Path.home()
    try:
        apply_allowed = mutation_allowed(home)
        report = (
            execute_updates(
                home,
                capture_output=args.as_json,
                on_start=None if args.as_json else _announce_step,
            )
            if args.apply
            else plan_updates(home)
        )
        safety_failed = any(
            result.step.name == "mise.tools"
            and result.status is UpdateStatus.FAILED
            and result.exit_code is None
            for result in report.results
        )
        if args.apply and safety_failed:
            report = replace(
                report,
                runtime={
                    "ok": False,
                    "apply": False,
                    "status": "skipped",
                    "reason": "mise ownership preflight failed; resolve before refreshing runtime",
                },
            )
        elif args.apply:
            from .runtime import _document as runtime_document
            from .runtime import execute_runtime, plan_runtime

            runtime = execute_runtime(
                plan_runtime(Path(__file__).resolve().parents[1], home, network=False),
                home,
                capture_output=True,
            )
            report = replace(report, runtime=runtime_document(runtime))

    except HostPolicyError as error:
        emit_error(
            "update",
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
    else:
        _render(report, apply_allowed=apply_allowed)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
