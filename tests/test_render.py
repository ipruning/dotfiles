from scripts.models import Finding, FindingReport, Severity
from scripts.render import finding_document, render_findings


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

    assert finding_document(report)["ok"] is True
    assert finding_document(report, strict=True)["ok"] is False


def test_plain_render_hides_ok_and_skipped_findings_by_default(capsys) -> None:
    report = FindingReport(
        schema_version=1,
        findings=(
            Finding("ready", Severity.OK, "ready", "ready"),
            Finding("not-applicable", Severity.SKIPPED, "skipped", "skipped"),
        ),
    )

    render_findings(report, include_ok=False)

    output = capsys.readouterr().out
    assert "READY" not in output
    assert "SKIPPED" not in output
    assert "Summary: 1 ok, 0 warn, 0 error, 1 skipped" in output
