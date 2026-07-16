"""Update installed host tools without synchronizing configuration."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .models import ExecutableFinder

StepCallback = Callable[["UpdateStep"], None]
NEXT_COMMANDS = (
    "mise run runtime",
    "mise run check",
    "mise run diff",
)


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


@dataclass(frozen=True)
class UpdateResult:
    step: UpdateStep
    status: UpdateStatus
    exit_code: int | None = None
    duration_ms: int | None = None
    reason: str | None = None


@dataclass(frozen=True)
class UpdateReport:
    apply: bool
    results: tuple[UpdateResult, ...]

    @property
    def ok(self) -> bool:
        return all(result.status is not UpdateStatus.FAILED for result in self.results)


def _emit_command_output(step: UpdateStep, output: str) -> None:
    for line in output.splitlines():
        print(f"[{step.name}] {line}", file=sys.stderr)


def _emit_failure(step: UpdateStep, reason: str) -> None:
    print(f"[{step.name}] FAIL {reason}", file=sys.stderr)


def _update_steps(home: Path) -> tuple[UpdateStep, ...]:
    return (
        UpdateStep("brew.metadata", "brew", ("brew", "update"), 900),
        # Package-mutating steps get transaction-scale timeouts: killing brew or
        # mise mid-upgrade leaves partial kegs, stale locks, or half-written
        # tool state, which is worse than waiting out a slow upgrade.
        UpdateStep("brew.packages", "brew", ("brew", "upgrade"), 3600),
        UpdateStep(
            "mise.tools",
            "mise",
            ("mise", "upgrade", "--bump", "-C", str(home)),
            1800,
        ),
        UpdateStep("mise.shims", "mise", ("mise", "reshim"), 120),
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
            ("sprite", "upgrade", "--check"),
            300,
        ),
        UpdateStep("amp", "amp", ("amp", "update"), 300),
        UpdateStep("tigris", "tigris", ("tigris", "update"), 300),
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
) -> UpdateReport:
    """Return the exact available update plan without running commands."""
    results = []
    for step in _update_steps(home):
        available = executable_finder(step.tool) is not None
        results.append(
            UpdateResult(
                step=step,
                status=UpdateStatus.PLANNED if available else UpdateStatus.SKIPPED,
                reason=None if available else f"{step.tool} is not available on PATH",
            ),
        )
    return UpdateReport(apply=False, results=tuple(results))


def execute_updates(
    home: Path,
    *,
    executable_finder: ExecutableFinder = shutil.which,
    capture_output: bool = False,
    on_start: StepCallback | None = None,
) -> UpdateReport:
    """Run every available updater and retain independent failure results."""
    results = []
    for planned in plan_updates(home, executable_finder=executable_finder).results:
        if planned.status is UpdateStatus.SKIPPED:
            results.append(planned)
            continue
        if on_start:
            on_start(planned.step)
        started_at = time.monotonic()
        try:
            completed = subprocess.run(
                planned.step.command,
                check=False,
                stdin=subprocess.DEVNULL,
                capture_output=capture_output,
                text=True,
                timeout=planned.step.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            reason = f"timed out after {planned.step.timeout_seconds}s"
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
        except OSError as error:
            reason = str(error)
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
        if capture_output:
            if completed.stdout:
                _emit_command_output(planned.step, completed.stdout)
            if completed.stderr:
                _emit_command_output(planned.step, completed.stderr)
            if completed.returncode != 0:
                _emit_failure(
                    planned.step,
                    f"command exited {completed.returncode}",
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
                reason=(
                    None
                    if completed.returncode == 0
                    else f"command exited {completed.returncode}"
                ),
            ),
        )
    return UpdateReport(apply=True, results=tuple(results))


def _document(report: UpdateReport) -> dict[str, object]:
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
                "status": result.status.value,
                "exit_code": result.exit_code,
                "duration_ms": result.duration_ms,
                "reason": result.reason,
            }
            for result in report.results
        ],
        "next": list(NEXT_COMMANDS),
    }


def _render(report: UpdateReport) -> None:
    for result in report.results:
        label = result.status.value.upper()
        if result.status is UpdateStatus.PLANNED:
            print(f"{label:7} {result.step.name}: {' '.join(result.step.command)}")
        elif result.status is UpdateStatus.SUCCEEDED:
            print(f"{label:7} {result.step.name}")
        elif result.status is UpdateStatus.SKIPPED:
            print(f"{label:7} {result.step.name}: {result.reason}")
        else:
            print(
                f"{label:7} {result.step.name}: {result.reason}",
                file=sys.stderr,
            )
    if not report.apply:
        print("No commands run. Re-run with --apply to update host tools.")
        return
    print("Next:")
    for command in NEXT_COMMANDS:
        print(f"  {command}")


def _announce_step(step: UpdateStep) -> None:
    print(f"RUN {step.name}: {' '.join(step.command)}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Update installed tools without synchronizing configuration.",
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
    report = (
        execute_updates(
            Path.home(),
            capture_output=args.as_json,
            on_start=None if args.as_json else _announce_step,
        )
        if args.apply
        else plan_updates(Path.home())
    )
    if args.as_json:
        print(json.dumps(_document(report), indent=2, sort_keys=True))
    else:
        _render(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
