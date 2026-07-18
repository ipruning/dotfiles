import configparser
import json
import subprocess
from pathlib import Path
from typing import cast

import pytest

from tests.conftest import mackup_cfg

from scripts.diff import (
    DriftProtocolError,
    MackupCommandError,
    SubprocessMackupRunner,
    inspect_drift,
    main,
)
from scripts.profiles import HostProfile


def _drift_document(kind: str, error: str | None = None) -> dict[str, object]:
    return {
        "schema_version": 1,
        "operation": "diff",
        "changes": [
            {
                "application": "git",
                "reference_path": "reference/.gitconfig",
                "live_path": "/home/someone/.gitconfig",
                "kind": kind,
                "reference_kind": "file",
                "live_kind": None if kind == "unreadable" else "file",
                "error": error,
            },
        ],
        "summary": {kind: 1},
    }


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


class MultiApplicationRunner:
    def inspect(
        self,
        repo_root: Path,
        home: Path,
        application: str | None,
    ) -> dict[str, object]:
        assert application is None
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
                {
                    "application": "skillshare",
                    "reference_path": str(
                        repo_root / "reference/.config/skillshare/config.yaml"
                    ),
                    "live_path": str(home / ".config/skillshare/config.yaml"),
                    "kind": "only-reference",
                    "reference_kind": "file",
                    "live_kind": None,
                    "error": None,
                },
                {
                    "application": "hushlogin",
                    "reference_path": str(repo_root / "reference/.hushlogin"),
                    "live_path": str(home / ".hushlogin"),
                    "kind": "only-reference",
                    "reference_kind": "file",
                    "live_kind": None,
                    "error": None,
                },
                {
                    "application": "uv",
                    "reference_path": str(repo_root / "reference/.config/uv/uv.toml"),
                    "live_path": str(home / ".config/uv/uv.toml"),
                    "kind": "only-reference",
                    "reference_kind": "file",
                    "live_kind": None,
                    "error": None,
                },
                {
                    "application": "aerospace",
                    "reference_path": str(
                        repo_root / "reference/.config/aerospace/aerospace.toml",
                    ),
                    "live_path": str(home / ".config/aerospace/aerospace.toml"),
                    "kind": "only-reference",
                    "reference_kind": "file",
                    "live_kind": None,
                    "error": None,
                },
            ],
            "summary": {"modified": 1, "only-reference": 4},
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


def test_linux_lite_profile_excludes_macos_drift_by_default(tmp_path: Path) -> None:
    report = inspect_drift(
        tmp_path / "repo",
        tmp_path / "home",
        profile="auto",
        system_name="Linux",
        runner=MultiApplicationRunner(),
    )

    assert report.profile is HostProfile.LINUX_LITE
    assert [change.application for change in report.changes] == [
        "git",
        "skillshare",
    ]
    assert report.summary == {"modified": 1, "only-reference": 1}

    full = inspect_drift(
        tmp_path / "repo",
        tmp_path / "home",
        profile="full",
        system_name="Linux",
        runner=MultiApplicationRunner(),
    )
    assert full.profile is HostProfile.FULL
    assert [change.application for change in full.changes] == [
        "git",
        "skillshare",
        "hushlogin",
        "uv",
        "aerospace",
    ]


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


def test_diff_cli_reports_ordinary_drift_as_success_and_unreadable_as_failure(
    monkeypatch,
    capsys,
) -> None:
    documents = iter(
        [
            _drift_document("modified"),
            _drift_document("unreadable", error="permission denied"),
        ],
    )

    def run(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, json.dumps(next(documents)), "")

    monkeypatch.setattr("scripts.diff.subprocess.run", run)

    assert main(["--profile", "full"]) == 0
    assert "1 modified" in capsys.readouterr().out

    assert main(["--profile", "full"]) == 1
    assert "permission denied" in capsys.readouterr().err


def test_subprocess_runner_surfaces_mackup_failure_modes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    (repo_root / "mackup/applications").mkdir(parents=True)
    config_path = repo_root / "mackup/mackup.cfg"
    config_path.write_text(mackup_cfg())
    responses: dict[str, tuple[int, str, str]] = {}

    def run(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        code, stdout, stderr = responses["next"]
        return subprocess.CompletedProcess(command, code, stdout, stderr)

    monkeypatch.setattr("scripts.diff.subprocess.run", run)
    runner = SubprocessMackupRunner()

    responses["next"] = (1, "", "mackup exploded")
    with pytest.raises(MackupCommandError, match="mackup exploded"):
        runner.inspect(repo_root, home, None)

    responses["next"] = (
        7,
        '{"schema_version":1,"operation":"diff","changes":[],"summary":{}}',
        "mackup failed after reporting",
    )
    with pytest.raises(MackupCommandError, match="failed after reporting"):
        runner.inspect(repo_root, home, None)

    unreadable = _drift_document("unreadable", error="permission denied")
    responses["next"] = (1, json.dumps(unreadable), "")
    assert runner.inspect(repo_root, home, None) == unreadable

    responses["next"] = (1, json.dumps(_drift_document("modified")), "")
    with pytest.raises(MackupCommandError, match="Mackup exited 1"):
        runner.inspect(repo_root, home, None)

    responses["next"] = (0, "not json", "")
    with pytest.raises(MackupCommandError, match="invalid JSON"):
        runner.inspect(repo_root, home, None)

    responses["next"] = (0, "[]", "")
    with pytest.raises(MackupCommandError, match="non-object"):
        runner.inspect(repo_root, home, None)

    config_path.write_text("[applications_to_sync]\n")
    responses["next"] = (0, "{}", "")
    with pytest.raises(MackupCommandError, match="Invalid Mackup config"):
        runner.inspect(repo_root, home, None)


def test_subprocess_runner_preserves_application_name_case(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    (repo_root / "mackup/applications").mkdir(parents=True)
    (repo_root / "mackup/mackup.cfg").write_text(mackup_cfg("Example-App\n"))
    captured: dict[str, str] = {}

    def run(command: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        config_path = Path(command[command.index("--config-file") + 1])
        captured["runtime_config"] = config_path.read_text()
        return subprocess.CompletedProcess(
            command,
            0,
            '{"schema_version":1,"operation":"diff","changes":[],"summary":{}}',
            "",
        )

    monkeypatch.setattr("scripts.diff.subprocess.run", run)

    SubprocessMackupRunner().inspect(repo_root, home, None)

    assert "Example-App" in captured["runtime_config"]
    assert "example-app" not in captured["runtime_config"]


def test_inspect_drift_uses_current_checkout_as_reference_storage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "checkout"
    home = tmp_path / "home"
    (repo_root / "mackup/applications").mkdir(parents=True)
    (repo_root / "mackup/mackup.cfg").write_text(mackup_cfg())
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
