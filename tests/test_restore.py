import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.models import Drift, DriftKind, FileKind
from scripts.restore import (
    RestoreReport,
    RestoreResult,
    RestoreStatus,
    apply_restore,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_restore(home: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
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
        [sys.executable, "-m", "scripts.restore", *arguments],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_restore_defaults_to_a_read_only_application_plan(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    completed = _run_restore(home, "hushlogin", "--json")

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    assert document["schema_version"] == 1
    assert document["operation"] == "restore"
    assert document["application"] == "hushlogin"
    assert document["apply"] is False
    assert document["ok"] is True
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


def test_restore_apply_backs_up_live_file_and_links_reference(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    live_path = home / ".hushlogin"
    live_path.write_text("host-specific\n")

    preview = _run_restore(home, "hushlogin", "--dry-run", "--json")
    assert preview.returncode == 0
    assert live_path.read_text() == "host-specific\n"

    applied = _run_restore(home, "hushlogin", "--apply", "--json")

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

    converged = _run_restore(home, "hushlogin", "--json")
    assert converged.returncode == 0
    assert json.loads(converged.stdout)["changes"] == []


def test_restore_rejects_invalid_scope_without_changing_home(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    conflicting = _run_restore(
        home,
        "hushlogin",
        "--apply",
        "--dry-run",
    )
    unknown = _run_restore(home, "not-a-configured-application", "--json")

    assert conflicting.returncode == 2
    assert "mutually exclusive" in conflicting.stderr
    assert unknown.returncode == 1
    assert unknown.stdout == ""
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
