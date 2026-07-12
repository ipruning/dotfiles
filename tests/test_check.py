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
    zellij_plugins = repo_root / "reference/.config/zellij/plugins"
    zellij_plugins.mkdir(parents=True)
    for plugin_name in ("zellij-sessionizer.wasm", "zjstatus.wasm"):
        (zellij_plugins / plugin_name).write_bytes(b"wasm")

    def finder(command: str) -> str:
        return f"/tools/{command}"

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
    assert findings["macos.launchctl_skipped"].severity is Severity.SKIPPED
