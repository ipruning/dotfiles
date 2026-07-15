import json
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import scripts.check as check_module
from scripts.check import inspect_host
from scripts.models import Severity


def test_inspect_host_reports_capabilities_and_their_invalid_transition(
    tmp_path: Path,
    monkeypatch,
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
    private_gitconfig.write_text(
        "[user]\n  name = Test User\n  email = test@example.com\n"
    )
    private_gitconfig.chmod(0o600)
    for directory in ("plugins", "completions", "functions"):
        (repo_root / "generated" / directory).mkdir(parents=True)
        (repo_root / "generated" / directory / "generated.txt").write_text(
            "generated\n",
        )
    runtime_files = (
        "generated/functions/_mise.zsh",
        "generated/functions/_starship.zsh",
        "generated/functions/_atuin.zsh",
        "generated/completions/_codex",
        "generated/plugins/fzf-tab/fzf-tab.plugin.zsh",
        "generated/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh",
        "generated/plugins/fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh",
    )
    for relative_path in runtime_files:
        runtime_path = repo_root / relative_path
        runtime_path.parent.mkdir(parents=True, exist_ok=True)
        runtime_path.write_text("runtime\n")
    for binary_name in ("atuin", "op-cache"):
        binary_path = repo_root / "generated/bin" / binary_name
        binary_path.parent.mkdir(parents=True, exist_ok=True)
        binary_path.write_bytes(b"binary")
        binary_path.chmod(0o755)
    zellij_plugins = repo_root / "generated/plugins"
    wasm_digest = hashlib.sha256(b"wasm").hexdigest()
    monkeypatch.setattr(
        check_module,
        "WASM_SPECS",
        (
            ("zellij-sessionizer", "https://example.invalid/one", wasm_digest),
            ("zjstatus", "https://example.invalid/two", wasm_digest),
        ),
    )
    for plugin_name in ("zellij-sessionizer.wasm", "zjstatus.wasm"):
        (zellij_plugins / plugin_name).write_bytes(b"wasm")

    tools = tmp_path / "tools"
    tools.mkdir()
    skillshare = tools / "skillshare"
    skillshare.write_text(
        '#!/bin/sh\nprintf \'%s\\n\' \'{"summary":{"warnings":0,"errors":0}}\'\n',
    )
    skillshare.chmod(0o755)
    session_health = _session_health_stub(
        tmp_path,
        {
            "installed": True,
            "loaded": True,
            "notification_configured": True,
            "last_snapshot_at": datetime.now(UTC)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "consecutive_delivery_failures": 0,
        },
    )

    available = {
        "git",
        "python",
        "uv",
        "mise",
        "skillshare",
        "tv",
        "launchctl",
        "starship",
        "atuin",
        "codex",
        "macos-session-health",
    }

    def finder(command: str) -> str | None:
        if command not in available:
            return None
        if command == "skillshare":
            return str(skillshare)
        if command == "macos-session-health":
            return str(session_health)
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
    (repo_root / "generated/functions/_mise.zsh").unlink()
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
    assert findings["runtime.function.mise_missing"].severity is Severity.WARN
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


def test_inspect_host_rejects_wasm_with_wrong_checksum(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    target = repo_root / "generated/plugins/example.wasm"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"corrupt")
    expected = hashlib.sha256(b"expected").hexdigest()
    monkeypatch.setattr(
        check_module,
        "WASM_SPECS",
        (("example", "https://example.invalid/example", expected),),
    )

    report = inspect_host(
        repo_root,
        home,
        executable_finder=lambda _command: None,
        system_name="Darwin",
        profile="full",
    )
    findings = {finding.code: finding for finding in report.findings}

    finding = findings["zellij.example.wasm_checksum_mismatch"]
    assert finding.severity is Severity.WARN
    assert finding.path == target


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


def test_skillshare_doctor_ignores_non_health_warnings(tmp_path: Path) -> None:
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
            {"name": "git_status", "status": "warning"},
            {
                "name": "skills_validity",
                "status": "warning",
                "details": ["extras"],
            },
            {"name": "tracked_repos", "status": "warning"},
        ],
        "summary": {"warnings": 4, "errors": 0},
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
    assert finding.message == "Skillshare doctor reports 1 actionable warning(s)"


def test_skillshare_doctor_keeps_real_skill_validity_warning(tmp_path: Path) -> None:
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
            {
                "name": "skills_validity",
                "status": "warning",
                "details": ["broken-skill"],
            },
        ],
        "summary": {"warnings": 1, "errors": 0},
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
    assert finding.message == "Skillshare doctor reports 1 actionable warning(s)"


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


def test_linux_lite_check_requires_only_git_and_mise_and_reports_legacy_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    legacy_bin = repo_root / "modules/bin"
    legacy_bin.mkdir(parents=True)
    monkeypatch.setenv("PATH", f"{legacy_bin}:/usr/bin:/bin")

    report = inspect_host(
        repo_root,
        home,
        executable_finder=lambda command: (
            f"/tools/{command}" if command in {"git", "mise"} else None
        ),
        system_name="Linux",
    )
    findings = {finding.check: finding for finding in report.findings}

    executable_checks = {
        finding.check
        for finding in report.findings
        if finding.check.startswith("executable.")
    }
    assert executable_checks == {
        "executable.git",
        "executable.mise",
        "executable.skillshare",
    }
    assert findings["shell.repo_commands"].severity is Severity.WARN
    assert findings["shell.repo_commands"].path == legacy_bin

    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    clean = inspect_host(
        repo_root,
        home,
        executable_finder=lambda command: (
            f"/tools/{command}" if command in {"git", "mise"} else None
        ),
        system_name="Linux",
    )
    clean_finding = next(
        finding for finding in clean.findings if finding.check == "shell.repo_commands"
    )
    assert clean_finding.severity is Severity.OK


def test_private_git_identity_requires_name_and_email_and_detects_transition(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    home.mkdir()
    (home / ".gitconfig").write_text("[include]\n  path = ~/.private.gitconfig\n")
    private_config = home / ".private.gitconfig"
    private_config.write_text(
        "[user]\n  name = Test User\n  email = test@example.com\n"
    )
    private_config.chmod(0o600)

    healthy = inspect_host(
        repo_root,
        home,
        executable_finder=lambda command: (
            f"/tools/{command}" if command in {"git", "mise"} else None
        ),
        system_name="Linux",
    )
    healthy_identity = next(
        finding
        for finding in healthy.findings
        if finding.check == "git.private_identity"
    )
    assert healthy_identity.severity is Severity.OK

    private_config.write_text("[user]\n  email = test@example.com\n")
    degraded = inspect_host(
        repo_root,
        home,
        executable_finder=lambda command: (
            f"/tools/{command}" if command in {"git", "mise"} else None
        ),
        system_name="Linux",
    )
    degraded_identity = next(
        finding
        for finding in degraded.findings
        if finding.check == "git.private_identity"
    )
    assert degraded_identity.severity is Severity.WARN
    assert degraded_identity.code == "git.private_identity_missing"


def test_private_git_identity_accepts_complete_conditional_includes(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    identity_config = home / ".config/git/personal.gitconfig"
    identity_config.parent.mkdir(parents=True)
    identity_config.write_text(
        "[user]\n  name = Test User\n  email = test@example.com\n"
    )
    private_config = home / ".private.gitconfig"
    private_config.write_text(
        '[includeIf "hasconfig:remote.*.url:https://example.com/**"]\n'
        "  path = ~/.config/git/personal.gitconfig\n"
    )
    private_config.chmod(0o600)

    healthy = inspect_host(
        repo_root,
        home,
        executable_finder=lambda command: (
            f"/tools/{command}" if command in {"git", "mise"} else None
        ),
        system_name="Linux",
    )
    healthy_identity = next(
        finding
        for finding in healthy.findings
        if finding.check == "git.private_identity"
    )
    assert healthy_identity.severity is Severity.OK

    identity_config.write_text("[user]\n  name = Test User\n")
    degraded = inspect_host(
        repo_root,
        home,
        executable_finder=lambda command: (
            f"/tools/{command}" if command in {"git", "mise"} else None
        ),
        system_name="Linux",
    )
    degraded_identity = next(
        finding
        for finding in degraded.findings
        if finding.check == "git.private_identity"
    )
    assert degraded_identity.severity is Severity.WARN


def _session_health_stub(tmp_path: Path, record: dict) -> Path:
    executable = tmp_path / "bin/macos-session-health"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text(
        f"#!/bin/sh\nprintf '%s\\n' {json.dumps(json.dumps([record]))}\n",
    )
    executable.chmod(0o755)
    return executable


def _session_health_codes(tmp_path: Path, record: dict) -> dict[str, str]:
    executable = _session_health_stub(tmp_path, record)

    def finder(command: str) -> str | None:
        if command == "macos-session-health":
            return str(executable)
        return (
            f"/tools/{command}" if command in {"git", "python", "uv", "mise"} else None
        )

    report = inspect_host(
        tmp_path / "repo",
        tmp_path / "home",
        executable_finder=finder,
        system_name="Darwin",
        profile="macos",
    )
    return {
        finding.check: finding.code
        for finding in report.findings
        if finding.check.startswith("session_health.")
    }


def test_session_health_probe_reports_healthy_agent(tmp_path: Path) -> None:
    (tmp_path / "home").mkdir()
    now = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    codes = _session_health_codes(
        tmp_path,
        {
            "installed": True,
            "loaded": True,
            "notification_configured": True,
            "last_snapshot_at": now,
            "consecutive_delivery_failures": 0,
        },
    )

    assert codes["session_health.agent"] == "session_health.agent_ready"
    assert codes["session_health.snapshot"] == "session_health.snapshot_recent"
    assert codes["session_health.notifications"] == "session_health.notifications_ready"


def test_session_health_probe_reports_silent_death_modes(tmp_path: Path) -> None:
    (tmp_path / "home").mkdir()
    codes = _session_health_codes(
        tmp_path,
        {
            "installed": True,
            "loaded": False,
            "notification_configured": True,
            "last_snapshot_at": "2026-01-01T00:00:00Z",
            "consecutive_delivery_failures": 5,
        },
    )

    assert codes["session_health.agent"] == "session_health.agent_down"
    assert codes["session_health.snapshot"] == "session_health.snapshot_stale"
    assert (
        codes["session_health.notifications"] == "session_health.notifications_failing"
    )


def test_session_health_probe_survives_naive_timestamp_and_failed_status(
    tmp_path: Path,
) -> None:
    (tmp_path / "home").mkdir()
    codes = _session_health_codes(
        tmp_path,
        {
            "installed": True,
            "loaded": True,
            "notification_configured": True,
            "last_snapshot_at": "2026-07-15T10:00:00",
            "consecutive_delivery_failures": 0,
        },
    )
    assert codes["session_health.snapshot"] == "session_health.snapshot_stale"

    executable = tmp_path / "bin/failing-session-health"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text('#!/bin/sh\necho "launchctl exploded" >&2\nexit 7\n')
    executable.chmod(0o755)
    report = inspect_host(
        tmp_path / "repo",
        tmp_path / "home",
        executable_finder=lambda command: (
            str(executable)
            if command == "macos-session-health"
            else f"/tools/{command}"
        ),
        system_name="Darwin",
        profile="macos",
    )
    finding = next(
        finding
        for finding in report.findings
        if finding.check == "session_health.agent"
    )

    assert finding.code == "session_health.status_unavailable"
    assert "launchctl exploded" in finding.message


def test_session_health_probe_treats_absent_tool_as_optional_warning(
    tmp_path: Path,
) -> None:
    (tmp_path / "home").mkdir()
    report = inspect_host(
        tmp_path / "repo",
        tmp_path / "home",
        executable_finder=lambda command: (
            f"/tools/{command}" if command in {"git", "python", "uv", "mise"} else None
        ),
        system_name="Darwin",
        profile="macos",
    )
    finding = next(
        finding
        for finding in report.findings
        if finding.check == "session_health.agent"
    )

    assert finding.severity is Severity.WARN
    assert finding.code == "session_health.missing"
    assert report.ok is True


def test_bash_integration_recognizes_symlinked_checkout(tmp_path: Path) -> None:
    checkout = tmp_path / "workspace/dotfiles"
    (checkout / "modules/bash").mkdir(parents=True)
    (checkout / "modules/bash/init.bash").write_text("export READY=1\n")
    repo_link = tmp_path / "dotfiles"
    repo_link.symlink_to(checkout)
    home = tmp_path / "home"
    home.mkdir()
    module_path = checkout / "modules/bash/init.bash"
    (home / ".bashrc").write_text(
        f"# >>> dotfiles linux-lite >>>\n. {module_path}\n# <<< dotfiles linux-lite <<<\n",
    )

    report = inspect_host(
        repo_link,
        home,
        executable_finder=lambda command: (
            f"/tools/{command}" if command in {"git", "mise"} else None
        ),
        system_name="Linux",
    )
    bash_finding = next(
        finding for finding in report.findings if finding.check == "shell.bash"
    )

    assert bash_finding.severity is Severity.OK
    assert bash_finding.code == "shell.bash_ready"


def test_private_git_identity_accepts_conditional_include_sections_with_spaces(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    identity_config = home / ".config/git/personal.gitconfig"
    identity_config.parent.mkdir(parents=True)
    identity_config.write_text(
        "[user]\n  name = Test User\n  email = test@example.com\n"
    )
    private_config = home / ".private.gitconfig"
    private_config.write_text(
        '[includeIf "gitdir:~/My Projects/"]\n'
        "  path = ~/.config/git/personal.gitconfig\n"
    )
    private_config.chmod(0o600)

    healthy = inspect_host(
        repo_root,
        home,
        executable_finder=lambda command: (
            f"/tools/{command}" if command in {"git", "mise"} else None
        ),
        system_name="Linux",
    )
    healthy_identity = next(
        finding
        for finding in healthy.findings
        if finding.check == "git.private_identity"
    )
    assert healthy_identity.severity is Severity.OK

    identity_config.write_text("[user]\n  name = Test User\n")
    degraded = inspect_host(
        repo_root,
        home,
        executable_finder=lambda command: (
            f"/tools/{command}" if command in {"git", "mise"} else None
        ),
        system_name="Linux",
    )
    degraded_identity = next(
        finding
        for finding in degraded.findings
        if finding.check == "git.private_identity"
    )
    assert degraded_identity.severity is Severity.WARN


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


def test_inspect_host_reports_generated_binaries_without_an_owner(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    generated_bin = repo_root / "generated/bin"
    generated_bin.mkdir(parents=True)
    (generated_bin / ".gitkeep").touch()
    custom_binary = generated_bin / "custom-tool"
    custom_binary.write_bytes(b"binary")

    report = inspect_host(
        repo_root,
        home,
        executable_finder=lambda _command: None,
        system_name="Darwin",
        profile="full",
    )
    findings = {finding.code: finding for finding in report.findings}

    finding = findings["runtime.binary.custom-tool_unowned"]
    assert finding.severity is Severity.WARN
    assert finding.path == custom_binary
    assert finding.action is not None
    assert "build or install owner" in finding.action


def test_inspect_host_reports_stale_owned_completion_when_tool_is_missing(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    stale = repo_root / "generated/completions/_bootdev"
    stale.parent.mkdir(parents=True)
    stale.write_text("stale\n")

    report = inspect_host(
        repo_root,
        home,
        executable_finder=lambda _command: None,
        system_name="Darwin",
        profile="full",
    )
    findings = {finding.code: finding for finding in report.findings}

    finding = findings["runtime.completion.bootdev_stale"]
    assert finding.severity is Severity.WARN
    assert finding.path == stale


def test_inspect_host_rejects_empty_or_non_executable_owned_binary(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    generated_bin = repo_root / "generated/bin"
    generated_bin.mkdir(parents=True)
    (generated_bin / "atuin").touch()
    op_cache = generated_bin / "op-cache"
    op_cache.write_text("binary\n")
    op_cache.chmod(0o644)

    report = inspect_host(
        repo_root,
        home,
        executable_finder=lambda _command: None,
        system_name="Darwin",
        profile="full",
    )
    findings = {finding.code: finding for finding in report.findings}

    assert findings["runtime.binary.atuin_invalid"].severity is Severity.WARN
    assert findings["runtime.binary.op-cache_invalid"].severity is Severity.WARN
