import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.adopt import (
    AdoptReport,
    AdoptResult,
    AdoptStatus,
    apply_adopt,
)
from scripts.models import Drift, DriftKind, FileKind

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_adopt(home: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    uv_dir = Path(
        subprocess.run(
            ["mise", "which", "uv"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
    ).parent
    uv_cache = subprocess.run(
        [uv_dir / "uv", "cache", "dir"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    environment["HOME"] = str(home)
    environment["XDG_CONFIG_HOME"] = str(home / ".config")
    environment["PATH"] = f"{uv_dir}{os.pathsep}{environment['PATH']}"
    environment["UV_CACHE_DIR"] = uv_cache
    return subprocess.run(
        [sys.executable, "-m", "scripts.adopt", *arguments],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


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

    completed = _run_adopt(home, "hushlogin", "--json")

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    assert document["schema_version"] == 1
    assert document["operation"] == "adopt"
    assert document["apply"] is False
    assert document["ok"] is True
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
