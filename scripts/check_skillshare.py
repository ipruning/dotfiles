"""Read-only Skillshare configuration and health checks."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .models import Finding, Severity


def _expand_home(value: str, home: Path) -> Path:
    if value == "~":
        return home
    if value.startswith("~/"):
        return home / value[2:]
    return Path(value)


def _configured_skillshare_source(config_path: Path, home: Path) -> Path:
    document = YAML(typ="safe").load(config_path)
    source_value = document["sources"]["skills"]
    if not isinstance(source_value, str):
        raise TypeError("sources.skills must be a string")
    return _expand_home(source_value, home)


def _skillshare_findings(home: Path) -> list[Finding]:
    config_path = home / ".config/skillshare/config.yaml"
    if not config_path.is_file():
        return [
            Finding(
                "skillshare.config",
                Severity.WARN,
                "skillshare.config_missing",
                "Skillshare configuration is missing",
                config_path,
                "Create a host-specific Skillshare config; do not copy harness extras blindly.",
            ),
        ]
    try:
        source = _configured_skillshare_source(config_path, home)
    except (OSError, KeyError, TypeError, YAMLError) as error:
        return [
            Finding(
                "skillshare.config",
                Severity.WARN,
                "skillshare.config_invalid",
                f"Skillshare configuration cannot identify sources.skills: {error}",
                config_path,
                "Repair sources.skills in the host-specific Skillshare config.",
            ),
        ]
    return [
        Finding(
            "skillshare.config",
            Severity.OK,
            "skillshare.config_ready",
            "Skillshare configuration is readable",
            config_path,
        ),
        Finding(
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


def _skillshare_resource_containers(details: object, home: Path) -> bool:
    if not isinstance(details, list) or not details:
        return False
    containers: list[str] = []
    for detail in details:
        if not isinstance(detail, str):
            return False
        containers.append(detail)
    config_path = home / ".config/skillshare/config.yaml"
    try:
        source = _configured_skillshare_source(config_path, home)
    except OSError, KeyError, TypeError, YAMLError:
        return False
    for detail in containers:
        if detail == "extras":
            continue
        relative = Path(detail)
        if relative.is_absolute() or ".." in relative.parts:
            return False
        container = source / relative
        try:
            if not any(
                (child / "SKILL.md").is_file()
                for child in container.iterdir()
                if child.is_dir()
            ):
                return False
        except OSError:
            return False
    return True


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
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return Finding(
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
        issues: list[str] = []
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
                raw_message = raw_check.get("message")
                if raw_message is not None and not isinstance(raw_message, str):
                    raise TypeError("check message must be a string")
                known_resource_warning = (
                    name == "skills_validity"
                    and _skillshare_resource_containers(details, home)
                )
                description = name
                if raw_message:
                    description = f"{name}: {' '.join(raw_message.split())}"
                elif isinstance(details, list) and all(
                    isinstance(detail, str) for detail in details
                ):
                    description = f"{name}: {', '.join(details)}"
                if check_status == "error":
                    reported_errors += 1
                    issues.append(description)
                elif (
                    check_status == "warning"
                    and name not in ignored_warnings
                    and not known_resource_warning
                ):
                    actionable_warnings += 1
                    issues.append(description)
            warnings = actionable_warnings
            errors = reported_errors
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        return Finding(
            "skillshare.doctor",
            Severity.WARN,
            "skillshare.doctor_invalid",
            f"Skillshare doctor returned invalid JSON: {error}",
            action="Run skillshare doctor --json and inspect its output.",
        )
    if errors or completed.returncode != 0:
        return Finding(
            "skillshare.doctor",
            Severity.WARN,
            "skillshare.doctor_failed",
            f"Skillshare doctor reports {errors} error(s) and "
            f"{warnings} actionable warning(s)"
            + (f": {'; '.join(issues)}" if issues else ""),
            action="Resolve doctor errors before treating Skillshare as ready.",
        )
    if warnings:
        return Finding(
            "skillshare.doctor",
            Severity.WARN,
            "skillshare.doctor_warnings",
            f"Skillshare doctor reports {warnings} actionable warning(s)"
            + (f": {'; '.join(issues)}" if issues else ""),
            action="Run skillshare doctor --json and resolve the listed warnings.",
        )
    return Finding(
        "skillshare.doctor",
        Severity.OK,
        "skillshare.doctor_ready",
        "Skillshare doctor reports no errors or warnings",
    )
