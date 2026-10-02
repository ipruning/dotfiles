"""Read-only checks for the host private Git identity boundary."""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

from .models import Finding, Severity


def _git_config_defines_identity(config_path: Path) -> bool | None:
    for key in ("user.name", "user.email"):
        try:
            completed = subprocess.run(
                ["git", "config", "--file", str(config_path), "--get", key],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            return None
        if completed.returncode > 1:
            return None
        if completed.returncode == 1 or not completed.stdout.strip():
            return False
    return True


def _private_git_identity_ready(private_config: Path, home: Path) -> bool | None:
    direct_identity = _git_config_defines_identity(private_config)
    if direct_identity is True:
        return True
    if direct_identity is None:
        return None
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
        return None
    if completed.returncode > 1:
        return None
    if completed.returncode == 1:
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
    if not identity_configs:
        return False
    identity_states = [
        _git_config_defines_identity(config_path) for config_path in identity_configs
    ]
    if any(state is None for state in identity_states):
        return None
    return all(identity_states)


def _private_git_findings(home: Path) -> list[Finding]:
    gitconfig = home / ".gitconfig"
    private_config = home / ".private.gitconfig"
    include_present: bool | None = False
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
            if completed.returncode > 1:
                include_present = None
            else:
                include_present = (
                    completed.returncode == 0
                    and "~/.private.gitconfig" in completed.stdout.splitlines()
                )
        except OSError:
            include_present = None
    if include_present is None:
        include_finding = Finding(
            "git.private_include",
            Severity.WARN,
            "git.private_include_unavailable",
            "The private Git include could not be inspected",
            gitconfig,
            "Inspect ~/.gitconfig with git config --get-all include.path.",
        )
    else:
        include_finding = Finding(
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
        )
    findings = [
        include_finding,
    ]
    if not private_config.is_file():
        findings.append(
            Finding(
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
        Finding(
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
    if identity_ready is None:
        findings.append(
            Finding(
                "git.private_identity",
                Severity.WARN,
                "git.private_identity_unavailable",
                "Private Git identities could not be inspected",
                private_config,
                "Inspect user.name, user.email, and conditional identity includes with git config.",
            ),
        )
        return findings
    findings.append(
        Finding(
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
