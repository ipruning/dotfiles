"""Preview or explicitly execute safe host cleanup owned by package managers."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .host_policy import HostPolicyError, mutation_allowed, require_mutation_allowed
from .mise import canonical_mise_environment, canonical_mise_executable
from .render import emit_error


class CleanStatus(StrEnum):
    PREVIEWED = "previewed"
    SKIPPED = "skipped"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class CleanStep:
    name: str
    owner: str
    preview_command: tuple[str, ...]
    apply_command: tuple[str, ...]
    timeout_seconds: int
    environment: tuple[tuple[str, str], ...] = ()

    def command(self, *, apply: bool) -> tuple[str, ...]:
        return self.apply_command if apply else self.preview_command


@dataclass(frozen=True)
class CleanResult:
    step: CleanStep
    status: CleanStatus
    command: tuple[str, ...]
    exit_code: int | None = None
    duration_ms: int | None = None
    output: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class CleanReport:
    apply: bool
    results: tuple[CleanResult, ...]

    @property
    def ok(self) -> bool:
        return all(result.status is not CleanStatus.FAILED for result in self.results)


CommandRunner = Callable[
    [tuple[str, ...], dict[str, str], int],
    subprocess.CompletedProcess[str],
]


def _default_runner(
    command: tuple[str, ...],
    environment: dict[str, str],
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        text=True,
        timeout=timeout_seconds,
    )


def _steps(
    home: Path,
    *,
    executable_finder: Callable[[str], str | None],
) -> tuple[CleanStep, ...]:
    steps: list[CleanStep] = []
    mise = canonical_mise_executable(home)
    if mise:
        steps.append(
            CleanStep(
                "mise.prune",
                "mise",
                (mise, "prune", "--dry-run", "--tools"),
                (mise, "prune", "--yes", "--tools"),
                600,
            ),
        )
    brew = executable_finder("brew")
    if brew:
        environment = (("HOMEBREW_NO_AUTO_UPDATE", "1"),)
        steps.extend(
            (
                CleanStep(
                    "brew.autoremove",
                    "brew",
                    (brew, "autoremove", "--dry-run"),
                    (brew, "autoremove"),
                    1800,
                    environment,
                ),
                CleanStep(
                    "brew.cleanup",
                    "brew",
                    (brew, "cleanup", "--dry-run"),
                    (brew, "cleanup"),
                    1800,
                    environment,
                ),
            ),
        )
    return tuple(steps)


def _environment(home: Path, step: CleanStep) -> dict[str, str]:
    environment = (
        canonical_mise_environment(home) if step.owner == "mise" else os.environ.copy()
    )
    environment.update(step.environment)
    environment["HOME"] = str(home)
    return environment


def _output(completed: subprocess.CompletedProcess[str]) -> str | None:
    return (
        "\n".join(
            part.strip()
            for part in (completed.stdout, completed.stderr)
            if part.strip()
        )
        or None
    )


def _execute_step(
    step: CleanStep,
    home: Path,
    *,
    apply: bool,
    runner: CommandRunner,
) -> CleanResult:
    command = step.command(apply=apply)
    started_at = time.monotonic()
    try:
        completed = runner(command, _environment(home, step), step.timeout_seconds)
    except subprocess.TimeoutExpired:
        return CleanResult(
            step,
            CleanStatus.FAILED,
            command,
            duration_ms=round((time.monotonic() - started_at) * 1000),
            reason=f"timed out after {step.timeout_seconds}s",
        )
    except OSError as error:
        return CleanResult(
            step,
            CleanStatus.FAILED,
            command,
            duration_ms=round((time.monotonic() - started_at) * 1000),
            reason=str(error),
        )
    succeeded = completed.returncode == 0
    return CleanResult(
        step,
        CleanStatus.SUCCEEDED
        if apply and succeeded
        else (CleanStatus.PREVIEWED if not apply and succeeded else CleanStatus.FAILED),
        command,
        exit_code=completed.returncode,
        duration_ms=round((time.monotonic() - started_at) * 1000),
        output=_output(completed),
        reason=None if succeeded else f"command exited {completed.returncode}",
    )


def plan_clean(
    home: Path,
    *,
    executable_finder: Callable[[str], str | None] = shutil.which,
    runner: CommandRunner = _default_runner,
) -> CleanReport:
    """Run package-manager dry-runs without changing the host."""
    return CleanReport(
        False,
        tuple(
            _execute_step(step, home, apply=False, runner=runner)
            for step in _steps(home, executable_finder=executable_finder)
        ),
    )


def execute_clean(
    home: Path,
    *,
    executable_finder: Callable[[str], str | None] = shutil.which,
    runner: CommandRunner = _default_runner,
) -> CleanReport:
    """Run the selected cleanup commands after the host policy allows mutation."""
    require_mutation_allowed(home)
    return CleanReport(
        True,
        tuple(
            _execute_step(step, home, apply=True, runner=runner)
            for step in _steps(home, executable_finder=executable_finder)
        ),
    )


def _summary(report: CleanReport) -> dict[str, int]:
    return {
        status.value: count
        for status in CleanStatus
        if (count := sum(result.status is status for result in report.results))
    }


def _document(report: CleanReport, *, apply_allowed: bool) -> dict[str, object]:
    return {
        "schema_version": 1,
        "operation": "clean",
        "ok": report.ok,
        "apply": report.apply,
        "summary": _summary(report),
        "steps": [
            {
                "name": result.step.name,
                "owner": result.step.owner,
                "command": list(result.command),
                "status": result.status.value,
                "exit_code": result.exit_code,
                "duration_ms": result.duration_ms,
                "output": result.output,
                "reason": result.reason,
            }
            for result in report.results
        ],
        "notes": [
            "Only mise tool versions and Homebrew package-manager cleanup are included.",
            "Skillshare trash, configuration drift, generated/, and inventory/ are not cleaned automatically.",
        ],
        "next": (
            ["mise run clean -- --apply"]
            if not report.apply
            and apply_allowed
            and any(result.status is CleanStatus.PREVIEWED for result in report.results)
            else []
        ),
    }


def _render(report: CleanReport, *, apply_allowed: bool) -> None:
    for result in report.results:
        detail = result.output or result.reason
        print(
            f"{result.status.value.upper():9} {result.step.name}"
            + (f": {detail}" if detail else "")
        )
    if not report.results:
        print("SKIPPED   no supported cleanup owners are available")
    summary = ", ".join(
        f"{count} {status}" for status, count in _summary(report).items()
    )
    print(f"Summary: {summary or 'no steps'}")
    if not report.apply:
        if apply_allowed and any(
            result.status is CleanStatus.PREVIEWED for result in report.results
        ):
            print("Next: mise run clean -- --apply")
        elif not apply_allowed:
            print("No apply step: host policy disables dotfiles mutation.")
    print(
        "Scope: mise tool versions and Homebrew cleanup only; "
        "Skillshare trash/configuration and repository state are untouched."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preview or explicitly run package-manager cleanup.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="run cleanup commands (default: preview only)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit one JSON document on stdout",
    )
    args = parser.parse_args(argv)
    home = Path.home()
    try:
        apply_allowed = mutation_allowed(home)
        report = execute_clean(home) if args.apply else plan_clean(home)
    except HostPolicyError as error:
        emit_error(
            "clean",
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
