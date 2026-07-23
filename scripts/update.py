"""Update installed host tools without synchronizing configuration."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

from .mise import canonical_mise_executable, canonical_mise_path
from .models import ExecutableFinder

StepCallback = Callable[["UpdateStep"], None]
NEXT_COMMANDS = ("mise run runtime",)


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


def _installed_mise_tools(home: Path, mise_executable: str) -> tuple[str, ...]:
    """Return active installed versions so upgrade cannot bootstrap missing tools."""
    command = (
        mise_executable,
        "ls",
        "--current",
        "--installed",
        "--json",
        "-C",
        str(home),
    )
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
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
            installed.append(f"{name}@{version}")
    return tuple(sorted(set(installed)))


def _update_steps(home: Path) -> tuple[UpdateStep, ...]:
    mise_executable = str(canonical_mise_path(home))
    return (
        UpdateStep("brew.metadata", "brew", ("brew", "update"), 900),
        # Package-mutating steps get transaction-scale timeouts: killing brew or
        # mise mid-upgrade leaves partial kegs, stale locks, or half-written
        # tool state, which is worse than waiting out a slow upgrade.
        UpdateStep("brew.packages", "brew", ("brew", "upgrade"), 3600),
        UpdateStep(
            "mise.self",
            "mise",
            (mise_executable, "self-update", "--yes", "--no-plugins"),
            900,
        ),
        UpdateStep(
            "mise.tools",
            "mise",
            (mise_executable, "upgrade", "--bump", "-C", str(home)),
            1800,
        ),
        UpdateStep("mise.shims", "mise", (mise_executable, "reshim"), 120),
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
        ),
        UpdateStep("amp", "amp", ("amp", "update"), 300),
        UpdateStep("claude", "claude", ("claude", "update"), 300),
        UpdateStep("codex", "codex", ("codex", "update"), 300),
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
    mise_executable = canonical_mise_executable(home)
    for step in _update_steps(home):
        available = (
            mise_executable is not None
            if step.tool == "mise"
            else executable_finder(step.tool) is not None
        )
        if available and step.name == "mise.tools":
            assert mise_executable is not None
            try:
                installed = _installed_mise_tools(home, mise_executable)
            except RuntimeError as error:
                results.append(
                    UpdateResult(
                        step=step,
                        status=UpdateStatus.FAILED,
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
                        f"{canonical_mise_path(home)} is missing, symlinked, or not executable"
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
) -> UpdateReport:
    """Run every available updater and retain independent failure results."""
    results = []
    for planned in plan_updates(home, executable_finder=executable_finder).results:
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


def _next_commands(report: UpdateReport) -> tuple[str, ...]:
    if not report.apply:
        return (
            ("mise run update -- --apply",)
            if any(result.status is UpdateStatus.PLANNED for result in report.results)
            else ()
        )
    if not report.ok or not any(
        result.status is UpdateStatus.SUCCEEDED for result in report.results
    ):
        return ()
    return NEXT_COMMANDS


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
        "summary": _summary(report),
        "next": list(_next_commands(report)),
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
    summary = _summary(report)
    rendered = ", ".join(f"{count} {status}" for status, count in summary.items())
    print(f"Summary: {rendered or 'no steps'}")
    if not report.apply:
        if _next_commands(report):
            print("No commands run. Re-run with --apply to update host tools.")
        else:
            print("No update commands are available on this host.")
        return
    if not report.ok:
        print("Update incomplete. Resolve failed steps before refreshing runtime.")
        return
    next_commands = _next_commands(report)
    if not next_commands:
        print("No update commands ran.")
        return
    print("Next:")
    for command in next_commands:
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
