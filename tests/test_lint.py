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


def test_inspect_repository_warns_when_checkout_is_not_home_dotfiles(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    repo_root = home / "dotfiles"
    (repo_root / "reference").mkdir(parents=True)
    (repo_root / "mackup/applications").mkdir(parents=True)
    (repo_root / "mackup/mackup.cfg").write_text(
        "[storage]\nengine = file_system\npath = dotfiles\n"
        "directory = reference\n[applications_to_sync]\n",
    )
    (repo_root / "tool.sh").write_text("plugin=~/dotfiles/generated/plugin.wasm\n")

    installed = inspect_repository(repo_root, home)
    installed_finding = next(
        finding
        for finding in installed.findings
        if finding.code == "path.dotfiles_root"
    )
    assert installed_finding.severity is Severity.OK

    checkout = tmp_path / "checkout"
    repo_root.rename(checkout)
    relocated = inspect_repository(checkout, home)
    relocated_finding = next(
        finding
        for finding in relocated.findings
        if finding.code == "path.dotfiles_root"
    )

    assert relocated_finding.severity is Severity.WARN
    assert relocated.ok is True
    assert relocated.is_ok(strict=True) is False


def test_inspect_repository_allows_only_declared_optional_reference_candidates(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    (repo_root / "reference").mkdir(parents=True)
    (repo_root / "reference/.required").write_text("configured\n")
    (repo_root / "mackup/applications").mkdir(parents=True)
    mapping = repo_root / "mackup/applications/example.cfg"
    mapping.write_text(
        "[application]\nname = example\n"
        "[configuration_files]\n.required\n.optional\n"
        "[dotfiles_optional_reference_files]\n.optional\n",
    )
    (repo_root / "mackup/mackup.cfg").write_text(
        "[storage]\nengine = file_system\npath = dotfiles\n"
        "directory = reference\n[applications_to_sync]\nexample\n",
    )

    declared = inspect_repository(repo_root, home)
    assert declared.ok is True
    assert "mackup.reference_missing" not in {
        finding.code for finding in declared.findings
    }

    mapping.write_text(
        "[application]\nname = example\n"
        "[configuration_files]\n.required\n.optional\n"
        "[dotfiles_optional_reference_files]\n.not-mapped\n",
    )
    invalid = inspect_repository(repo_root, home)
    codes = {finding.code for finding in invalid.findings}

    assert "mackup.reference_missing" in codes
    assert "mackup.optional_reference_unmapped" in codes


def test_linux_repository_lint_skips_macos_only_paths(tmp_path: Path) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    (repo_root / "reference").mkdir(parents=True)
    (repo_root / "mackup/applications").mkdir(parents=True)
    (repo_root / "mackup/mackup.cfg").write_text(
        "[storage]\nengine = file_system\npath = dotfiles\n"
        "directory = reference\n[applications_to_sync]\n",
    )
    (repo_root / "tool.sh").write_text(
        "app=/Applications/ChatGPT.app\n"
        "brew=/opt/homebrew/bin/brew\n"
        "portable=/usr/local/bin/example\n",
    )

    report = inspect_repository(repo_root, home, system_name="Linux")
    path_findings = [
        finding for finding in report.findings if finding.code.startswith("path.")
    ]

    assert all(finding.severity is not Severity.WARN for finding in path_findings)
    assert {finding.code for finding in path_findings} == {
        "path.platform_skipped",
        "path.toolchain",
    }
