import json
import os
import subprocess
from pathlib import Path

from scripts.adopt import (
    AdoptReport,
    AdoptResult,
    AdoptStatus,
    _render,
    apply_adopt,
    plan_adopt,
)
from scripts.models import Drift, DriftKind, FileKind

from tests.conftest import REPO_ROOT, run_scripts_module


def _tracked_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    (repo_root / "reference").mkdir(parents=True)
    home.mkdir()
    subprocess.run(["git", "init", "-q", str(repo_root)], check=True)
    return repo_root, home


def _commit_all(repo_root: Path) -> None:
    subprocess.run(["git", "-C", str(repo_root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-q",
            "-m",
            "state",
        ],
        check=True,
    )


def _plan(*results: AdoptResult) -> AdoptReport:
    return AdoptReport(application="example", apply=False, results=results)


def _drift(
    repo_root: Path,
    home: Path,
    relative: str,
    kind: DriftKind,
    *,
    live_kind: FileKind | None = FileKind.FILE,
) -> Drift:
    return Drift(
        application="example",
        reference_path=repo_root / "reference" / relative,
        live_path=home / relative,
        kind=kind,
        reference_kind=FileKind.FILE,
        live_kind=live_kind,
    )


def test_adopt_defaults_to_a_read_only_application_plan(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    completed = run_scripts_module("adopt", home, "hushlogin", "--json")

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    assert document["schema_version"] == 1
    assert document["operation"] == "adopt"
    assert document["apply"] is False
    assert document["ok"] is True
    assert document["next"] == ["mise run adopt -- hushlogin --apply"]
    assert document["changes"] == [
        {
            "action": "remove",
            "error": None,
            "kind": "only-reference",
            "live_path": str(home / ".hushlogin"),
            "reference_path": str(REPO_ROOT / "reference/.hushlogin"),
            "status": "planned",
        },
    ]
    assert (REPO_ROOT / "reference/.hushlogin").exists()


def test_adopt_human_output_does_not_suggest_apply_when_converged(capsys) -> None:
    _render(AdoptReport(application="example", apply=False, results=()))

    captured = capsys.readouterr()
    assert captured.out == "Summary: no changes\n"
    assert captured.err == ""


def test_adopt_apply_copies_live_truth_and_removes_dead_reference(
    tmp_path: Path,
) -> None:
    repo_root, home = _tracked_repo(tmp_path)
    (repo_root / "reference/.gitconfig").write_text("[user]\n  name = Old\n")
    (repo_root / "reference/.dead").write_text("gone live\n")
    _commit_all(repo_root)
    (home / ".gitconfig").write_text("[user]\n  name = New\n")
    (home / ".fresh").write_text("new live file\n")

    plan = _plan(
        AdoptResult(
            _drift(repo_root, home, ".gitconfig", DriftKind.MODIFIED),
            action="copy",
            status=AdoptStatus.PLANNED,
        ),
        AdoptResult(
            _drift(repo_root, home, ".fresh", DriftKind.ONLY_LIVE),
            action="copy",
            status=AdoptStatus.PLANNED,
        ),
        AdoptResult(
            _drift(
                repo_root,
                home,
                ".dead",
                DriftKind.ONLY_REFERENCE,
                live_kind=None,
            ),
            action="remove",
            status=AdoptStatus.PLANNED,
        ),
    )
    applied = apply_adopt(repo_root, home, plan)

    assert applied.ok is True
    assert (repo_root / "reference/.gitconfig").read_text() == "[user]\n  name = New\n"
    assert (repo_root / "reference/.fresh").read_text() == "new live file\n"
    assert not (repo_root / "reference/.dead").exists()
    assert (home / ".gitconfig").read_text() == "[user]\n  name = New\n"


def test_adopt_preserves_live_symlinks_instead_of_materializing_targets(
    tmp_path: Path,
) -> None:
    repo_root, home = _tracked_repo(tmp_path)
    (repo_root / "reference/.seed").write_text("seed\n")
    _commit_all(repo_root)
    secret_target = tmp_path / "outside-secret"
    secret_target.write_text("outside content\n")
    (home / ".linked").symlink_to(secret_target)

    plan = _plan(
        AdoptResult(
            _drift(repo_root, home, ".linked", DriftKind.ONLY_LIVE),
            action="copy",
            status=AdoptStatus.PLANNED,
        ),
    )
    applied = apply_adopt(repo_root, home, plan)

    assert applied.ok is True
    adopted = repo_root / "reference/.linked"
    assert adopted.is_symlink()
    assert os.readlink(adopted) == str(secret_target)


def test_adopt_apply_refuses_uncommitted_reference_changes(tmp_path: Path) -> None:
    repo_root, home = _tracked_repo(tmp_path)
    (repo_root / "reference/.gitconfig").write_text("[user]\n  name = Old\n")
    _commit_all(repo_root)
    (repo_root / "reference/.gitconfig").write_text("[user]\n  name = Dirty\n")
    (home / ".gitconfig").write_text("[user]\n  name = New\n")

    plan = _plan(
        AdoptResult(
            _drift(repo_root, home, ".gitconfig", DriftKind.MODIFIED),
            action="copy",
            status=AdoptStatus.PLANNED,
        ),
    )
    applied = apply_adopt(repo_root, home, plan)

    assert applied.ok is False
    assert all(result.status is AdoptStatus.FAILED for result in applied.results)
    assert "uncommitted" in (applied.results[0].error or "")
    assert (
        repo_root / "reference/.gitconfig"
    ).read_text() == "[user]\n  name = Dirty\n"


def test_adopt_apply_copies_directories_and_confines_paths(tmp_path: Path) -> None:
    repo_root, home = _tracked_repo(tmp_path)
    (repo_root / "reference/.config/templates").mkdir(parents=True)
    (repo_root / "reference/.config/templates/a.txt").write_text("old\n")
    _commit_all(repo_root)
    (home / ".config/templates").mkdir(parents=True)
    (home / ".config/templates/b.txt").write_text("new\n")

    plan = _plan(
        AdoptResult(
            Drift(
                application="example",
                reference_path=repo_root / "reference/.config/templates",
                live_path=home / ".config/templates",
                kind=DriftKind.MODIFIED,
                reference_kind=FileKind.DIRECTORY,
                live_kind=FileKind.DIRECTORY,
            ),
            action="copy",
            status=AdoptStatus.PLANNED,
        ),
    )
    applied = apply_adopt(repo_root, home, plan)

    assert applied.ok is True
    assert (repo_root / "reference/.config/templates/b.txt").read_text() == "new\n"
    assert not (repo_root / "reference/.config/templates/a.txt").exists()

    dotdot = _plan(
        AdoptResult(
            Drift(
                application="example",
                reference_path=repo_root / "reference/.config/..",
                live_path=home / ".config",
                kind=DriftKind.ONLY_REFERENCE,
                reference_kind=FileKind.DIRECTORY,
                live_kind=None,
            ),
            action="remove",
            status=AdoptStatus.PLANNED,
        ),
    )
    swallowed = apply_adopt(repo_root, home, dotdot)

    assert swallowed.ok is False
    assert "traverses" in (swallowed.results[0].error or "")
    assert (repo_root / "reference/.config/templates/b.txt").exists()

    link_escape_target = tmp_path / "outside-tree"
    link_escape_target.mkdir()
    (repo_root / "reference/.linkdir").symlink_to(link_escape_target)
    (home / ".linkdir").mkdir()
    (home / ".linkdir/new.txt").write_text("payload\n")
    through_link = _plan(
        AdoptResult(
            Drift(
                application="example",
                reference_path=repo_root / "reference/.linkdir/deeper/new.txt",
                live_path=home / ".linkdir/new.txt",
                kind=DriftKind.ONLY_LIVE,
                reference_kind=None,
                live_kind=FileKind.FILE,
            ),
            action="copy",
            status=AdoptStatus.PLANNED,
        ),
    )
    blocked = apply_adopt(repo_root, home, through_link)

    assert blocked.ok is False
    assert not (link_escape_target / "deeper").exists()

    escape = _plan(
        AdoptResult(
            Drift(
                application="example",
                reference_path=repo_root / "reference/../escape",
                live_path=home / ".escape",
                kind=DriftKind.ONLY_LIVE,
                reference_kind=None,
                live_kind=FileKind.FILE,
            ),
            action="copy",
            status=AdoptStatus.PLANNED,
        ),
    )
    (home / ".escape").write_text("nope\n")
    escaped = apply_adopt(repo_root, home, escape)

    assert escaped.ok is False
    assert not (repo_root / "escape").exists()


def test_adopt_failed_publish_restores_the_previous_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root, home = _tracked_repo(tmp_path)
    reference = repo_root / "reference/.config/example"
    reference.mkdir(parents=True)
    (reference / "old.txt").write_text("old\n")
    _commit_all(repo_root)
    live = home / ".config/example"
    live.mkdir(parents=True)
    (live / "new.txt").write_text("new\n")
    original_rename = Path.rename

    def fail_staged_publish(source: Path, target: Path) -> Path:
        if source.parent.name.startswith(".adopt-") and target == reference:
            raise OSError("injected publish failure")
        return original_rename(source, target)

    monkeypatch.setattr(Path, "rename", fail_staged_publish)
    applied = apply_adopt(
        repo_root,
        home,
        _plan(
            AdoptResult(
                _drift(repo_root, home, ".config/example", DriftKind.MODIFIED),
                action="copy",
                status=AdoptStatus.PLANNED,
            ),
        ),
    )

    assert applied.ok is False
    assert (reference / "old.txt").read_text() == "old\n"
    assert not (reference / "new.txt").exists()
    assert not list(reference.parent.glob(".example.adopt-backup-*"))


def test_adopt_retains_backup_when_publish_rollback_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root, home = _tracked_repo(tmp_path)
    reference = repo_root / "reference/.config/example"
    reference.mkdir(parents=True)
    (reference / "old.txt").write_text("old\n")
    _commit_all(repo_root)
    live = home / ".config/example"
    live.mkdir(parents=True)
    (live / "new.txt").write_text("new\n")
    original_rename = Path.rename

    def fail_publish_and_rollback(source: Path, target: Path) -> Path:
        if target == reference and (
            source.parent.name.startswith(".adopt-") or source.name == "previous"
        ):
            raise OSError("injected rename failure")
        return original_rename(source, target)

    monkeypatch.setattr(Path, "rename", fail_publish_and_rollback)
    applied = apply_adopt(
        repo_root,
        home,
        _plan(
            AdoptResult(
                _drift(repo_root, home, ".config/example", DriftKind.MODIFIED),
                action="copy",
                status=AdoptStatus.PLANNED,
            ),
        ),
    )

    assert applied.ok is False
    assert "previous reference retained at" in (applied.results[0].error or "")
    backups = list(reference.parent.glob(".*adopt-backup-*/previous"))
    assert len(backups) == 1
    assert (backups[0] / "old.txt").read_text() == "old\n"


def test_adopt_file_rollback_failure_cleans_staged_copy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root, home = _tracked_repo(tmp_path)
    reference = repo_root / "reference/.example"
    reference.write_text("old\n")
    _commit_all(repo_root)
    live = home / ".example"
    live.write_text("new\n")
    original_rename = Path.rename

    def fail_publish_and_rollback(source: Path, target: Path) -> Path:
        if target == reference and (
            source.name.startswith(".adopt-") or source.name == "previous"
        ):
            raise OSError("injected rename failure")
        return original_rename(source, target)

    monkeypatch.setattr(Path, "rename", fail_publish_and_rollback)
    applied = apply_adopt(
        repo_root,
        home,
        _plan(
            AdoptResult(
                _drift(repo_root, home, ".example", DriftKind.MODIFIED),
                action="copy",
                status=AdoptStatus.PLANNED,
            ),
        ),
    )

    assert applied.ok is False
    assert "previous reference retained at" in (applied.results[0].error or "")
    assert not list(reference.parent.glob(".adopt-*"))
    backups = list(reference.parent.glob(".*adopt-backup-*/previous"))
    assert len(backups) == 1
    assert backups[0].read_text() == "old\n"


def test_adopt_apply_refuses_renamed_uncommitted_reference(tmp_path: Path) -> None:
    repo_root, home = _tracked_repo(tmp_path)
    (repo_root / "reference/.old").write_text("content\n")
    _commit_all(repo_root)
    subprocess.run(
        ["git", "-C", str(repo_root), "mv", "reference/.old", "reference/.renamed"],
        check=True,
    )
    (home / ".renamed").write_text("live\n")

    plan = _plan(
        AdoptResult(
            _drift(repo_root, home, ".renamed", DriftKind.MODIFIED),
            action="copy",
            status=AdoptStatus.PLANNED,
        ),
    )
    applied = apply_adopt(repo_root, home, plan)

    assert applied.ok is False
    assert "uncommitted" in (applied.results[0].error or "")


def test_adopt_apply_fails_cleanly_outside_a_git_worktree(tmp_path: Path) -> None:
    repo_root = tmp_path / "plain"
    home = tmp_path / "home"
    (repo_root / "reference").mkdir(parents=True)
    home.mkdir()
    (home / ".gitconfig").write_text("live\n")

    plan = _plan(
        AdoptResult(
            _drift(repo_root, home, ".gitconfig", DriftKind.ONLY_LIVE),
            action="copy",
            status=AdoptStatus.PLANNED,
        ),
    )
    applied = apply_adopt(repo_root, home, plan)

    assert applied.ok is False
    assert applied.results[0].status is AdoptStatus.FAILED
    assert not (repo_root / "reference/.gitconfig").exists()


def test_plan_adopt_marks_unreadable_drift_failed(tmp_path: Path, monkeypatch) -> None:
    from scripts import adopt as adopt_module
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
        adopt_module,
        "inspect_drift",
        lambda *args, **kwargs: DriftReport(
            schema_version=1,
            operation="diff",
            changes=(unreadable,),
            summary={"unreadable": 1},
            profile=HostProfile.FULL,
        ),
    )

    plan = plan_adopt(tmp_path / "repo", tmp_path / "home", "git")

    assert plan.ok is False
    assert "permission denied" in (plan.results[0].error or "")


def test_adopt_refuses_live_paths_under_symlinked_parents(tmp_path: Path) -> None:
    repo_root, home = _tracked_repo(tmp_path)
    (repo_root / "reference/.seed").write_text("seed\n")
    _commit_all(repo_root)
    outside = tmp_path / "volume-config"
    outside.mkdir()
    (outside / "secret.toml").write_text("outside-home content\n")
    (home / ".config").symlink_to(outside)

    plan = _plan(
        AdoptResult(
            _drift(repo_root, home, ".config/secret.toml", DriftKind.ONLY_LIVE),
            action="copy",
            status=AdoptStatus.PLANNED,
        ),
    )
    applied = apply_adopt(repo_root, home, plan)

    assert applied.ok is False
    assert "live parent" in (applied.results[0].error or "")
    assert not (repo_root / "reference/.config").exists()

    inner = home / "real-dir"
    inner.mkdir()
    (inner / "ok.toml").write_text("inside content\n")
    (home / ".linkdir2").symlink_to(inner)
    inner_plan = _plan(
        AdoptResult(
            _drift(repo_root, home, ".linkdir2/ok.toml", DriftKind.ONLY_LIVE),
            action="copy",
            status=AdoptStatus.PLANNED,
        ),
    )
    inner_applied = apply_adopt(repo_root, home, inner_plan)

    assert inner_applied.ok is True
    assert (repo_root / "reference/.linkdir2/ok.toml").read_text() == "inside content\n"
