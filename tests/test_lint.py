import subprocess
from pathlib import Path

import pytest

from tests.conftest import mackup_cfg

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
    (repo_root / "mackup/mackup.cfg").write_text(mackup_cfg("example\n"))
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
    assert degraded.is_ok() is False


def test_inspect_repository_ignores_absolute_paths_inside_urls(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    (repo_root / "reference").mkdir(parents=True)
    (repo_root / "mackup/applications").mkdir(parents=True)
    (repo_root / "mackup/mackup.cfg").write_text(mackup_cfg())
    script = repo_root / "tool.sh"
    script.write_text(
        "curl https://mirror.example/home/pkg/file.tar\n"
        "docs=https://example.com/Users/guide\n",
    )

    clean = inspect_repository(repo_root, home)
    assert "path.absolute_home" not in {finding.code for finding in clean.findings}

    script.write_text(
        "helper=/home/someone/private/tool https://example.com/home/pkg\n",
    )
    mixed = inspect_repository(repo_root, home)
    absolute_findings = [
        finding for finding in mixed.findings if finding.code == "path.absolute_home"
    ]

    assert len(absolute_findings) == 1
    assert "/home/someone/private/tool" in absolute_findings[0].message


def test_inspect_repository_reports_only_tracked_dangling_symlinks(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    (repo_root / "reference").mkdir(parents=True)
    (repo_root / "mackup/applications").mkdir(parents=True)
    (repo_root / "mackup/mackup.cfg").write_text(mackup_cfg())
    tracked_link = repo_root / "reference/.broken"
    tracked_link.symlink_to(repo_root / "reference/.target")
    venv_link = repo_root / ".venv/bin/python"
    venv_link.parent.mkdir(parents=True)
    venv_link.symlink_to(tmp_path / "removed-interpreter")
    (repo_root / ".gitignore").write_text(".venv/\n")
    subprocess.run(["git", "init", "-q", str(repo_root)], check=True)
    subprocess.run(["git", "-C", str(repo_root), "add", "."], check=True)

    dangling = inspect_repository(repo_root, home)
    symlink_findings = [
        finding
        for finding in dangling.findings
        if finding.code == "repository.dangling_symlink"
    ]

    assert len(symlink_findings) == 1
    assert symlink_findings[0].path == tracked_link

    (repo_root / "reference/.target").write_text("configured\n")
    repaired = inspect_repository(repo_root, home)

    assert "repository.dangling_symlink" not in {
        finding.code for finding in repaired.findings
    }


def test_inspect_repository_rejects_tracked_private_generated_and_legacy_files(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    (repo_root / "mackup/applications").mkdir(parents=True)
    (repo_root / "reference").mkdir()
    (repo_root / "mackup/mackup.cfg").write_text(mackup_cfg())
    private_file = repo_root / "reference/.machine.private.zsh"
    private_file.write_text("TOKEN=secret\n")
    generated_file = repo_root / "generated/.gitkeep"
    generated_file.parent.mkdir()
    generated_file.write_text("stale\n")
    legacy_file = repo_root / "notes.txt"
    legacy_file.write_text(
        "run mise run sync\n"
        "run mise run update -- --dry-run\n"
        "run modules/bin/ss status\n"
        "run modules/bin/ssh-helper status\n"
    )
    subprocess.run(["git", "init", "-q", str(repo_root)], check=True)
    subprocess.run(["git", "-C", str(repo_root), "add", "."], check=True)

    report = inspect_repository(repo_root, home)
    codes = {finding.code for finding in report.findings}

    assert "repository.private_tracked" in codes
    assert "repository.generated_tracked" in codes
    assert "repository.legacy_reference" in codes
    legacy_findings = [
        finding
        for finding in report.findings
        if finding.code == "repository.legacy_reference"
    ]
    assert len(legacy_findings) == 2
    assert "mise run sync" in legacy_findings[0].message


def test_inspect_repository_warns_when_checkout_is_not_home_dotfiles(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    repo_root = home / "dotfiles"
    (repo_root / "reference").mkdir(parents=True)
    (repo_root / "mackup/applications").mkdir(parents=True)
    (repo_root / "mackup/mackup.cfg").write_text(mackup_cfg())
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
    assert relocated.is_ok() is True
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
    (repo_root / "mackup/mackup.cfg").write_text(mackup_cfg("example\n"))

    declared = inspect_repository(repo_root, home)
    assert declared.is_ok() is True
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
    (repo_root / "mackup/mackup.cfg").write_text(mackup_cfg())
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


def test_inspect_repository_checks_paths_under_reference_library(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    settings = repo_root / "reference/Library/Application Support/App/settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text('{"tool": "/Users/someone/private/tool"}\n')
    (repo_root / "mackup/applications").mkdir(parents=True)
    (repo_root / "mackup/mackup.cfg").write_text(mackup_cfg())

    report = inspect_repository(repo_root, home, system_name="Darwin")
    finding = next(
        finding for finding in report.findings if finding.code == "path.absolute_home"
    )

    assert finding.severity is Severity.ERROR
    assert finding.path == settings


def test_linux_lint_treats_skillshare_source_paths_as_optional(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    config = repo_root / "reference/.config/skillshare/config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "sources:\n"
        "  skills: ~/Developer/ipruning/skills\n"
        "  extras: ~/Developer/ipruning/skills/extras\n"
        "extras: []\n"
    )
    (repo_root / "mackup/applications").mkdir(parents=True)
    (repo_root / "mackup/mackup.cfg").write_text(mackup_cfg())

    report = inspect_repository(repo_root, home, system_name="Linux")
    source_findings = [
        finding
        for finding in report.findings
        if finding.path == config and finding.code.startswith("path.")
    ]

    assert len(source_findings) == 2
    assert all(
        finding.code == "path.optional_compatibility"
        and finding.severity is Severity.OK
        for finding in source_findings
    )


def test_inspect_repository_rejects_pruning_skillshare_extra_modes(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    (repo_root / "reference/.config/skillshare").mkdir(parents=True)
    (repo_root / "reference/.config/skillshare/config.yaml").write_text(
        "extras:\n- name: codex\n  targets:\n  - path: ~/.codex\n    mode: merge\n",
    )
    (repo_root / "mackup/applications").mkdir(parents=True)
    (repo_root / "mackup/mackup.cfg").write_text(mackup_cfg())

    unsafe = inspect_repository(repo_root, home)
    unsafe_finding = next(
        finding
        for finding in unsafe.findings
        if finding.code == "skillshare.extra_mode_unsafe"
    )
    assert unsafe_finding.severity is Severity.ERROR

    (repo_root / "reference/.config/skillshare/config.yaml").write_text(
        "extras:\n- name: codex\n  targets:\n  - path: ~/.codex\n    mode: copy\n",
    )
    safe = inspect_repository(repo_root, home)
    safe_finding = next(
        finding
        for finding in safe.findings
        if finding.code == "skillshare.extra_modes_safe"
    )
    assert safe_finding.severity is Severity.OK


def test_inspect_repository_rejects_unselected_mackup_mappings(tmp_path: Path) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    (repo_root / "reference").mkdir(parents=True)
    (repo_root / "reference/.example").write_text("configured\n")
    (repo_root / "mackup/applications").mkdir(parents=True)
    (repo_root / "mackup/applications/example.cfg").write_text(
        "[application]\nname = example\n[configuration_files]\n.example\n",
    )
    (repo_root / "mackup/applications/parked.cfg").write_text(
        "[application]\nname = parked\n[configuration_files]\n.parked\n",
    )
    (repo_root / "mackup/mackup.cfg").write_text(mackup_cfg("example\n"))

    orphaned = inspect_repository(repo_root, home)
    orphan_finding = next(
        finding
        for finding in orphaned.findings
        if finding.code == "mackup.mapping_unused"
    )

    assert orphan_finding.severity is Severity.ERROR
    assert orphan_finding.path == repo_root / "mackup/applications/parked.cfg"
    assert orphaned.is_ok() is False

    (repo_root / "mackup/applications/parked.cfg").unlink()
    clean = inspect_repository(repo_root, home)

    assert "mackup.mapping_unused" not in {finding.code for finding in clean.findings}


@pytest.mark.parametrize(
    "extras_yaml",
    [
        "extras:\n- codex\n",
        "extras:\n- name: codex\n  targets: ~/.codex\n",
        "extras:\n- name: codex\n  targets:\n  - ~/.codex\n",
    ],
)
def test_inspect_repository_rejects_malformed_skillshare_extras_shapes(
    tmp_path: Path,
    extras_yaml: str,
) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    (repo_root / "reference/.config/skillshare").mkdir(parents=True)
    (repo_root / "reference/.config/skillshare/config.yaml").write_text(extras_yaml)
    (repo_root / "mackup/applications").mkdir(parents=True)
    (repo_root / "mackup/mackup.cfg").write_text(mackup_cfg())

    report = inspect_repository(repo_root, home)
    codes = {finding.code for finding in report.findings}

    assert "skillshare.config_invalid" in codes
    assert "skillshare.extra_modes_safe" not in codes
    assert report.is_ok() is False


def test_full_home_rule_fires_only_for_its_keyed_zellij_file(tmp_path: Path) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    keyed = repo_root / "reference/.config/zellij/config.kdl"
    keyed.parent.mkdir(parents=True)
    keyed.write_text('session_dir "/Users/stranger/work"\n')
    other = repo_root / "reference/.config/other.conf"
    other.write_text('session_dir "/Users/stranger/work"\n')
    (repo_root / "mackup/applications").mkdir(parents=True)
    (repo_root / "mackup/mackup.cfg").write_text(mackup_cfg())

    report = inspect_repository(repo_root, home, system_name="Darwin")
    by_path = {}
    for finding in report.findings:
        if finding.code in {"path.full_home_required", "path.absolute_home"}:
            by_path[finding.path] = finding

    assert by_path[keyed].code == "path.full_home_required"
    assert by_path[keyed].severity is Severity.WARN
    assert by_path[other].code == "path.absolute_home"
    assert by_path[other].severity is Severity.ERROR


def test_inspect_repository_reports_git_inventory_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    (repo_root / "mackup/applications").mkdir(parents=True)
    (repo_root / "mackup/mackup.cfg").write_text(mackup_cfg())

    monkeypatch.setattr(
        "scripts.lint.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=("git", "ls-files"),
            returncode=7,
            stdout=b"",
            stderr=b"injected git failure",
        ),
    )

    report = inspect_repository(repo_root, home)
    finding = next(
        finding
        for finding in report.findings
        if finding.code == "repository.tracked_files_unavailable"
    )
    assert finding.severity is Severity.ERROR
    assert "injected git failure" in finding.message
    assert report.is_ok() is False
