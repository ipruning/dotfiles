import configparser
import subprocess
from pathlib import Path
from typing import cast

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


class InvalidFileKindRunner(StubMackupRunner):
    def inspect(
        self,
        repo_root: Path,
        home: Path,
        application: str | None,
    ) -> dict[str, object]:
        document = super().inspect(repo_root, home, "git")
        changes = document["changes"]
        assert isinstance(changes, list)
        change = cast("dict[str, object]", changes[0])
        assert isinstance(change, dict)
        change["live_kind"] = "socket"
        return document


def test_inspect_drift_rejects_unknown_file_kind(tmp_path: Path) -> None:
    with pytest.raises(DriftProtocolError, match="unknown file kind"):
        inspect_drift(tmp_path, tmp_path, runner=InvalidFileKindRunner())


def test_inspect_drift_uses_current_checkout_as_reference_storage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "checkout"
    home = tmp_path / "home"
    (repo_root / "mackup/applications").mkdir(parents=True)
    (repo_root / "mackup/mackup.cfg").write_text(
        "[storage]\nengine = file_system\npath = dotfiles\n"
        "directory = reference\n[applications_to_sync]\n",
    )
    captured: dict[str, str] = {}

    def run(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        config_path = Path(command[command.index("--config-file") + 1])
        config = configparser.ConfigParser(allow_no_value=True)
        config.read(config_path)
        captured["config_path"] = str(config_path)
        captured["storage_path"] = config.get("storage", "path")
        return subprocess.CompletedProcess(
            command,
            0,
            '{"schema_version":1,"operation":"diff","changes":[],"summary":{}}',
            "",
        )

    monkeypatch.setattr("scripts.diff.subprocess.run", run)

    report = inspect_drift(repo_root, home)

    assert report.ok is True
    assert captured["storage_path"] == str(repo_root)
    assert captured["config_path"] != str(repo_root / "mackup/mackup.cfg")
