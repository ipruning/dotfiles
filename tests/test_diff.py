import json
import time
from pathlib import Path

import pytest

from scripts.diff import inspect_drift, main
from scripts.mappings import MappingError
from scripts.models import DriftKind
from tests.conftest import mackup_cfg


def setup_mapping(repo: Path, name: str, mapping: str) -> None:
    root = repo / "mackup"
    (root / "applications").mkdir(parents=True, exist_ok=True)
    (root / "mackup.cfg").write_text(mackup_cfg(f"{name}\n"))
    (root / "applications" / f"{name}.cfg").write_text(mapping)
    (repo / "reference").mkdir(exist_ok=True)


def test_drift_compares_files_directories_and_symlinks(tmp_path: Path) -> None:
    repo, home = tmp_path / "repo", tmp_path / "home"
    setup_mapping(repo, "Example-App", "[configuration_files]\ndata\nmanaged\n")
    reference = repo / "reference"
    for root in (reference, home):
        (root / "data").mkdir(parents=True, exist_ok=True)
        (root / "data/same").write_text("same")
        (root / "data/changed").write_text(root.name)
    (reference / "data/only-reference").touch()
    (home / "data/only-live").touch()
    (reference / "data/changed-type").touch()
    (home / "data/changed-type").symlink_to("absent")
    (reference / "data/changed-link").symlink_to("first")
    (home / "data/changed-link").symlink_to("second")
    (reference / "managed").touch()
    (home / "managed").symlink_to(reference / "managed")

    report = inspect_drift(repo, home, "Example-App")

    assert report.ok
    assert {change.live_path.name: change.kind for change in report.changes} == {
        "changed": DriftKind.MODIFIED,
        "changed-link": DriftKind.MODIFIED,
        "changed-type": DriftKind.TYPE_CHANGED,
        "only-live": DriftKind.ONLY_LIVE,
        "only-reference": DriftKind.ONLY_REFERENCE,
    }
    assert report.summary["modified"] == 2


@pytest.mark.parametrize("xdg_directory", ["custom", ""])
def test_profile_and_xdg_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, xdg_directory: str
) -> None:
    repo, home = tmp_path / "repo", tmp_path / "home"
    setup_mapping(repo, "zed", "[xdg_configuration_files]\nzed/settings.json\n")
    monkeypatch.setenv(
        "XDG_CONFIG_HOME", str(home / xdg_directory) if xdg_directory else ""
    )
    reference = repo / "reference/.config/zed/settings.json"
    reference.parent.mkdir(parents=True)
    reference.touch()

    assert not inspect_drift(repo, home, system_name="Linux").changes
    explicit = inspect_drift(repo, home, "zed", system_name="Linux")
    assert explicit.changes[0].reference_path == reference
    assert (
        explicit.changes[0].live_path
        == home / (xdg_directory or ".config") / "zed/settings.json"
    )


def test_empty_mapping_cannot_report_a_clean_scan(tmp_path: Path) -> None:
    setup_mapping(tmp_path, "git", "[application]\nname = Git\n")
    with pytest.raises(MappingError, match="No configuration paths"):
        inspect_drift(tmp_path, tmp_path / "home", "git")


def test_invalid_mapping_path_is_reported(tmp_path: Path) -> None:
    setup_mapping(tmp_path, "git", "[configuration_files]\n../outside\n")
    with pytest.raises(MappingError, match="Invalid relative path"):
        inspect_drift(tmp_path, tmp_path / "home", "git")
    with pytest.raises(MappingError, match="Unsupported application"):
        inspect_drift(tmp_path, tmp_path / "home", "missing")


def test_empty_applications_cannot_report_a_clean_scan(tmp_path: Path) -> None:
    setup_mapping(tmp_path, "git", "[configuration_files]\n.gitconfig\n")
    (tmp_path / "mackup/mackup.cfg").write_text(mackup_cfg())
    with pytest.raises(MappingError, match="No applications selected"):
        inspect_drift(tmp_path, tmp_path / "home")


def test_diff_timeout_reports_an_incomplete_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_mapping(tmp_path, "git", "[configuration_files]\n.gitconfig\n")
    monkeypatch.setattr("scripts.diff.DRIFT_TIMEOUT_SECONDS", 0.02)

    def slow_read(_path: Path) -> None:
        time.sleep(0.5)

    monkeypatch.setattr("scripts.diff.read_mapping_config", slow_read)
    with pytest.raises(MappingError, match="inspection timed out"):
        inspect_drift(tmp_path, tmp_path / "home")


def test_diff_cli_reports_unreadable_files_without_exposing_contents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, home = tmp_path / "repo", tmp_path / "home"
    setup_mapping(repo, "git", "[configuration_files]\n.gitconfig\n")
    home.mkdir()
    (repo / "reference/.gitconfig").write_text("reference data")
    live = home / ".gitconfig"
    live.write_text("live data")
    monkeypatch.setattr("scripts.diff.__file__", str(repo / "scripts/diff.py"))
    monkeypatch.setenv("HOME", str(home))

    assert main(["--json", "--profile", "linux-lite"]) == 0
    captured = capsys.readouterr().out
    document = json.loads(captured)
    assert document["profile"] == "linux-lite"
    assert document["summary"] == {"modified": 1}
    assert "reference data" not in captured and "live data" not in captured

    read_bytes = Path.read_bytes

    def deny(path: Path) -> bytes:
        if path == live:
            raise PermissionError("permission denied")
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", deny)
    assert main(["--json", "git"]) == 1
    document = json.loads(capsys.readouterr().out)
    assert document["ok"] is False
    assert document["summary"] == {"unreadable": 1}
    assert document["changes"][0]["error"] == "permission denied"
