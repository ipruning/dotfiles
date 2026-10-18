import json

from scripts.models import Finding, FindingReport, Severity
from scripts.render import (
    emit_error,
    error_document,
    finding_document,
    render_findings,
)


def test_finding_document_honors_strict_warning_policy() -> None:
    report = FindingReport(
        schema_version=1,
        findings=(
            Finding(
                check="optional.capability",
                severity=Severity.WARN,
                code="optional.capability_missing",
                message="Optional capability is missing",
            ),
        ),
    )

    lenient = finding_document(report, operation="check")
    strict = finding_document(report, operation="check", strict=True)

    assert lenient["ok"] is True
    assert lenient["operation"] == "check"
    assert lenient["schema_version"] == 1
    assert lenient["summary"] == {
        "ok": 0,
        "warn": 1,
        "error": 0,
        "skipped": 0,
    }
    assert strict["ok"] is False


def test_finding_document_marks_inapplicable_checks_without_a_severity() -> None:
    report = FindingReport(
        schema_version=1,
        findings=(
            Finding("repository", None, "syntax.zsh_skipped", "no zsh here"),
            Finding("repository", Severity.ERROR, "syntax.zsh", "broken"),
        ),
    )

    document = finding_document(report, operation="shell")

    assert document["findings"] == [
        {
            "check": "repository",
            "severity": None,
            "applicable": False,
            "code": "syntax.zsh_skipped",
            "message": "no zsh here",
            "path": None,
            "action": None,
        },
        {
            "check": "repository",
            "severity": "error",
            "applicable": True,
            "code": "syntax.zsh",
            "message": "broken",
            "path": None,
            "action": None,
        },
    ]
    assert document["summary"] == {"ok": 0, "warn": 0, "error": 1, "skipped": 1}
    # An inapplicable check never gates, but a real error still does.
    assert document["ok"] is False


def test_plain_render_hides_only_ok_findings_by_default(capsys) -> None:
    report = FindingReport(
        schema_version=1,
        findings=(
            Finding("ready", Severity.OK, "ready.code", "all good"),
            Finding("not-applicable", None, "gate.skipped", "no zsh"),
        ),
    )

    render_findings(report, include_ok=False)

    output = capsys.readouterr().out
    assert "ready.code" not in output
    assert "SKIPPED" in output
    assert "gate.skipped" in output
    assert "Summary: 1 ok, 0 warn, 0 error, 1 skipped" in output


def test_error_document_reports_a_failed_operation() -> None:
    document = error_document("diff", "diff.failed", "Unsupported application: xyz")

    assert document == {
        "schema_version": 1,
        "operation": "diff",
        "ok": False,
        "error": {
            "code": "diff.failed",
            "message": "Unsupported application: xyz",
        },
    }


def test_emit_error_writes_prose_to_stderr_and_json_to_stdout(capsys) -> None:
    emit_error("adopt", "Unsupported application: xyz", as_json=True, apply=True)

    captured = capsys.readouterr()
    assert "ERROR adopt.failed Unsupported application: xyz" in captured.err
    document = json.loads(captured.out)
    assert document["ok"] is False
    assert document["apply"] is True
    assert document["error"]["code"] == "adopt.failed"


def test_emit_error_keeps_stdout_empty_without_json(capsys) -> None:
    emit_error("adopt", "Unsupported application: xyz", as_json=False)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ERROR adopt.failed" in captured.err
