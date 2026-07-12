"""Inspect host capabilities without installing or changing them."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import stat
import subprocess
from collections.abc import Callable
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .models import CheckReport, Finding, Severity
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
        ),
    ]


def _file_capability(check: str, file_path: Path, label: str) -> Finding:
    exists = file_path.is_file()
    return _finding(
        check,
        Severity.OK if exists else Severity.WARN,
        f"{check}_{'ready' if exists else 'missing'}",
        f"{label} {'exists' if exists else 'is missing'}",
        file_path,
    )


def inspect_host(
    repo_root: Path,
    home: Path,
    *,
    executable_finder: ExecutableFinder = shutil.which,
    system_name: str | None = None,
) -> CheckReport:
    """Return explicit required and optional capabilities for this host."""
    findings = [
        _check_executable(
            command,
            required=True,
            executable_finder=executable_finder,
        )
        for command in ("git", "python", "uv", "mise")
    ]
    findings.extend(_private_git_findings(home))
    findings.append(
        _check_executable(
            "skillshare",
            required=False,
            executable_finder=executable_finder,
        ),
    )
    findings.extend(_skillshare_findings(home))
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
        directory_path = repo_root / "generated" / directory
        findings.append(
            _finding(
                f"shell.{directory}",
                Severity.OK if directory_path.is_dir() else Severity.WARN,
                f"shell.{directory}_{'ready' if directory_path.is_dir() else 'missing'}",
                f"Generated shell {directory} directory "
                f"{'exists' if directory_path.is_dir() else 'is missing'}",
                directory_path,
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
    active_system = system_name or platform.system()
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
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    report = inspect_host(repo_root, Path.home())
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
