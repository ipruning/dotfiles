import json
import os
from pathlib import Path

from scripts.models import Drift, DriftKind, FileKind
from scripts.restore import (
    RestoreReport,
    RestoreResult,
    RestoreStatus,
    _render,
    apply_restore,
    plan_restore,
)
from tests.conftest import REPO_ROOT, run_scripts_module


def test_restore_defaults_to_a_read_only_application_plan(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    completed = run_scripts_module("restore", home, "hushlogin", "--json")

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    assert document["schema_version"] == 1
    assert document["operation"] == "restore"
    assert document["application"] == "hushlogin"
    assert document["apply"] is False
    assert document["ok"] is True
    assert document["next"] == ["mise run restore -- hushlogin --apply"]
    assert document["summary"] == {"planned": 1}
    assert document["changes"] == [
        {
            "action": "link",
            "backup_path": None,
            "error": None,
            "kind": "only-reference",
            "live_path": str(home / ".hushlogin"),
            "reference_path": str(REPO_ROOT / "reference/.hushlogin"),
            "status": "planned",
        },
    ]
    assert not (home / ".hushlogin").exists()


def test_restore_human_output_does_not_suggest_apply_when_converged(capsys) -> None:
    _render(RestoreReport(application="example", apply=False, results=()))

    captured = capsys.readouterr()
    assert captured.out == "Summary: no changes\n"
    assert captured.err == ""


def test_restore_apply_backs_up_live_file_and_links_reference(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    live_path = home / ".hushlogin"
    live_path.write_text("host-specific\n")

    preview = run_scripts_module("restore", home, "hushlogin", "--json")
    assert preview.returncode == 0
    assert live_path.read_text() == "host-specific\n"

    applied = run_scripts_module("restore", home, "hushlogin", "--apply", "--json")

    assert applied.returncode == 0
    document = json.loads(applied.stdout)
    assert document["apply"] is True
    assert document["summary"] == {"applied": 1}
    change = document["changes"][0]
    assert change["status"] == "applied"
    backup_path = Path(change["backup_path"])
    assert backup_path.read_text() == "host-specific\n"
    assert live_path.is_symlink()
    assert live_path.resolve() == REPO_ROOT / "reference/.hushlogin"

    converged = run_scripts_module("restore", home, "hushlogin", "--json")
    assert converged.returncode == 0
    assert json.loads(converged.stdout)["changes"] == []


def test_restore_recreates_an_adopted_symlink(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    reference = repo_root / "reference/.linked"
    live = home / ".linked"
    external = tmp_path / "outside-config"
    reference.parent.mkdir(parents=True)
    home.mkdir()
    external.write_text("outside content\n")
    reference.symlink_to(external)
    live.write_text("host-specific\n")
    plan = RestoreReport(
        application="example",
        apply=False,
        results=(
            RestoreResult(
                Drift(
                    application="example",
                    reference_path=reference,
                    live_path=live,
                    kind=DriftKind.TYPE_CHANGED,
                    reference_kind=FileKind.LINK,
                    live_kind=FileKind.FILE,
                ),
                action="link",
                status=RestoreStatus.PLANNED,
            ),
        ),
    )

    applied = apply_restore(repo_root, home, plan)

    result = applied.results[0]
    assert result.status is RestoreStatus.APPLIED
    assert result.backup_path is not None
    assert result.backup_path.read_text() == "host-specific\n"
    assert live.is_symlink()
    assert os.readlink(live) == str(external)
    assert external.read_text() == "outside content\n"


def test_restore_human_apply_reports_the_backup_location(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / ".hushlogin").write_text("host-specific\n")

    completed = run_scripts_module("restore", home, "hushlogin", "--apply")

    assert completed.returncode == 0
    assert "backup:" in completed.stdout
    assert ".local/state/dotfiles/restore-backups/" in completed.stdout
    assert "Summary: 1 applied" in completed.stdout


def test_restore_rejects_invalid_scope_without_changing_home(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    conflicting = run_scripts_module(
        "restore",
        home,
        "hushlogin",
        "--dry-run",
    )
    unknown = run_scripts_module(
        "restore", home, "not-a-configured-application", "--apply", "--json"
    )

    assert conflicting.returncode == 2
    assert "unrecognized arguments: --dry-run" in conflicting.stderr
    assert unknown.returncode == 1
    error_document = json.loads(unknown.stdout)
    assert error_document["ok"] is False
    assert error_document["apply"] is True
    assert error_document["operation"] == "restore"
    assert error_document["error"]["code"] == "restore_failed"
    assert "Unsupported application" in error_document["error"]["message"]
    assert "uvx" not in error_document["error"]["message"]
    assert "ERROR restore_failed" in unknown.stderr
    assert list(home.iterdir()) == []


def test_restore_rejects_a_live_parent_that_escapes_home(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    external = tmp_path / "external"
    reference = repo_root / "reference/.config/tool/config.toml"
    reference.parent.mkdir(parents=True)
    reference.write_text("reference\n")
    home.mkdir()
    external.mkdir()
    (home / ".config").symlink_to(external, target_is_directory=True)
    drift = Drift(
        application="tool",
        reference_path=reference,
        live_path=home / ".config/tool/config.toml",
        kind=DriftKind.ONLY_REFERENCE,
        reference_kind=FileKind.FILE,
        live_kind=None,
    )
    plan = RestoreReport(
        application="tool",
        apply=False,
        results=(RestoreResult(drift, "link", RestoreStatus.PLANNED),),
    )

    report = apply_restore(repo_root, home, plan)

    assert report.ok is False
    assert report.results[0].status is RestoreStatus.FAILED
    assert "live parent is outside" in (report.results[0].error or "")
    assert list(external.iterdir()) == []


def test_restore_rolls_back_live_file_when_symlink_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    (repo_root / "reference").mkdir(parents=True)
    home.mkdir()
    (repo_root / "reference/.gitconfig").write_text("reference\n")
    live = home / ".gitconfig"
    live.write_text("live content\n")
    plan = RestoreReport(
        application="git",
        apply=False,
        results=(
            RestoreResult(
                Drift(
                    application="git",
                    reference_path=repo_root / "reference/.gitconfig",
                    live_path=live,
                    kind=DriftKind.MODIFIED,
                    reference_kind=FileKind.FILE,
                    live_kind=FileKind.FILE,
                ),
                action="link",
                status=RestoreStatus.PLANNED,
            ),
        ),
    )

    def refuse(self, target, target_is_directory=False):
        raise OSError("symlink refused")

    monkeypatch.setattr(Path, "symlink_to", refuse)
    applied = apply_restore(repo_root, home, plan)

    result = applied.results[0]
    assert result.status is RestoreStatus.FAILED
    assert result.backup_path is None
    assert live.read_text() == "live content\n"


def test_plan_restore_marks_unreadable_drift_failed(
    tmp_path: Path, monkeypatch
) -> None:
    from scripts import restore as restore_module
    from scripts.models import DriftReport
    from scripts.profiles import HostProfile

    unreadable = Drift(
        application="git",
        reference_path=tmp_path / "repo/reference/.gitconfig",
        live_path=tmp_path / "home/.gitconfig",
        kind=DriftKind.UNREADABLE,
        reference_kind=None,
        live_kind=None,
        error="permission denied",
    )
    monkeypatch.setattr(
        restore_module,
        "inspect_drift",
        lambda *args, **kwargs: DriftReport(
            schema_version=1,
            operation="diff",
            changes=(unreadable,),
            summary={"unreadable": 1},
            profile=HostProfile.FULL,
        ),
    )

    plan = plan_restore(tmp_path / "repo", tmp_path / "home", "git")

    assert plan.ok is False
    assert plan.results[0].status is RestoreStatus.FAILED
    assert "permission denied" in (plan.results[0].error or "")


def test_restore_rejects_traversal_segments_in_planned_paths(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    (repo_root / "reference").mkdir(parents=True)
    (home / ".ssh").mkdir(parents=True)
    (home / ".ssh/config").write_text("live ssh config\n")
    (repo_root / "reference/.ssh").mkdir()
    (repo_root / "reference/.ssh/config").write_text("reference\n")

    plan = RestoreReport(
        application="git",
        apply=False,
        results=(
            RestoreResult(
                Drift(
                    application="git",
                    reference_path=repo_root / "reference/.ssh/config",
                    live_path=home / "foo/../.ssh/config",
                    kind=DriftKind.MODIFIED,
                    reference_kind=FileKind.FILE,
                    live_kind=FileKind.FILE,
                ),
                action="link",
                status=RestoreStatus.PLANNED,
            ),
        ),
    )
    applied = apply_restore(repo_root, home, plan)

    assert applied.results[0].status is RestoreStatus.FAILED
    assert "traverses" in (applied.results[0].error or "")
    assert (home / ".ssh/config").read_text() == "live ssh config\n"
