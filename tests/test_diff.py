from pathlib import Path

import pytest

from scripts.diff import DriftProtocolError, inspect_drift


class StubMackupRunner:
    def inspect(
        self,
        repo_root: Path,
        home: Path,
        application: str | None,
    ) -> dict[str, object]:
        assert application == "git"
        return {
            "schema_version": 1,
            "operation": "diff",
            "changes": [
                {
                    "application": "git",
                    "reference_path": str(repo_root / "reference/.gitconfig"),
                    "live_path": str(home / ".gitconfig"),
                    "kind": "modified",
                    "reference_kind": "file",
                    "live_kind": "file",
                    "error": None,
                },
            ],
            "summary": {"modified": 1},
        }


def test_inspect_drift_returns_typed_location_only_report(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"

    report = inspect_drift(
        repo_root,
        home,
        application="git",
        runner=StubMackupRunner(),
    )

    assert report.schema_version == 1
    assert report.operation == "diff"
    assert report.summary == {"modified": 1}
    assert report.changes[0].application == "git"
    assert report.changes[0].kind.value == "modified"
    assert report.changes[0].live_path == home / ".gitconfig"
    assert report.ok is True


class InvalidSchemaRunner:
    def inspect(
        self,
        repo_root: Path,
        home: Path,
        application: str | None,
    ) -> dict[str, object]:
        return {
            "schema_version": 2,
            "operation": "diff",
            "changes": [],
            "summary": {},
        }


def test_inspect_drift_rejects_unknown_schema(tmp_path: Path) -> None:
    with pytest.raises(DriftProtocolError, match="schema_version"):
        inspect_drift(tmp_path, tmp_path, runner=InvalidSchemaRunner())
