from scripts.models import Finding, FindingReport, Severity
from scripts.render import finding_document


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
