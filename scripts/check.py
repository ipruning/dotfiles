"""Inspect host capabilities without installing or changing them."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import shutil
import stat
import subprocess
from collections.abc import Callable
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .models import CheckReport, Finding, Severity
from .profiles import HostProfile, resolve_profile
from .render import finding_document, render_findings
from .runtime import (
    COMPLETION_SPECS,
    FUNCTION_SPECS,
    LOCAL_BINARY_SPECS,
    PLUGIN_SPECS,
    WASM_SPECS,
    file_sha256,
    repo_aware_finder,
)

ExecutableFinder = Callable[[str], str | None]


def _finding(
    check: str,
    severity: Severity,
    code: str,
    message: str,
    path: Path | None = None,
    action: str | None = None,
) -> Finding:
    return Finding(check, severity, code, message, path, action)


def _check_executable(
    command: str,
    *,
    required: bool,
    executable_finder: ExecutableFinder,
) -> Finding:
    executable = executable_finder(command)
    if executable:
        return _finding(
            f"executable.{command}",
            Severity.OK,
            f"executable.{command}.ready",
            f"{command} is available",
            Path(executable),
        )
    severity = Severity.ERROR if required else Severity.WARN
    return _finding(
        f"executable.{command}",
        severity,
        f"executable.{command}.missing",
        f"{command} is not available on PATH",
        action=f"Install {command} if this host needs that capability.",
    )


def _git_config_defines_identity(config_path: Path) -> bool:
    for key in ("user.name", "user.email"):
        try:
            completed = subprocess.run(
                ["git", "config", "--file", str(config_path), "--get", key],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            return False
        if completed.returncode != 0 or not completed.stdout.strip():
            return False
    return True


def _private_git_identity_ready(private_config: Path, home: Path) -> bool:
    if _git_config_defines_identity(private_config):
        return True
    try:
        completed = subprocess.run(
            [
                "git",
                "config",
                "--file",
                str(private_config),
                "--get-regexp",
                "-z",
                r"^includeif\..*\.path$",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    if completed.returncode != 0:
        return False
    identity_configs: list[Path] = []
    for record in completed.stdout.split("\0"):
        if not record:
            continue
        _, _, raw_path = record.partition("\n")
        if not raw_path:
            return False
        if raw_path.startswith("~/"):
            config_path = home / raw_path[2:]
        else:
            config_path = Path(raw_path)
            if not config_path.is_absolute():
                config_path = private_config.parent / config_path
        identity_configs.append(config_path)
    return bool(identity_configs) and all(
        _git_config_defines_identity(config_path) for config_path in identity_configs
    )


def _private_git_findings(home: Path) -> list[Finding]:
    gitconfig = home / ".gitconfig"
    private_config = home / ".private.gitconfig"
    include_present = False
    if gitconfig.is_file():
        try:
            completed = subprocess.run(
                [
                    "git",
                    "config",
                    "--file",
                    str(gitconfig),
                    "--get-all",
                    "include.path",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            include_present = "~/.private.gitconfig" in completed.stdout.splitlines()
        except OSError:
            include_present = False
    findings = [
        _finding(
            "git.private_include",
            Severity.OK if include_present else Severity.WARN,
            (
                "git.private_include_ready"
                if include_present
                else "git.private_include_missing"
            ),
            (
                "Git includes ~/.private.gitconfig"
                if include_present
                else "Git does not include ~/.private.gitconfig"
            ),
            gitconfig,
            None if include_present else "Add the private include to ~/.gitconfig.",
        ),
    ]
    if not private_config.is_file():
        findings.append(
            _finding(
                "git.private_file",
                Severity.WARN,
                "git.private_file_missing",
                "The private Git configuration is missing",
                private_config,
                "Create ~/.private.gitconfig with this host's Git identity.",
            ),
        )
        return findings
    writable_by_others = private_config.stat().st_mode & (stat.S_IWGRP | stat.S_IWOTH)
    findings.append(
        _finding(
            "git.private_file",
            Severity.WARN if writable_by_others else Severity.OK,
            (
                "git.private_file_permissions"
                if writable_by_others
                else "git.private_file_ready"
            ),
            (
                "The private Git configuration is group or world writable"
                if writable_by_others
                else "The private Git configuration exists with safe permissions"
            ),
            private_config,
            "Remove group and world write permission." if writable_by_others else None,
        ),
    )
    identity_ready = _private_git_identity_ready(private_config, home)
    findings.append(
        _finding(
            "git.private_identity",
            Severity.OK if identity_ready else Severity.WARN,
            (
                "git.private_identity_ready"
                if identity_ready
                else "git.private_identity_missing"
            ),
            (
                "The private Git configuration provides complete Git identities"
                if identity_ready
                else "The private Git configuration does not provide complete Git identities"
            ),
            private_config,
            (
                None
                if identity_ready
                else "Define user.name and user.email directly or in every conditional identity include."
            ),
        ),
    )
    return findings


def _expand_home(value: str, home: Path) -> Path:
    if value == "~":
        return home
    if value.startswith("~/"):
        return home / value[2:]
    return Path(value)


def _skillshare_findings(home: Path) -> list[Finding]:
    config_path = home / ".config/skillshare/config.yaml"
    if not config_path.is_file():
        return [
            _finding(
                "skillshare.config",
                Severity.WARN,
                "skillshare.config_missing",
                "Skillshare configuration is missing",
                config_path,
                "Create a host-specific Skillshare config; do not copy harness extras blindly.",
            ),
        ]
    try:
        document = YAML(typ="safe").load(config_path)
        source_value = document["sources"]["skills"]
        if not isinstance(source_value, str):
            raise TypeError("sources.skills must be a string")
    except (OSError, KeyError, TypeError, YAMLError) as error:
        return [
            _finding(
                "skillshare.config",
                Severity.WARN,
                "skillshare.config_invalid",
                f"Skillshare configuration cannot identify sources.skills: {error}",
                config_path,
                "Repair sources.skills in the host-specific Skillshare config.",
            ),
        ]
    source = _expand_home(source_value, home)
    return [
        _finding(
            "skillshare.config",
            Severity.OK,
            "skillshare.config_ready",
            "Skillshare configuration is readable",
            config_path,
        ),
        _finding(
            "skillshare.source",
            Severity.OK if source.is_dir() else Severity.WARN,
            (
                "skillshare.source_ready"
                if source.is_dir()
                else "skillshare.source_missing"
            ),
            (
                "Skillshare source directory exists"
                if source.is_dir()
                else "Skillshare source directory is missing"
            ),
            source,
            None
            if source.is_dir()
            else "Clone or restore the configured skills source.",
        ),
    ]


def _skillshare_doctor_finding(executable: Path, home: Path) -> Finding:
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    try:
        completed = subprocess.run(
            [str(executable), "doctor", "--json"],
            cwd=home,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        return _finding(
            "skillshare.doctor",
            Severity.WARN,
            "skillshare.doctor_unavailable",
            f"Skillshare doctor could not run: {error}",
            action="Run skillshare doctor --json and resolve reported errors.",
        )
    try:
        document = json.loads(completed.stdout)
        summary = document["summary"]
        warnings = summary["warnings"]
        errors = summary["errors"]
        if not isinstance(warnings, int) or not isinstance(errors, int):
            raise TypeError("summary counts must be integers")
        raw_checks = document.get("checks")
        if isinstance(raw_checks, list):
            ignored_warnings = {"git_status", "theme"}
            actionable_warnings = 0
            reported_errors = 0
            for raw_check in raw_checks:
                if not isinstance(raw_check, dict):
                    raise TypeError("checks must contain objects")
                name = raw_check.get("name")
                check_status = raw_check.get("status")
                if not isinstance(name, str) or not isinstance(check_status, str):
                    raise TypeError("check name and status must be strings")
                details = raw_check.get("details")
                known_resource_warning = name == "skills_validity" and details == [
                    "extras"
                ]
                if check_status == "error":
                    reported_errors += 1
                elif (
                    check_status == "warning"
                    and name not in ignored_warnings
                    and not known_resource_warning
                ):
                    actionable_warnings += 1
            warnings = actionable_warnings
            errors = reported_errors
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        return _finding(
            "skillshare.doctor",
            Severity.WARN,
            "skillshare.doctor_invalid",
            f"Skillshare doctor returned invalid JSON: {error}",
            action="Run skillshare doctor --json and inspect its output.",
        )
    if errors or completed.returncode != 0:
        return _finding(
            "skillshare.doctor",
            Severity.WARN,
            "skillshare.doctor_failed",
            f"Skillshare doctor reports {errors} error(s) and "
            f"{warnings} actionable warning(s)",
            action="Resolve doctor errors before treating Skillshare as ready.",
        )
    if warnings:
        return _finding(
            "skillshare.doctor",
            Severity.WARN,
            "skillshare.doctor_warnings",
            f"Skillshare doctor reports {warnings} actionable warning(s)",
            action="Review Skillshare warnings, including failed tracked repositories.",
        )
    return _finding(
        "skillshare.doctor",
        Severity.OK,
        "skillshare.doctor_ready",
        "Skillshare doctor reports no errors or warnings",
    )


def _file_capability(
    check: str,
    file_path: Path,
    label: str,
    missing_action: str | None = None,
) -> Finding:
    exists = file_path.is_file()
    return _finding(
        check,
        Severity.OK if exists else Severity.WARN,
        f"{check}_{'ready' if exists else 'missing'}",
        f"{label} {'exists' if exists else 'is missing'}",
        file_path,
        None if exists else missing_action,
    )


def _owned_generated_capability(
    check: str,
    file_path: Path,
    label: str,
    *,
    tool_available: bool,
) -> Finding | None:
    action = "Run mise run runtime -- --dry-run, then mise run runtime."
    if tool_available:
        return _file_capability(check, file_path, label, action)
    if file_path.exists() or file_path.is_symlink():
        return _finding(
            check,
            Severity.WARN,
            f"{check}_stale",
            f"{label} is stale because its generator is not available",
            file_path,
            action,
        )
    return None


def _binary_capability(check: str, file_path: Path, label: str) -> Finding:
    try:
        ready = (
            file_path.is_file()
            and file_path.stat().st_size > 0
            and os.access(file_path, os.X_OK)
        )
    except OSError:
        ready = False
    if ready:
        return _finding(
            check,
            Severity.OK,
            f"{check}_ready",
            f"{label} is present and executable",
            file_path,
        )
    return _finding(
        check,
        Severity.WARN,
        f"{check}_invalid",
        f"{label} is missing, empty, or not executable",
        file_path,
        "Run mise run runtime -- --build --dry-run, then mise run runtime -- --build.",
    )


def _generated_directory_finding(directory_path: Path, label: str) -> Finding:
    if not directory_path.is_dir():
        return _finding(
            f"shell.{label}",
            Severity.WARN,
            f"shell.{label}_missing",
            f"Generated shell {label} directory is missing",
            directory_path,
            "Run the generator that owns this shell runtime state.",
        )
    populated = any(
        child.name != ".gitkeep"
        for child in directory_path.rglob("*")
        if child.is_file() or child.is_symlink()
    )
    return _finding(
        f"shell.{label}",
        Severity.OK if populated else Severity.WARN,
        f"shell.{label}_{'ready' if populated else 'empty'}",
        f"Generated shell {label} directory "
        f"{'contains runtime data' if populated else 'contains no runtime data'}",
        directory_path,
        None if populated else "Generate this shell runtime state if the host uses it.",
    )


def _bash_integration_finding(repo_root: Path, home: Path) -> Finding:
    bashrc = home / ".bashrc"
    module_path = repo_root.resolve() / "modules/bash/init.bash"
    try:
        configured = bashrc.is_file() and str(module_path) in bashrc.read_text()
    except OSError:
        configured = False
    return _finding(
        "shell.bash",
        Severity.OK if configured else Severity.WARN,
        "shell.bash_ready" if configured else "shell.bash_missing",
        "Bash loads the Linux Lite module"
        if configured
        else "Bash does not load the Linux Lite module",
        bashrc,
        None if configured else "Run mise run setup -- --profile linux-lite.",
    )


def _legacy_repo_path_finding(repo_root: Path) -> Finding:
    legacy_directories = (
        (repo_root / "modules/bin").resolve(),
        (repo_root / "generated/bin").resolve(),
    )
    active_directories = {
        Path(entry).expanduser().resolve()
        for entry in os.environ.get("PATH", "").split(os.pathsep)
        if entry
    }
    exposed = next(
        (
            directory
            for directory in legacy_directories
            if directory in active_directories
        ),
        None,
    )
    return _finding(
        "shell.repo_commands",
        Severity.WARN if exposed else Severity.OK,
        ("shell.repo_commands_exposed" if exposed else "shell.repo_commands_isolated"),
        (
            "Linux PATH exposes repository commands from a legacy configuration"
            if exposed
            else "Linux PATH does not expose repository command directories"
        ),
        exposed,
        (
            "Remove dotfiles modules/bin and generated/bin from Bash or global mise PATH configuration."
            if exposed
            else None
        ),
    )


SESSION_HEALTH_SNAPSHOT_MAX_AGE = dt.timedelta(minutes=30)
SESSION_HEALTH_FAILURE_STREAK = 3


def _session_health_findings(
    executable_finder: ExecutableFinder,
    *,
    now: dt.datetime | None = None,
) -> list[Finding]:
    executable = executable_finder("macos-session-health")
    if executable is None:
        return [
            _finding(
                "session_health.agent",
                Severity.WARN,
                "session_health.missing",
                "macos-session-health is not installed",
                action=(
                    "Run modules/macos-session-health/macos-session-health install."
                ),
            ),
        ]
    try:
        completed = subprocess.run(
            [str(executable), "status", "--format", "json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return [
            _finding(
                "session_health.agent",
                Severity.WARN,
                "session_health.status_unavailable",
                f"macos-session-health status could not run: {error}",
                action="Run macos-session-health status and resolve the failure.",
            ),
        ]
    if completed.returncode != 0 and not completed.stdout.strip():
        detail = completed.stderr.strip() or f"exit {completed.returncode}"
        return [
            _finding(
                "session_health.agent",
                Severity.WARN,
                "session_health.status_unavailable",
                f"macos-session-health status failed: {detail}",
                action="Run macos-session-health status and resolve the failure.",
            ),
        ]
    try:
        records = json.loads(completed.stdout)
        record = records[0]
        installed = bool(record["installed"])
        loaded = bool(record["loaded"])
        last_snapshot_at = str(record.get("last_snapshot_at") or "")
        failures = int(record.get("consecutive_delivery_failures") or 0)
        configured = bool(record.get("notification_configured"))
    except (json.JSONDecodeError, LookupError, TypeError, ValueError) as error:
        return [
            _finding(
                "session_health.agent",
                Severity.WARN,
                "session_health.status_invalid",
                f"macos-session-health status returned an invalid report: {error}",
                action="Run macos-session-health status --format json.",
            ),
        ]

    agent_ready = installed and loaded
    findings = [
        _finding(
            "session_health.agent",
            Severity.OK if agent_ready else Severity.WARN,
            "session_health.agent_ready"
            if agent_ready
            else "session_health.agent_down",
            "session-health launch agent is installed and loaded"
            if agent_ready
            else "session-health launch agent is not running",
            action=(
                None
                if agent_ready
                else "Run modules/macos-session-health/macos-session-health install."
            ),
        ),
    ]

    snapshot_fresh = False
    if last_snapshot_at:
        try:
            last = dt.datetime.fromisoformat(last_snapshot_at.replace("Z", "+00:00"))
            current = now or dt.datetime.now(dt.timezone.utc)
            snapshot_fresh = current - last <= SESSION_HEALTH_SNAPSHOT_MAX_AGE
        except ValueError, TypeError:
            snapshot_fresh = False
    findings.append(
        _finding(
            "session_health.snapshot",
            Severity.OK if snapshot_fresh else Severity.WARN,
            "session_health.snapshot_recent"
            if snapshot_fresh
            else "session_health.snapshot_stale",
            f"last snapshot: {last_snapshot_at}"
            if last_snapshot_at
            else "no snapshot has been recorded",
            action=(
                None
                if snapshot_fresh
                else "Inspect launchd logs; the agent may have silently stopped."
            ),
        ),
    )

    if not configured:
        findings.append(
            _finding(
                "session_health.notifications",
                Severity.WARN,
                "session_health.notifications_unconfigured",
                "notification delivery is not configured",
                action="Provide BRRR_SECRET via ~/.config/brrr/env.",
            ),
        )
    elif failures >= SESSION_HEALTH_FAILURE_STREAK:
        findings.append(
            _finding(
                "session_health.notifications",
                Severity.WARN,
                "session_health.notifications_failing",
                f"last {failures} notification deliveries failed",
                action="Run macos-session-health notify-test --dry-run.",
            ),
        )
    else:
        findings.append(
            _finding(
                "session_health.notifications",
                Severity.OK,
                "session_health.notifications_ready",
                "notification delivery is configured and recently healthy",
            ),
        )
    return findings


def inspect_host(
    repo_root: Path,
    home: Path,
    *,
    executable_finder: ExecutableFinder = shutil.which,
    system_name: str | None = None,
    profile: str | HostProfile = HostProfile.AUTO,
) -> CheckReport:
    """Return explicit required and optional capabilities for this host."""
    active_system = system_name or platform.system()
    active_profile = resolve_profile(profile, active_system)
    required_commands = (
        ("git", "mise")
        if active_profile is HostProfile.LINUX_LITE
        else ("git", "python", "uv", "mise")
    )
    findings = [
        _check_executable(
            command,
            required=True,
            executable_finder=executable_finder,
        )
        for command in required_commands
    ]
    findings.extend(_private_git_findings(home))
    skillshare_finding = _check_executable(
        "skillshare",
        required=False,
        executable_finder=executable_finder,
    )
    findings.append(skillshare_finding)
    findings.extend(_skillshare_findings(home))
    if skillshare_finding.path and (home / ".config/skillshare/config.yaml").is_file():
        findings.append(_skillshare_doctor_finding(skillshare_finding.path, home))
    if active_profile is HostProfile.LINUX_LITE:
        findings.append(_bash_integration_finding(repo_root, home))
        findings.append(_legacy_repo_path_finding(repo_root))
        return CheckReport(schema_version=1, findings=tuple(findings))
    if active_system == "Darwin":
        findings.extend(_session_health_findings(executable_finder))
    findings.append(
        _check_executable(
            "tv",
            required=False,
            executable_finder=executable_finder,
        ),
    )
    findings.append(
        _file_capability(
            "television.config",
            home / ".config/television/config.toml",
            "Television configuration",
        ),
    )
    for directory in ("plugins", "completions", "functions"):
        findings.append(
            _generated_directory_finding(
                repo_root / "generated" / directory, directory
            ),
        )
    owned_tool_finder = repo_aware_finder(repo_root, executable_finder)
    for tool, _command, filename in FUNCTION_SPECS:
        finding = _owned_generated_capability(
            f"runtime.function.{tool}",
            repo_root / "generated/functions" / filename,
            f"Generated {tool} Zsh initialization",
            tool_available=owned_tool_finder(tool) is not None,
        )
        if finding:
            findings.append(finding)
    for name, tool, _command, filename, _environment in COMPLETION_SPECS:
        finding = _owned_generated_capability(
            f"runtime.completion.{name}",
            repo_root / "generated/completions" / filename,
            f"Generated {name} completion",
            tool_available=owned_tool_finder(tool) is not None,
        )
        if finding:
            findings.append(finding)
    for name, _source, entrypoint in PLUGIN_SPECS:
        findings.append(
            _file_capability(
                f"runtime.plugin.{name}",
                repo_root / "generated/plugins" / name / entrypoint,
                f"Zsh plugin {name}",
                "Run mise run runtime -- --dry-run, then mise run runtime.",
            ),
        )
    for name, _source, sha256 in WASM_SPECS:
        plugin_name = f"{name}.wasm"
        plugin_path = repo_root / "generated/plugins" / plugin_name
        actual_sha256 = file_sha256(plugin_path)
        if actual_sha256 == sha256:
            findings.append(
                _finding(
                    f"zellij.{plugin_name}",
                    Severity.OK,
                    f"zellij.{plugin_name}_ready",
                    f"Zellij plugin {plugin_name} matches its pinned checksum",
                    plugin_path,
                ),
            )
        else:
            code = "missing" if actual_sha256 is None else "checksum_mismatch"
            message = (
                f"Zellij plugin {plugin_name} is missing"
                if actual_sha256 is None
                else f"Zellij plugin {plugin_name} does not match its pinned checksum"
            )
            findings.append(
                _finding(
                    f"zellij.{plugin_name}",
                    Severity.WARN,
                    f"zellij.{plugin_name}_{code}",
                    message,
                    plugin_path,
                    "Run mise run runtime -- --dry-run, then mise run runtime.",
                ),
            )
    generated_bin = repo_root / "generated/bin"
    owned_binaries = {name for name, _source, _command, _artifact in LOCAL_BINARY_SPECS}
    for binary_name in sorted(owned_binaries):
        findings.append(
            _binary_capability(
                f"runtime.binary.{binary_name}",
                generated_bin / binary_name,
                f"Generated binary {binary_name}",
            ),
        )
    if generated_bin.is_dir():
        for file_path in sorted(generated_bin.iterdir()):
            if (
                file_path.name in owned_binaries
                or file_path.name == ".gitkeep"
                or not (file_path.is_file() or file_path.is_symlink())
            ):
                continue
            findings.append(
                _finding(
                    f"runtime.binary.{file_path.name}",
                    Severity.WARN,
                    f"runtime.binary.{file_path.name}_unowned",
                    f"Generated binary {file_path.name} has no repository owner",
                    file_path,
                    "Define its build or install owner before treating it as reproducible.",
                ),
            )
    if active_system == "Darwin":
        findings.append(
            _check_executable(
                "launchctl",
                required=False,
                executable_finder=executable_finder,
            ),
        )
    else:
        findings.append(
            _finding(
                "macos.launchctl",
                Severity.SKIPPED,
                "macos.launchctl_skipped",
                f"launchctl is not applicable on {active_system}",
            ),
        )
    return CheckReport(schema_version=1, findings=tuple(findings))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect this host's capabilities.")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--profile",
        choices=[profile.value for profile in HostProfile],
        default=HostProfile.AUTO.value,
    )
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    report = inspect_host(repo_root, Path.home(), profile=args.profile)
    if args.as_json:
        print(
            json.dumps(
                finding_document(report, strict=args.strict),
                indent=2,
                sort_keys=True,
            ),
        )
    else:
        render_findings(report, include_ok=True)
    return 0 if report.is_ok(strict=args.strict) else 1


if __name__ == "__main__":
    raise SystemExit(main())
