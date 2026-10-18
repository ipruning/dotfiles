"""Aggregate read-only repository and host health checks."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .host_policy import HostPolicyError
from .mise import canonical_mise_environment, canonical_mise_executable
from .models import NOT_APPLICABLE, Severity
from .process import CommandRunner, run_in_repository
from .render import emit_error


@dataclass(frozen=True)
class DoctorStep:
    name: str
    owner: str
    command: tuple[str, ...]
    timeout_seconds: int
    json_output: bool = False
    environment: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class DoctorResult:
    step: DoctorStep
    # None means the owner is not available on this host, as for Finding.
    severity: Severity | None
    exit_code: int | None = None
    report: dict[str, object] | None = None
    output: str | None = None
    reason: str | None = None

    @property
    def label(self) -> str:
        return self.severity.value if self.severity is not None else NOT_APPLICABLE


@dataclass(frozen=True)
class DoctorReport:
    results: tuple[DoctorResult, ...]
    strict: bool = False

    @property
    def ok(self) -> bool:
        return not any(
            result.severity is Severity.ERROR
            or (self.strict and result.severity is Severity.WARN)
            for result in self.results
        )


def _severity_from_report(
    report: dict[str, object] | None,
    *,
    exit_code: int,
) -> Severity:
    if exit_code != 0:
        return Severity.ERROR
    if report is None:
        return Severity.OK
    if report.get("ok") is False:
        return Severity.ERROR
    changes = report.get("changes")
    if isinstance(changes, list) and changes:
        return Severity.WARN
    summary = report.get("summary")
    counts = summary if isinstance(summary, dict) else {}

    def count(severity: Severity) -> int:
        value = counts.get(severity.value)
        return value if isinstance(value, int) else 0

    if count(Severity.ERROR) > 0:
        return Severity.ERROR
    if count(Severity.WARN) > 0:
        return Severity.WARN
    return Severity.OK


def _parse_report(step: DoctorStep, stdout: str) -> dict[str, object] | None:
    if not step.json_output:
        return None
    try:
        document = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise ValueError(f"returned invalid JSON: {error}") from error
    if not isinstance(document, dict):
        raise ValueError("returned JSON that is not an object")
    return cast("dict[str, object]", document)


def _step_environment(
    home: Path,
    step: DoctorStep,
) -> dict[str, str]:
    environment = (
        canonical_mise_environment(home) if step.owner == "mise" else os.environ.copy()
    )
    environment.update(step.environment)
    environment["HOME"] = str(home)
    return environment


def _run_step(
    step: DoctorStep,
    home: Path,
    *,
    runner: CommandRunner,
) -> DoctorResult:
    try:
        completed = runner(
            step.command,
            _step_environment(home, step),
            step.timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return DoctorResult(
            step,
            Severity.ERROR,
            reason=f"timed out after {step.timeout_seconds}s",
        )
    except OSError as error:
        return DoctorResult(step, Severity.ERROR, reason=str(error))

    output = (
        "\n".join(
            part.strip()
            for part in (completed.stdout, completed.stderr)
            if part.strip()
        )
        or None
    )
    try:
        report = _parse_report(step, completed.stdout)
    except ValueError as error:
        return DoctorResult(
            step,
            Severity.ERROR,
            exit_code=completed.returncode,
            output=output,
            reason=str(error),
        )
    severity = _severity_from_report(report, exit_code=completed.returncode)
    return DoctorResult(
        step,
        severity,
        exit_code=completed.returncode,
        report=report,
        output=output,
        reason=(
            None
            if severity is not Severity.ERROR
            else f"command exited {completed.returncode}"
        ),
    )


def _internal_steps() -> tuple[DoctorStep, ...]:
    python = sys.executable
    return tuple(
        DoctorStep(
            name,
            "dotfiles",
            (python, "-m", f"scripts.{module}", "--json"),
            300,
            json_output=True,
        )
        for name, module in (
            ("dotfiles.check", "check"),
            ("dotfiles.diff", "diff"),
            ("dotfiles.mise-sync", "mise_sync"),
            ("dotfiles.lint", "lint"),
        )
    )


def _external_steps(
    home: Path,
    *,
    executable_finder: Callable[[str], str | None],
) -> tuple[DoctorStep, ...]:
    steps: list[DoctorStep] = []
    mise = canonical_mise_executable(home)
    if mise:
        steps.append(DoctorStep("mise.doctor", "mise", (mise, "doctor"), 300))
    # Skillshare doctor migrates configuration and writes target probes, even
    # with --json: https://github.com/runkids/skillshare/blob/v0.20.29/cmd/skillshare/doctor.go
    # Its read-only configuration checks are already part of scripts.check.
    for name, tool, arguments, timeout, json_output in (
        ("brew.doctor", "brew", ("doctor",), 300, False),
        ("pueue.status", "pueue", ("status",), 30, False),
    ):
        executable = executable_finder(tool)
        if executable:
            steps.append(
                DoctorStep(
                    name,
                    tool,
                    (executable, *arguments),
                    timeout,
                    json_output=json_output,
                ),
            )
    return tuple(steps)


def inspect_doctor(
    home: Path,
    *,
    executable_finder: Callable[[str], str | None] = shutil.which,
    runner: CommandRunner = run_in_repository,
    strict: bool = False,
) -> DoctorReport:
    """Run the aggregate read-only checks and retain each command's evidence."""
    results = [
        _run_step(step, home, runner=runner)
        for step in (
            *_internal_steps(),
            *_external_steps(
                home,
                executable_finder=executable_finder,
            ),
        )
    ]
    missing_names = {
        "brew": "brew.doctor",
        "mise": "mise.doctor",
        "pueue": "pueue.status",
    }
    present_tools = {result.step.owner for result in results}
    for tool, name in missing_names.items():
        if tool not in present_tools:
            results.append(
                DoctorResult(
                    DoctorStep(name, tool, (tool,), 0),
                    None,
                    reason=f"{tool} is not available on PATH",
                ),
            )
    return DoctorReport(tuple(results), strict=strict)


def _summary(report: DoctorReport) -> dict[str, int]:
    counts = Counter(result.label for result in report.results)
    labels = (*(severity.value for severity in Severity), NOT_APPLICABLE)
    return {label: counts[label] for label in labels if counts[label]}


def _document(report: DoctorReport) -> dict[str, object]:
    return {
        "schema_version": 1,
        "operation": "doctor",
        "ok": report.ok,
        "strict": report.strict,
        "system": platform.system(),
        "summary": _summary(report),
        "steps": [
            {
                "name": result.step.name,
                "owner": result.step.owner,
                "command": list(result.step.command),
                "severity": result.severity.value if result.severity else None,
                "applicable": result.severity is not None,
                "exit_code": result.exit_code,
                "report": result.report,
                "output": result.output,
                "reason": result.reason,
            }
            for result in report.results
        ],
    }


def _render(report: DoctorReport) -> None:
    for result in report.results:
        detail = result.reason
        if detail is None and result.report:
            summary = result.report.get("summary")
            if isinstance(summary, dict):
                detail = (
                    ", ".join(
                        f"{key}={value}"
                        for key, value in summary.items()
                        if isinstance(value, int) and value
                    )
                    or None
                )
            if result.step.name == "dotfiles.diff":
                changes = result.report.get("changes")
                if isinstance(changes, list) and changes:
                    detail = f"{len(changes)} drift entries"
        if detail is None and result.output and result.severity is not Severity.OK:
            detail = result.output.splitlines()[0]
        print(
            f"{result.label.upper():7} {result.step.name}"
            + (f": {detail}" if detail else "")
        )
    summary = ", ".join(
        f"{count} {status}" for status, count in _summary(report).items()
    )
    print(f"Summary: {summary or 'no checks'}")
    if not report.ok:
        print("One or more doctor checks failed; inspect the JSON report for details.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run aggregate read-only repository and host health checks.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit one JSON document on stdout",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat warnings as failures",
    )
    args = parser.parse_args(argv)
    try:
        report = inspect_doctor(Path.home(), strict=args.strict)
    except HostPolicyError as error:
        emit_error("doctor", str(error), as_json=args.as_json, code=error.code)
        return 1
    if args.as_json:
        print(json.dumps(_document(report), indent=2, sort_keys=True))
    else:
        _render(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
