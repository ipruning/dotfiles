import json
import hashlib
import subprocess
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
    canonical_mise = home / ".local/bin/mise"
    canonical_mise.parent.mkdir(parents=True)
    canonical_mise.write_text("#!/bin/sh\nexit 0\n")
    canonical_mise.chmod(0o755)
    for directory in ("plugins", "completions", "functions"):
        (repo_root / "generated" / directory).mkdir(parents=True)
        marker = ".gitkeep" if directory == "plugins" else "generated.txt"
        (repo_root / "generated" / directory / marker).write_text(
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
    (repo_root / "generated/functions/_mise.zsh").write_text(
        f"command {canonical_mise}\n",
    )
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
    bag_mode = _bag_mode_stub(
        tmp_path,
        {
            "enabled": True,
            "phase": "running",
            "recovery_required": False,
            "brightness_pending": False,
        },
        version="2.6.0",
    )
    _write_module_source(
        repo_root / "modules/bag-mode/bag-mode",
        'VERSION="2.6.0"',
    )
    maxfiles = _maxfiles_stub(
        tmp_path,
        {
            "installed": True,
            "binary": True,
            "loaded": True,
            "soft_limit": "8192",
            "hard_limit": "65536",
        },
    )
    _write_module_source(
        repo_root / "modules/macos-maxfiles/macos-maxfiles",
        'SOFT_LIMIT="8192"\nHARD_LIMIT="65536"',
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
        "bag-mode",
        "macos-maxfiles",
    }

    def finder(command: str) -> str | None:
        if command not in available:
            return None
        if command == "skillshare":
            return str(skillshare)
        if command == "macos-session-health":
            return str(session_health)
        if command == "bag-mode":
            return str(bag_mode)
        if command == "macos-maxfiles":
            return str(maxfiles)
        if command == "mise":
            return str(canonical_mise)
        return f"/tools/{command}"

    healthy = inspect_host(
        repo_root,
        home,
        executable_finder=finder,
        system_name="Darwin",
    )

    assert healthy.is_ok() is True
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

    assert degraded.is_ok() is True
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


def test_inspect_host_reports_duplicate_mise_and_stale_runtime_binding(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    canonical = home / ".local/bin/mise"
    alternate = tmp_path / "package-manager/bin/mise"
    generated = repo_root / "generated/functions/_mise.zsh"
    for executable in (canonical, alternate):
        executable.parent.mkdir(parents=True)
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)
    shims = home / ".local/share/mise/shims"
    shims.mkdir(parents=True)
    python_shim = shims / "python3"
    python_shim.symlink_to(alternate)
    generated.parent.mkdir(parents=True)
    generated.write_text(f"command {alternate}\n")

    def alternate_finder(command: str) -> str | None:
        return str(alternate) if command == "mise" else f"/tools/{command}"

    conflicted = inspect_host(
        repo_root,
        home,
        executable_finder=alternate_finder,
        system_name="Linux",
        profile="full",
    )
    findings = {finding.check: finding for finding in conflicted.findings}

    assert findings["mise.canonical"].severity is Severity.OK
    assert findings["mise.installations"].code == "mise.installations_multiple"
    assert findings["mise.installations"].severity is Severity.WARN
    assert findings["mise.shims"].code == "mise.shims_stale"
    assert findings["mise.shims"].severity is Severity.WARN
    assert (
        findings["runtime.function.mise_binding"].code
        == "runtime.function.mise_binding_mismatch"
    )

    python_shim.unlink()
    python_shim.symlink_to(canonical)
    alternate.unlink()
    generated.write_text(f"command {canonical}\n")
    repaired = inspect_host(
        repo_root,
        home,
        executable_finder=lambda command: (
            str(canonical) if command == "mise" else f"/tools/{command}"
        ),
        system_name="Linux",
        profile="full",
    )
    findings = {finding.check: finding for finding in repaired.findings}

    assert findings["mise.installations"].code == "mise.installations_single"
    assert findings["mise.installations"].severity is Severity.OK
    assert findings["mise.shims"].code == "mise.shims_ready"
    assert findings["mise.shims"].severity is Severity.OK
    assert (
        findings["runtime.function.mise_binding"].code
        == "runtime.function.mise_binding_ready"
    )

    canonical.unlink()
    missing = inspect_host(
        repo_root,
        home,
        executable_finder=lambda command: (
            str(canonical) if command == "mise" else f"/tools/{command}"
        ),
        system_name="Linux",
        profile="full",
    )
    missing_canonical = next(
        finding for finding in missing.findings if finding.check == "mise.canonical"
    )
    assert missing_canonical.code == "mise.canonical_missing_or_invalid"
    assert missing_canonical.severity is Severity.WARN
    stale_runtime = next(
        finding
        for finding in missing.findings
        if finding.check == "runtime.function.mise"
    )
    assert stale_runtime.code == "runtime.function.mise_stale"
    assert stale_runtime.severity is Severity.WARN


def test_mise_installation_scan_finds_an_alternate_later_on_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    canonical = home / ".local/bin/mise"
    alternate = tmp_path / "package-manager/bin/mise"
    for executable in (canonical, alternate):
        executable.parent.mkdir(parents=True)
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)
    monkeypatch.setenv(
        "PATH",
        f"{canonical.parent}:{alternate.parent}",
    )
    monkeypatch.setattr(check_module, "MISE_COMMON_LOCATIONS", ())

    findings = check_module._mise_installation_findings(
        home,
        executable_finder=lambda _command: str(canonical),
        scan_host_path=True,
    )

    assert findings[1].code == "mise.installations_multiple"
    assert findings[1].path == alternate

    alternate.unlink()
    repaired = check_module._mise_installation_findings(
        home,
        executable_finder=lambda _command: str(canonical),
        scan_host_path=True,
    )
    assert repaired[1].code == "mise.installations_single"
    assert repaired[1].severity is Severity.OK


def test_linux_systemd_check_reports_global_mise_shim_dependencies(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    system_units = tmp_path / "systemd"
    user_units = home / ".config/systemd/user"
    system_units.mkdir()
    user_units.mkdir(parents=True)
    worker = system_units / "worker.service"
    worker.write_text("[Service]\nExecStart=/usr/bin/worker\n")
    drop_in = system_units / "worker.service.d/override.conf"
    drop_in.parent.mkdir()
    safe = user_units / "pueued.service"
    safe.write_text("[Service]\nExecStart=/usr/bin/pueued -vv\n")

    for execution_directive in check_module.SYSTEMD_SERVICE_EXEC_DIRECTIVES:
        drop_in.write_text(
            f"[Service]\n{execution_directive} = "
            "/root/.local/share/mise/shims/pueued --token=private\n"
        )
        findings = check_module._mise_systemd_shim_findings(
            home,
            system_unit_directory=system_units,
        )

        assert len(findings) == 1
        assert findings[0].code == "mise.systemd_shim_dependency"
        assert findings[0].severity is Severity.WARN
        assert findings[0].path == drop_in
        assert execution_directive in findings[0].message
        assert "private" not in findings[0].message

    drop_in.write_text(
        "[Service]\nExecStart=/root/.local/bin/mise -C /root/project exec -- pueued\n"
    )
    repaired = check_module._mise_systemd_shim_findings(
        home,
        system_unit_directory=system_units,
    )
    assert repaired[0].code == "mise.systemd_shims_clean"
    assert repaired[0].severity is Severity.OK


def test_linux_systemd_check_scans_global_and_data_user_unit_paths(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    system_units = tmp_path / "systemd/system"
    system_units.mkdir(parents=True)
    user_unit_directories = (
        system_units.parent / "user",
        home / ".local/share/systemd/user",
    )

    for unit_directory in user_unit_directories:
        unit_directory.mkdir(parents=True)
        unit = unit_directory / "worker.service"
        unit.write_text(
            "[Service]\nExecStart=/home/alex/.local/share/mise/shims/worker\n"
        )

        findings = check_module._mise_systemd_shim_findings(
            home,
            system_unit_directory=system_units,
        )

        assert len(findings) == 1
        assert findings[0].code == "mise.systemd_shim_dependency"
        assert findings[0].path == unit
        unit.unlink()


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


def test_inspect_host_reports_symlinked_generated_directories(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    external = tmp_path / "external-functions"
    home.mkdir()
    external.mkdir()
    (external / "generated.zsh").write_text("external\n")
    functions = repo_root / "generated/functions"
    functions.parent.mkdir(parents=True)
    functions.symlink_to(external, target_is_directory=True)

    report = inspect_host(
        repo_root,
        home,
        executable_finder=lambda _command: None,
        system_name="Darwin",
        profile="full",
    )
    findings = {finding.code: finding for finding in report.findings}

    finding = findings["shell.functions_symlinked"]
    assert finding.severity is Severity.WARN
    assert finding.path == functions
    assert finding.action is not None
    assert "Remove the symlink" in finding.action


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
    grouped_skill = source / "skill-group/example/SKILL.md"
    grouped_skill.parent.mkdir(parents=True)
    grouped_skill.write_text("---\nname: example\n---\n")
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
                "details": ["extras", "skill-group"],
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
    assert finding.message == (
        "Skillshare doctor reports 1 actionable warning(s): tracked_repos"
    )


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
    assert finding.message == (
        "Skillshare doctor reports 1 actionable warning(s): "
        "skills_validity: broken-skill"
    )


def test_skillshare_doctor_timeout_returns_a_warning(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def time_out(*args: object, **kwargs: object) -> None:
        assert kwargs["timeout"] == 30
        raise subprocess.TimeoutExpired(["skillshare", "doctor", "--json"], 30)

    monkeypatch.setattr(check_module.subprocess, "run", time_out)

    finding = check_module._skillshare_doctor_finding(
        tmp_path / "skillshare",
        tmp_path,
    )

    assert finding.severity is Severity.WARN
    assert finding.code == "skillshare.doctor_unavailable"
    assert "timed out" in finding.message


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
    assert report.is_ok() is True


def _write_module_source(source: Path, body: str) -> None:
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(f"#!/bin/bash\n{body}\n")


def _bag_mode_stub(tmp_path: Path, record: dict, *, version: str) -> Path:
    executable = tmp_path / "bin/bag-mode"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text(
        "#!/bin/sh\n"
        f"if [ \"$1\" = version ]; then printf '%s\\n' 'bag-mode {version}'; exit 0; fi\n"
        f"printf '%s\\n' {json.dumps(json.dumps(record))}\n",
    )
    executable.chmod(0o755)
    return executable


def _maxfiles_stub(tmp_path: Path, record: dict) -> Path:
    executable = tmp_path / "bin/macos-maxfiles"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text(
        f"#!/bin/sh\nprintf '%s\\n' {json.dumps(json.dumps(record))}\n",
    )
    executable.chmod(0o755)
    return executable


def _module_probe_findings(tmp_path: Path, finder, prefix: str) -> dict:
    report = inspect_host(
        tmp_path / "repo",
        tmp_path / "home",
        executable_finder=finder,
        system_name="Darwin",
        profile="macos",
    )
    return {
        finding.check: finding
        for finding in report.findings
        if finding.check.startswith(prefix)
    }


def test_bag_mode_probe_flags_version_drift_and_stalled_controller(
    tmp_path: Path,
) -> None:
    (tmp_path / "home").mkdir()
    _write_module_source(
        tmp_path / "repo/modules/bag-mode/bag-mode",
        'VERSION="2.6.0"',
    )
    stub = _bag_mode_stub(
        tmp_path,
        {
            "enabled": True,
            "phase": "starting",
            "recovery_required": False,
            "brightness_pending": False,
        },
        version="2.5.0",
    )

    def finder(command: str) -> str | None:
        if command == "bag-mode":
            return str(stub)
        return (
            f"/tools/{command}" if command in {"git", "python", "uv", "mise"} else None
        )

    findings = _module_probe_findings(tmp_path, finder, "bag_mode.")

    assert findings["bag_mode.lifecycle"].severity is Severity.WARN
    assert findings["bag_mode.lifecycle"].code == "bag_mode.stalled"
    assert findings["bag_mode.version"].severity is Severity.WARN
    assert findings["bag_mode.version"].code == "bag_mode.version_drift"
    assert "upgrade" in findings["bag_mode.version"].action


def test_bag_mode_probe_reports_recovery_then_clean_stop(tmp_path: Path) -> None:
    (tmp_path / "home").mkdir()
    _write_module_source(
        tmp_path / "repo/modules/bag-mode/bag-mode",
        'VERSION="2.6.0"',
    )
    stub = _bag_mode_stub(
        tmp_path,
        {
            "enabled": True,
            "phase": "running",
            "recovery_required": False,
            "brightness_pending": True,
        },
        version="2.6.0",
    )

    def finder(command: str) -> str | None:
        if command == "bag-mode":
            return str(stub)
        return (
            f"/tools/{command}" if command in {"git", "python", "uv", "mise"} else None
        )

    pending = _module_probe_findings(tmp_path, finder, "bag_mode.")
    assert pending["bag_mode.lifecycle"].code == "bag_mode.recovery_pending"
    assert "bag-mode recover" in pending["bag_mode.lifecycle"].action
    assert pending["bag_mode.version"].code == "bag_mode.version_current"
    assert pending["bag_mode.version"].severity is Severity.OK

    _bag_mode_stub(
        tmp_path,
        {
            "enabled": False,
            "phase": "stopped",
            "recovery_required": False,
            "brightness_pending": False,
        },
        version="2.6.0",
    )
    stopped = _module_probe_findings(tmp_path, finder, "bag_mode.")
    assert stopped["bag_mode.lifecycle"].code == "bag_mode.stopped"
    assert stopped["bag_mode.lifecycle"].severity is Severity.OK


def test_bag_mode_probe_rejects_version_output_from_failed_command(
    tmp_path: Path,
) -> None:
    (tmp_path / "home").mkdir()
    _write_module_source(
        tmp_path / "repo/modules/bag-mode/bag-mode",
        'VERSION="2.6.0"',
    )
    stub = _bag_mode_stub(
        tmp_path,
        {
            "enabled": False,
            "phase": "stopped",
            "recovery_required": False,
            "brightness_pending": False,
        },
        version="2.6.0",
    )
    stub.write_text(
        stub.read_text().replace("exit 0; fi", "echo broken >&2; exit 9; fi")
    )

    def finder(command: str) -> str | None:
        if command == "bag-mode":
            return str(stub)
        return (
            f"/tools/{command}" if command in {"git", "python", "uv", "mise"} else None
        )

    findings = _module_probe_findings(tmp_path, finder, "bag_mode.")
    version = findings["bag_mode.version"]

    assert version.severity is Severity.WARN
    assert version.code == "bag_mode.version_unavailable"
    assert "command exited 9: broken" in version.message


def test_bag_mode_probe_handles_missing_tool_and_invalid_status(
    tmp_path: Path,
) -> None:
    (tmp_path / "home").mkdir()

    def absent_finder(command: str) -> str | None:
        return (
            f"/tools/{command}" if command in {"git", "python", "uv", "mise"} else None
        )

    missing = _module_probe_findings(tmp_path, absent_finder, "bag_mode.")
    assert missing["bag_mode.lifecycle"].code == "bag_mode.missing"
    assert missing["bag_mode.lifecycle"].severity is Severity.WARN

    broken = tmp_path / "bin/broken-bag-mode"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_text("#!/bin/sh\necho 'not json'\n")
    broken.chmod(0o755)

    def broken_finder(command: str) -> str | None:
        if command == "bag-mode":
            return str(broken)
        return absent_finder(command)

    invalid = _module_probe_findings(tmp_path, broken_finder, "bag_mode.")
    assert invalid["bag_mode.lifecycle"].code == "bag_mode.status_unavailable"
    assert "bag_mode.version" not in invalid


def test_maxfiles_probe_flags_limit_drift_and_unloaded_daemon(
    tmp_path: Path,
) -> None:
    (tmp_path / "home").mkdir()
    _write_module_source(
        tmp_path / "repo/modules/macos-maxfiles/macos-maxfiles",
        'SOFT_LIMIT="8192"\nHARD_LIMIT="65536"',
    )
    stub = _maxfiles_stub(
        tmp_path,
        {
            "installed": True,
            "binary": True,
            "loaded": True,
            "soft_limit": "256",
            "hard_limit": "unlimited",
        },
    )

    def finder(command: str) -> str | None:
        if command == "macos-maxfiles":
            return str(stub)
        return (
            f"/tools/{command}" if command in {"git", "python", "uv", "mise"} else None
        )

    drifted = _module_probe_findings(tmp_path, finder, "maxfiles.")
    assert drifted["maxfiles.agent"].code == "maxfiles.agent_ready"
    assert drifted["maxfiles.limits"].severity is Severity.WARN
    assert drifted["maxfiles.limits"].code == "maxfiles.limits_drift"
    assert "install" in drifted["maxfiles.limits"].action

    _maxfiles_stub(
        tmp_path,
        {
            "installed": True,
            "binary": True,
            "loaded": True,
            "soft_limit": "8192",
            "hard_limit": "unlimited",
        },
    )
    unlimited = _module_probe_findings(tmp_path, finder, "maxfiles.")
    assert unlimited["maxfiles.limits"].code == "maxfiles.limits_effective"
    assert unlimited["maxfiles.limits"].severity is Severity.OK

    _maxfiles_stub(
        tmp_path,
        {
            "installed": True,
            "binary": True,
            "loaded": False,
            "soft_limit": "",
            "hard_limit": "",
        },
    )
    down = _module_probe_findings(tmp_path, finder, "maxfiles.")
    assert down["maxfiles.agent"].code == "maxfiles.agent_down"
    assert down["maxfiles.agent"].severity is Severity.WARN
    assert "maxfiles.limits" not in down

    def absent_finder(command: str) -> str | None:
        return (
            f"/tools/{command}" if command in {"git", "python", "uv", "mise"} else None
        )

    missing = _module_probe_findings(tmp_path, absent_finder, "maxfiles.")
    assert missing["maxfiles.agent"].code == "maxfiles.missing"


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


def test_inspect_host_reports_generated_plugins_without_an_owner(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    generated_plugins = repo_root / "generated/plugins"
    generated_plugins.mkdir(parents=True)
    stale_plugin = generated_plugins / "old-plugin"
    stale_plugin.mkdir()

    report = inspect_host(
        repo_root,
        home,
        executable_finder=lambda _command: None,
        system_name="Darwin",
        profile="full",
    )
    findings = {finding.code: finding for finding in report.findings}

    finding = findings["runtime.plugin.old-plugin_unowned"]
    assert finding.severity is Severity.WARN
    assert finding.path == stale_plugin
    assert finding.action is not None
    assert "Remove it explicitly" in finding.action


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


def test_session_health_probe_reports_unconfigured_and_invalid_status(
    tmp_path: Path,
) -> None:
    (tmp_path / "home").mkdir()
    now = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    codes = _session_health_codes(
        tmp_path,
        {
            "installed": True,
            "loaded": True,
            "notification_configured": False,
            "last_snapshot_at": now,
            "consecutive_delivery_failures": 0,
        },
    )
    assert (
        codes["session_health.notifications"]
        == "session_health.notifications_unconfigured"
    )

    garbled = tmp_path / "bin/garbled-session-health"
    garbled.parent.mkdir(parents=True, exist_ok=True)
    garbled.write_text("#!/bin/sh\necho this is not json\n")
    garbled.chmod(0o755)
    report = inspect_host(
        tmp_path / "repo",
        tmp_path / "home",
        executable_finder=lambda command: (
            str(garbled) if command == "macos-session-health" else f"/tools/{command}"
        ),
        system_name="Darwin",
        profile="macos",
    )
    finding = next(
        finding
        for finding in report.findings
        if finding.check == "session_health.agent"
    )

    assert finding.code == "session_health.status_invalid"


def test_dangling_repo_links_are_reported_and_track_target_removal(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "dotfiles"
    (repo_root / "reference").mkdir(parents=True)
    home = tmp_path / "home"
    (home / ".config").mkdir(parents=True)

    healthy_target = repo_root / "reference/.zshrc"
    healthy_target.write_text("reference\n")
    (home / ".zshrc").symlink_to(healthy_target)
    (home / ".condarc").symlink_to(repo_root / "home/.condarc")
    (home / ".unrelated").symlink_to(tmp_path / "elsewhere/file")
    code_user = home / "Library/Application Support/Code/User"
    code_user.mkdir(parents=True)
    (code_user / "keybindings.json").symlink_to(repo_root / "assets/keybindings.json")
    # XDG app config at depth 4 — the mapped path a shallower scan missed.
    code_xdg = home / ".config/Code/User"
    code_xdg.mkdir(parents=True)
    (code_xdg / "settings.json").symlink_to(repo_root / "reference/removed.json")
    # Depth 5, still beyond the scan and beyond any mapped path.
    deep = home / "a/b/c/d"
    deep.mkdir(parents=True)
    (deep / "too-deep").symlink_to(repo_root / "gone")

    findings = check_module._dangling_repo_link_findings(repo_root, home)
    dangling = {
        finding.path for finding in findings if finding.severity is Severity.WARN
    }

    assert dangling == {
        home / ".condarc",
        code_user / "keybindings.json",
        code_xdg / "settings.json",
    }
    assert all(
        finding.code == "home.dangling_repo_link"
        for finding in findings
        if finding.severity is Severity.WARN
    )

    healthy_target.unlink()
    degraded = check_module._dangling_repo_link_findings(repo_root, home)
    assert home / ".zshrc" in {
        finding.path for finding in degraded if finding.severity is Severity.WARN
    }


def test_home_without_repository_links_reports_clean(tmp_path: Path) -> None:
    repo_root = tmp_path / "dotfiles"
    (repo_root / "reference").mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir()
    (home / ".zshrc").write_text("plain file\n")

    findings = check_module._dangling_repo_link_findings(repo_root, home)

    assert [finding.code for finding in findings] == ["home.repo_links_clean"]
    assert findings[0].severity is Severity.OK
