"""Shared rendering for reports and CLI failure envelopes."""

from __future__ import annotations

import json
import sys

from .models import FindingReport, Severity


def finding_document(
    report: FindingReport,
    *,
    operation: str,
    strict: bool = False,
) -> dict[str, object]:
    return {
        "schema_version": report.schema_version,
        "operation": operation,
        "ok": report.is_ok(strict=strict),
        "summary": finding_counts(report),
        "findings": [
            {
                "check": finding.check,
                "severity": finding.severity.value,
                "code": finding.code,
                "message": finding.message,
                "path": str(finding.path) if finding.path else None,
                "action": finding.action,
            }
            for finding in report.findings
        ],
    }


def error_document(
    operation: str,
    code: str,
    message: str,
    *,
    apply: bool | None = None,
) -> dict[str, object]:
    document: dict[str, object] = {
        "schema_version": 1,
        "operation": operation,
        "ok": False,
        "error": {"code": code, "message": message},
    }
    if apply is not None:
        document["apply"] = apply
    return document


def emit_error(
    operation: str,
    message: str,
    *,
    as_json: bool,
    apply: bool | None = None,
) -> None:
    """Report a failed operation on both streams: prose to stderr, JSON to stdout."""
    code = f"{operation}_failed"
    print(f"ERROR {code} {message}", file=sys.stderr)
    if as_json:
        print(
            json.dumps(
                error_document(operation, code, message, apply=apply),
                indent=2,
                sort_keys=True,
            ),
        )


def finding_counts(report: FindingReport) -> dict[str, int]:
    return {
        severity.value: sum(finding.severity is severity for finding in report.findings)
        for severity in Severity
    }


def render_findings(report: FindingReport, *, include_ok: bool) -> None:
    visible = [
        finding
        for finding in report.findings
        if include_ok or finding.severity is not Severity.OK
    ]
    if not visible:
        print("No findings.")
    for finding in visible:
        print(f"{finding.severity.value.upper():7} {finding.code}")
        print(f"        {finding.message}")
        if finding.path:
            print(f"        {finding.path}")
        if finding.action:
            print(f"        action: {finding.action}")
    counts = finding_counts(report)
    print(
        "Summary: " + ", ".join(f"{count} {name}" for name, count in counts.items()),
    )
