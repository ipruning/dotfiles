"""Inspect host capabilities without installing or changing them."""

from __future__ import annotations

import argparse
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
            ignored_warnings = {"theme"}
            actionable_warnings = 0
            reported_errors = 0
            for raw_check in raw_checks:
                if not isinstance(raw_check, dict):
                    raise TypeError("checks must contain objects")
                name = raw_check.get("name")
                check_status = raw_check.get("status")
                if not isinstance(name, str) or not isinstance(check_status, str):
                    raise TypeError("check name and status must be strings")
                if check_status == "error":
                    reported_errors += 1
                elif check_status == "warning" and name not in ignored_warnings:
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


def _file_capability(check: str, file_path: Path, label: str) -> Finding:
    exists = file_path.is_file()
    return _finding(
        check,
        Severity.OK if exists else Severity.WARN,
        f"{check}_{'ready' if exists else 'missing'}",
        f"{label} {'exists' if exists else 'is missing'}",
        file_path,
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
    module_path = repo_root / "modules/bash/init.bash"
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
    findings = [
        _check_executable(
            command,
            required=True,
            executable_finder=executable_finder,
        )
        for command in ("git", "python", "uv", "mise")
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
        return CheckReport(schema_version=1, findings=tuple(findings))
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
    for plugin_name in ("zellij-sessionizer.wasm", "zjstatus.wasm"):
        findings.append(
            _file_capability(
                f"zellij.{plugin_name}",
                repo_root / "generated/plugins" / plugin_name,
                f"Zellij plugin {plugin_name}",
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
