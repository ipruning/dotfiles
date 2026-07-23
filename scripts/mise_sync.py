"""Converge this host on the repository's locked global mise declaration."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .diff import DriftProtocolError, MackupCommandError
from .mise import (
    canonical_mise_environment,
    canonical_mise_executable,
    canonical_mise_path,
)
from .render import emit_error
from .restore import (
    RestoreReport,
    RestoreStatus,
    apply_restore,
    plan_restore,
)


class MiseSyncStatus(StrEnum):
    PLANNED = "planned"
    SKIPPED = "skipped"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class MiseSyncStep:
    name: str
    command: tuple[str, ...]
    timeout_seconds: int
    path_prepend: tuple[Path, ...]


@dataclass(frozen=True)
class MiseSyncResult:
    step: MiseSyncStep
    status: MiseSyncStatus
    exit_code: int | None = None
    duration_ms: int | None = None
    reason: str | None = None


@dataclass(frozen=True)
class MiseSyncReport:
    apply: bool
    restore: RestoreReport
    results: tuple[MiseSyncResult, ...]
    live_only_tools: tuple[str, ...] = ()
    configuration_error: str | None = None

    @property
    def ok(self) -> bool:
        return (
            self.restore.ok
            and not self.live_only_tools
            and self.configuration_error is None
            and all(
                result.status is not MiseSyncStatus.FAILED for result in self.results
            )
        )


def _tool_names(config_path: Path, *, required: bool) -> frozenset[str]:
    try:
        with config_path.open("rb") as config_file:
            document = tomllib.load(config_file)
    except FileNotFoundError:
        if required:
            raise ValueError(f"{config_path} is missing") from None
        return frozenset()
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"{config_path} cannot be read as TOML: {error}") from error
    tools = document.get("tools", {})
    if not isinstance(tools, dict):
        raise ValueError(f"{config_path} [tools] must be a table")
    aliases = document.get("tool_alias", {})
    if not isinstance(aliases, dict):
        raise ValueError(f"{config_path} [tool_alias] must be a table")
    names: set[str] = set()
    for tool in tools:
        if not isinstance(tool, str):
            raise ValueError(f"{config_path} [tools] keys must be strings")
        names.add(tool)
    for alias, backend in aliases.items():
        if not isinstance(alias, str) or not isinstance(backend, str):
            raise ValueError(
                f"{config_path} [tool_alias] entries must map strings to strings"
            )
        if backend in tools:
            names.add(alias)
    return frozenset(names)


def _mise_tool_safety(
    repo_root: Path, home: Path
) -> tuple[tuple[str, ...], str | None]:
    reference_config = repo_root / "reference/.config/mise/config.toml"
    live_config = home / ".config/mise/config.toml"
    try:
        reference_tools = _tool_names(reference_config, required=True)
        live_tools = _tool_names(live_config, required=False)
    except ValueError as error:
        return (), str(error)
    return tuple(sorted(live_tools - reference_tools)), None


def _sync_steps(home: Path) -> tuple[MiseSyncStep, ...]:
    executable = str(canonical_mise_path(home))
    path_prepend = (canonical_mise_path(home).parent,)
    return (
        MiseSyncStep(
            "mise.tools",
            (executable, "install", "--locked", "--yes", "-C", str(home)),
            3600,
            path_prepend,
        ),
        MiseSyncStep(
            "mise.shims",
            (executable, "reshim", "-C", str(home)),
            120,
            path_prepend,
        ),
    )


def plan_mise_sync(repo_root: Path, home: Path) -> MiseSyncReport:
    """Return the configuration changes and locked commands without applying them."""
    restore = plan_restore(repo_root, home, "mise")
    live_only_tools, configuration_error = _mise_tool_safety(repo_root, home)
    steps = _sync_steps(home)
    if not restore.ok:
        reason = "mise configuration restore is not safe to apply"
        results = tuple(
            MiseSyncResult(step, MiseSyncStatus.SKIPPED, reason=reason)
            for step in steps
        )
    elif configuration_error:
        results = tuple(
            MiseSyncResult(
                step,
                MiseSyncStatus.SKIPPED,
                reason="mise tool ownership cannot be inspected safely",
            )
            for step in steps
        )
    elif live_only_tools:
        results = tuple(
            MiseSyncResult(
                step,
                MiseSyncStatus.SKIPPED,
                reason="live global tools are absent from the shared declaration",
            )
            for step in steps
        )
    elif canonical_mise_executable(home) is None:
        reason = f"{canonical_mise_path(home)} is missing, symlinked, or not executable"
        results = (
            MiseSyncResult(steps[0], MiseSyncStatus.FAILED, reason=reason),
            MiseSyncResult(
                steps[1],
                MiseSyncStatus.SKIPPED,
                reason="canonical mise is unavailable",
            ),
        )
    else:
        results = tuple(MiseSyncResult(step, MiseSyncStatus.PLANNED) for step in steps)
    return MiseSyncReport(
        apply=False,
        restore=restore,
        results=results,
        live_only_tools=live_only_tools,
        configuration_error=configuration_error,
    )


def _emit_output(step: MiseSyncStep, output: str) -> None:
    for line in output.splitlines():
        print(f"[{step.name}] {line}", file=sys.stderr)


def execute_mise_sync(
    repo_root: Path,
    home: Path,
    *,
    capture_output: bool = False,
) -> MiseSyncReport:
    """Restore the shared declaration, install it locked, and rebuild owned shims."""
    plan = plan_mise_sync(repo_root, home)
    if not plan.ok:
        return MiseSyncReport(
            apply=True,
            restore=plan.restore,
            results=plan.results,
            live_only_tools=plan.live_only_tools,
            configuration_error=plan.configuration_error,
        )
    restore = apply_restore(repo_root, home, plan.restore)
    if not restore.ok:
        results = tuple(
            MiseSyncResult(
                result.step,
                MiseSyncStatus.SKIPPED,
                reason="mise configuration restore failed",
            )
            for result in plan.results
        )
        return MiseSyncReport(
            apply=True,
            restore=restore,
            results=results,
            live_only_tools=plan.live_only_tools,
            configuration_error=plan.configuration_error,
        )

    results: list[MiseSyncResult] = []
    for planned in plan.results:
        started_at = time.monotonic()
        try:
            completed = subprocess.run(
                planned.step.command,
                check=False,
                stdin=subprocess.DEVNULL,
                capture_output=capture_output,
                env=canonical_mise_environment(home),
                text=True,
                timeout=planned.step.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            reason = f"timed out after {planned.step.timeout_seconds}s"
            results.append(
                MiseSyncResult(
                    planned.step,
                    MiseSyncStatus.FAILED,
                    duration_ms=round((time.monotonic() - started_at) * 1000),
                    reason=reason,
                ),
            )
            continue
        except OSError as error:
            results.append(
                MiseSyncResult(
                    planned.step,
                    MiseSyncStatus.FAILED,
                    duration_ms=round((time.monotonic() - started_at) * 1000),
                    reason=str(error),
                ),
            )
            continue
        if capture_output:
            if completed.stdout:
                _emit_output(planned.step, completed.stdout)
            if completed.stderr:
                _emit_output(planned.step, completed.stderr)
        results.append(
            MiseSyncResult(
                planned.step,
                (
                    MiseSyncStatus.SUCCEEDED
                    if completed.returncode == 0
                    else MiseSyncStatus.FAILED
                ),
                exit_code=completed.returncode,
                duration_ms=round((time.monotonic() - started_at) * 1000),
                reason=(
                    None
                    if completed.returncode == 0
                    else f"command exited {completed.returncode}"
                ),
            ),
        )
    return MiseSyncReport(
        apply=True,
        restore=restore,
        results=tuple(results),
        live_only_tools=plan.live_only_tools,
        configuration_error=plan.configuration_error,
    )


def _summary(report: MiseSyncReport) -> dict[str, int]:
    labels = [result.status.value for result in report.restore.results]
    labels.extend(result.status.value for result in report.results)
    return {
        status: labels.count(status)
        for status in (
            "planned",
            "applied",
            "succeeded",
            "skipped",
            "failed",
        )
        if status in labels
    }


def _next_commands(report: MiseSyncReport) -> tuple[str, ...]:
    if not report.apply and report.ok:
        return ("mise run mise-sync -- --apply",)
    if report.apply and report.ok:
        return ("mise run check", "mise run diff")
    return ()


def _document(report: MiseSyncReport) -> dict[str, object]:
    return {
        "schema_version": 1,
        "operation": "mise-sync",
        "apply": report.apply,
        "ok": report.ok,
        "safety": {
            "apply_blocked": bool(report.live_only_tools or report.configuration_error),
            "configuration_error": report.configuration_error,
            "live_only_tools": list(report.live_only_tools),
        },
        "changes": [
            {
                "reference_path": str(result.drift.reference_path),
                "live_path": str(result.drift.live_path),
                "kind": result.drift.kind.value,
                "action": result.action,
                "status": result.status.value,
                "backup_path": (
                    str(result.backup_path) if result.backup_path else None
                ),
                "error": result.error,
            }
            for result in report.restore.results
        ],
        "steps": [
            {
                "name": result.step.name,
                "command": list(result.step.command),
                "environment": {
                    "PATH_prepend": [
                        str(directory) for directory in result.step.path_prepend
                    ],
                },
                "status": result.status.value,
                "exit_code": result.exit_code,
                "duration_ms": result.duration_ms,
                "reason": result.reason,
            }
            for result in report.results
        ],
        "summary": _summary(report),
        "next": list(_next_commands(report)),
    }


def _display_command(step: MiseSyncStep) -> str:
    path = ":".join(str(directory) for directory in step.path_prepend)
    return f"PATH={path}:$PATH {' '.join(step.command)}"


def _render(report: MiseSyncReport) -> None:
    if report.configuration_error:
        print(
            f"BLOCKED   mise ownership inspection: {report.configuration_error}",
            file=sys.stderr,
        )
    if report.live_only_tools:
        print(
            "BLOCKED   live-only global mise tools: "
            + ", ".join(report.live_only_tools),
            file=sys.stderr,
        )
        print(
            "          Move project/service tools to their owner, add genuinely shared "
            "tools to reference, or remove them explicitly; then preview again.",
            file=sys.stderr,
        )
    for result in report.restore.results:
        stream = sys.stderr if result.status is RestoreStatus.FAILED else sys.stdout
        print(
            f"{result.status.value.upper():9} config {result.drift.live_path}",
            file=stream,
        )
        if result.backup_path:
            print(f"          backup: {result.backup_path}", file=stream)
        if result.error:
            print(f"          reason: {result.error}", file=stream)
    for result in report.results:
        label = result.status.value.upper()
        detail = (
            _display_command(result.step)
            if result.status is MiseSyncStatus.PLANNED
            else result.reason
        )
        stream = sys.stderr if result.status is MiseSyncStatus.FAILED else sys.stdout
        print(
            f"{label:9} {result.step.name}{f': {detail}' if detail else ''}",
            file=stream,
        )
    summary = _summary(report)
    rendered = ", ".join(f"{count} {status}" for status, count in summary.items())
    print(f"Summary: {rendered or 'no changes'}")
    if not report.apply and report.ok:
        print(
            "No files changed and no commands ran. Re-run with --apply to converge mise."
        )
    if next_commands := _next_commands(report):
        print("Next:")
        for command in next_commands:
            print(f"  {command}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Converge global mise configuration, locked tools, and shims.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="back up and link configuration, install locked tools, and reshim",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit the report as JSON on stdout",
    )
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    try:
        report = (
            execute_mise_sync(repo_root, Path.home(), capture_output=args.as_json)
            if args.apply
            else plan_mise_sync(repo_root, Path.home())
        )
    except (DriftProtocolError, MackupCommandError) as error:
        emit_error("mise-sync", str(error), as_json=args.as_json, apply=args.apply)
        return 1
    if args.as_json:
        print(json.dumps(_document(report), indent=2, sort_keys=True))
        if report.configuration_error:
            print(
                f"[mise.safety] FAIL {report.configuration_error}",
                file=sys.stderr,
            )
        if report.live_only_tools:
            print(
                "[mise.safety] FAIL live-only global tools: "
                + ", ".join(report.live_only_tools),
                file=sys.stderr,
            )
        for result in report.restore.results:
            if result.status is RestoreStatus.FAILED:
                print(
                    f"[mise.config] FAIL {result.drift.live_path}: {result.error}",
                    file=sys.stderr,
                )
        for result in report.results:
            if result.status is MiseSyncStatus.FAILED:
                print(
                    f"[{result.step.name}] FAIL {result.reason}",
                    file=sys.stderr,
                )
    else:
        _render(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
