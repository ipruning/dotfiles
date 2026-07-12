import subprocess
from pathlib import Path

import pytest

from scripts.lint import inspect_repository
from scripts.models import Severity


@pytest.mark.parametrize(
    "absolute_path",
    [
        "/Users/someone/private/tool",
        "/home/someone/private/tool",
        "/root/private/tool",
    ],
)
def test_inspect_repository_checks_paths_and_mapping_state(
    tmp_path: Path,
    absolute_path: str,
) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    (repo_root / "reference").mkdir(parents=True)
    (repo_root / "reference/.example").write_text("configured\n")
    (repo_root / "mackup/applications").mkdir(parents=True)
    (repo_root / "mackup/applications/example.cfg").write_text(
        "[application]\nname = example\n[configuration_files]\n.example\n.missing\n",
    )
    (repo_root / "mackup/mackup.cfg").write_text(
        "[storage]\nengine = file_system\npath = dotfiles\n"
        "directory = reference\n"
        "[applications_to_sync]\nexample\n",
    )
    script = repo_root / "tool.sh"
    script.write_text(f"helper={absolute_path}\n")

    report = inspect_repository(repo_root, home)
    findings = {finding.code: finding for finding in report.findings}

    assert findings["path.absolute_home"].severity is Severity.ERROR
    assert "mackup.application_empty" not in findings
    assert findings["mackup.reference_missing"].severity is Severity.ERROR

    (repo_root / "reference/.example").unlink()
    degraded = inspect_repository(repo_root, home)
    findings = {finding.code: finding for finding in degraded.findings}

    assert findings["mackup.application_empty"].severity is Severity.ERROR
    assert degraded.ok is False


def test_inspect_repository_rejects_tracked_private_generated_and_legacy_files(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    (repo_root / "mackup/applications").mkdir(parents=True)
    (repo_root / "reference").mkdir()
    (repo_root / "mackup/mackup.cfg").write_text(
        "[storage]\nengine = file_system\npath = dotfiles\n"
        "directory = reference\n[applications_to_sync]\n",
    )
    private_file = repo_root / "reference/.machine.private.zsh"
    private_file.write_text("TOKEN=secret\n")
    generated_file = repo_root / "generated/stale.txt"
    generated_file.parent.mkdir()
    generated_file.write_text("stale\n")
    legacy_file = repo_root / "notes.txt"
    legacy_file.write_text("run mise run restore\n")
    subprocess.run(["git", "init", "-q", str(repo_root)], check=True)
    subprocess.run(["git", "-C", str(repo_root), "add", "."], check=True)

    report = inspect_repository(repo_root, home)
    codes = {finding.code for finding in report.findings}

    assert "repository.private_tracked" in codes
    assert "repository.generated_tracked" in codes
    assert "repository.legacy_reference" in codes
