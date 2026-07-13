import json
from pathlib import Path

from scripts.check import inspect_host
from scripts.models import Severity


def test_inspect_host_reports_capabilities_and_their_invalid_transition(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    source = home / "Developer/ipruning/skills"
    source.mkdir(parents=True)
    (home / ".config/skillshare").mkdir(parents=True)
    (home / ".config/skillshare/config.yaml").write_text(
        "sources:\n  skills: ~/Developer/ipruning/skills\n",
    )
    (home / ".config/television").mkdir(parents=True)
    (home / ".config/television/config.toml").write_text("[ui]\n")
    (home / ".gitconfig").write_text(
        "[include]\n  path = ~/.private.gitconfig\n",
    )
    private_gitconfig = home / ".private.gitconfig"
    private_gitconfig.write_text("[user]\n  email = test@example.com\n")
    private_gitconfig.chmod(0o600)
    for directory in ("plugins", "completions", "functions"):
        (repo_root / "generated" / directory).mkdir(parents=True)
        (repo_root / "generated" / directory / "generated.txt").write_text(
            "generated\n",
        )
    zellij_plugins = repo_root / "generated/plugins"
    for plugin_name in ("zellij-sessionizer.wasm", "zjstatus.wasm"):
        (zellij_plugins / plugin_name).write_bytes(b"wasm")

    tools = tmp_path / "tools"
    tools.mkdir()
    skillshare = tools / "skillshare"
    skillshare.write_text(
        '#!/bin/sh\nprintf \'%s\\n\' \'{"summary":{"warnings":0,"errors":0}}\'\n',
    )
    skillshare.chmod(0o755)

    def finder(command: str) -> str:
        return str(skillshare) if command == "skillshare" else f"/tools/{command}"

    healthy = inspect_host(
        repo_root,
        home,
        executable_finder=finder,
        system_name="Darwin",
    )

    assert healthy.ok is True
    assert all(finding.severity is Severity.OK for finding in healthy.findings)

    private_gitconfig.unlink()
    source.rmdir()
    degraded = inspect_host(
        repo_root,
        home,
        executable_finder=finder,
        system_name="Darwin",
    )
    findings = {finding.code: finding for finding in degraded.findings}

    assert degraded.ok is True
    assert findings["git.private_file_missing"].severity is Severity.WARN
    assert findings["skillshare.source_missing"].severity is Severity.WARN
    assert degraded.is_ok(strict=True) is False

    (home / ".gitconfig").write_text(
        "# path = ~/.private.gitconfig\n",
    )
    commented = inspect_host(
        repo_root,
        home,
        executable_finder=finder,
        system_name="Darwin",
    )
    findings = {finding.code: finding for finding in commented.findings}
    assert findings["git.private_include_missing"].severity is Severity.WARN


def test_inspect_host_reports_empty_generated_state_and_skillshare_doctor_errors(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    source = home / "skills"
    source.mkdir(parents=True)
    config_path = home / ".config/skillshare/config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("sources:\n  skills: ~/skills\n")
    for directory in ("plugins", "completions", "functions"):
        generated = repo_root / "generated" / directory
        generated.mkdir(parents=True)
        (generated / ".gitkeep").touch()

    tool_path = tmp_path / "skillshare"
    document = {"summary": {"warnings": 1, "errors": 1}}
    tool_path.write_text(
        f"#!/bin/sh\nprintf '%s\\n' '{json.dumps(document)}'\nexit 1\n",
    )
    tool_path.chmod(0o755)

    def finder(command: str) -> str | None:
        if command == "skillshare":
            return str(tool_path)
        return f"/tools/{command}"

    report = inspect_host(
        repo_root,
        home,
        executable_finder=finder,
        system_name="Darwin",
        profile="full",
    )
    findings = {finding.code: finding for finding in report.findings}

    assert findings["skillshare.doctor_failed"].severity is Severity.WARN
    assert findings["shell.plugins_empty"].severity is Severity.WARN
    assert findings["shell.completions_empty"].severity is Severity.WARN
    assert findings["shell.functions_empty"].severity is Severity.WARN


def test_skillshare_doctor_ignores_terminal_theme_warning(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    source = home / "skills"
    source.mkdir(parents=True)
    config_path = home / ".config/skillshare/config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("sources:\n  skills: ~/skills\n")
    tool_path = tmp_path / "skillshare"
    document = {
        "checks": [
            {"name": "theme", "status": "warning"},
            {"name": "skills_validity", "status": "warning"},
            {"name": "tracked_repos", "status": "warning"},
        ],
        "summary": {"warnings": 3, "errors": 0},
    }
    tool_path.write_text(
        f"#!/bin/sh\nprintf '%s\\n' '{json.dumps(document)}'\n",
    )
    tool_path.chmod(0o755)

    report = inspect_host(
        repo_root,
        home,
        executable_finder=lambda command: (
            str(tool_path) if command == "skillshare" else f"/tools/{command}"
        ),
        system_name="Linux",
    )
    finding = next(
        finding for finding in report.findings if finding.check == "skillshare.doctor"
    )

    assert finding.code == "skillshare.doctor_warnings"
    assert finding.message == "Skillshare doctor reports 2 actionable warning(s)"


def test_linux_lite_check_omits_macos_and_optional_desktop_capabilities(
    tmp_path: Path,
) -> None:
    report = inspect_host(
        tmp_path / "repo",
        tmp_path / "home",
        executable_finder=lambda command: f"/tools/{command}",
        system_name="Linux",
        profile="auto",
    )

    checks = {finding.check for finding in report.findings}
    assert "shell.bash" in checks
    assert "television.config" not in checks
    assert not any(check.startswith("zellij.") for check in checks)
    assert "macos.launchctl" not in checks


def test_inspect_host_reports_invalid_skillshare_yaml(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    config_path = home / ".config/skillshare/config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("sources: [unterminated\n")

    report = inspect_host(
        repo_root,
        home,
        executable_finder=lambda _command: None,
        system_name="Linux",
    )

    findings = {finding.code: finding for finding in report.findings}
    assert findings["skillshare.config_invalid"].severity is Severity.WARN
    assert findings["shell.bash_missing"].severity is Severity.WARN
    assert "macos.launchctl_skipped" not in findings
