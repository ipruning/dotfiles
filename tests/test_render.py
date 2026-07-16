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
    assert strict["ok"] is False


def test_plain_render_hides_only_ok_findings_by_default(capsys) -> None:
    report = FindingReport(
        schema_version=1,
        findings=(
            Finding("ready", Severity.OK, "ready.code", "all good"),
            Finding("not-applicable", Severity.SKIPPED, "gate.skipped", "no zsh"),
        ),
    )

    render_findings(report, include_ok=False)

    output = capsys.readouterr().out
    assert "ready.code" not in output
    assert "SKIPPED" in output
    assert "gate.skipped" in output
    assert "Summary: 1 ok, 0 warn, 0 error, 1 skipped" in output


def test_error_document_reports_a_failed_operation() -> None:
    document = error_document("diff", "diff_failed", "Unsupported application: xyz")

    assert document == {
        "schema_version": 1,
        "operation": "diff",
        "ok": False,
        "error": {
            "code": "diff_failed",
            "message": "Unsupported application: xyz",
        },
    }


def test_emit_error_writes_prose_to_stderr_and_json_to_stdout(capsys) -> None:
    emit_error("adopt", "Unsupported application: xyz", as_json=True)

    captured = capsys.readouterr()
    assert "ERROR adopt_failed Unsupported application: xyz" in captured.err
    document = json.loads(captured.out)
    assert document["ok"] is False
    assert document["error"]["code"] == "adopt_failed"


def test_emit_error_keeps_stdout_empty_without_json(capsys) -> None:
    emit_error("adopt", "Unsupported application: xyz", as_json=False)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ERROR adopt_failed" in captured.err
