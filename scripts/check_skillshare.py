"""Read-only Skillshare configuration and ownership checks."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import cast

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .mise import (
    canonical_mise_environment,
    canonical_mise_executable,
    canonical_mise_path,
)
from .models import Finding, Severity

SKILLSHARE_MISE_TOOL = "github:runkids/skillshare"
SKILLSHARE_SYSTEM_PATHS = tuple(
    Path("/").joinpath(*parts)
    for parts in (
        ("opt", "homebrew", "bin", "skillshare"),
        ("home", "linuxbrew", ".linuxbrew", "bin", "skillshare"),
        ("usr", "local", "bin", "skillshare"),
    )
)


def _expand_home(value: str, home: Path) -> Path:
    if value == "~":
        return home
    if value.startswith("~/"):
        return home / value[2:]
    return Path(value)


def _configured_skillshare_target(
    document: object,
    name: str,
    home: Path,
) -> tuple[Path, str]:
    if not isinstance(document, dict):
        raise TypeError("configuration must be a mapping")
    targets = document.get("targets")
    if not isinstance(targets, dict) or name not in targets:
        raise KeyError(name)
    target = cast("dict[str, object]", targets)[name]
    if not isinstance(target, dict):
        raise TypeError(f"targets.{name} must be a mapping")
    skills = target.get("skills")
    if not isinstance(skills, dict):
        raise TypeError(f"targets.{name}.skills must be a mapping")
    path_value = skills.get("path")
    if not isinstance(path_value, str) or not path_value:
        raise TypeError(f"targets.{name}.skills.path must be a string")
    mode = skills.get("mode", document.get("mode", "merge"))
    if not isinstance(mode, str) or not mode:
        raise TypeError(f"targets.{name}.skills.mode must be a non-empty string")
    return _expand_home(path_value, home), mode


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
                "Create a host-specific Skillshare configuration.",
            ),
        ]
    try:
        document = YAML(typ="safe").load(config_path)
        if not isinstance(document, dict):
            raise TypeError("configuration must be a mapping")
        sources = document.get("sources")
        if not isinstance(sources, dict):
            raise TypeError("sources must be a mapping")
        source_value = sources.get("skills")
        if not isinstance(source_value, str) or not source_value:
            raise TypeError("sources.skills must be a non-empty string")
        source_path = _expand_home(source_value, home)
        targets = document.get("targets")
        if targets is not None and not isinstance(targets, dict):
            raise TypeError("targets must be a mapping")
    except (OSError, TypeError, YAMLError) as error:
        return [
            Finding(
                "skillshare.config",
                Severity.WARN,
                "skillshare.config_invalid",
                f"Skillshare configuration is unreadable or invalid: {error}",
                config_path,
                "Repair the host-specific Skillshare configuration.",
            ),
        ]

    findings = [
        Finding(
            "skillshare.config",
            Severity.OK,
            "skillshare.config_ready",
            "Skillshare configuration is structurally readable",
            config_path,
        ),
        Finding(
            "skillshare.source",
            Severity.OK if source_path.is_dir() else Severity.WARN,
            (
                "skillshare.source_ready"
                if source_path.is_dir()
                else "skillshare.source_missing"
            ),
            (
                "Configured Skillshare source directory exists"
                if source_path.is_dir()
                else "Configured Skillshare source directory is missing"
            ),
            source_path,
            None
            if source_path.is_dir()
            else "Restore the configured Skillshare source directory.",
        ),
    ]

    if not targets:
        findings.append(
            Finding(
                "skillshare.targets",
                Severity.WARN,
                "skillshare.targets_missing",
                "Skillshare configuration declares no Skill targets",
                config_path,
                "Declare host-specific targets before synchronizing Skills.",
            ),
        )
        return findings

    inspected_paths: dict[Path, str] = {}
    for raw_name in sorted(targets, key=str):
        if not isinstance(raw_name, str) or not raw_name:
            findings.append(
                Finding(
                    "skillshare.targets",
                    Severity.WARN,
                    "skillshare.target_invalid",
                    "Skillshare target names must be non-empty strings",
                    config_path,
                    "Repair the target name before synchronizing Skills.",
                ),
            )
            continue
        name = raw_name
        try:
            target_path, mode = _configured_skillshare_target(document, name, home)
        except (KeyError, TypeError) as error:
            findings.append(
                Finding(
                    f"skillshare.target.{name}",
                    Severity.WARN,
                    "skillshare.target_invalid",
                    f"Skillshare target {name} is invalid: {error}",
                    config_path,
                    "Repair the host-specific Skillshare target configuration.",
                ),
            )
            continue
        if previous_name := inspected_paths.get(target_path):
            findings.append(
                Finding(
                    f"skillshare.target.{name}",
                    Severity.WARN,
                    "skillshare.target_duplicate_path",
                    f"Skillshare targets {previous_name} and {name} point to the same directory",
                    target_path,
                    "Give each target a distinct path or remove the duplicate declaration.",
                ),
            )
            continue
        inspected_paths[target_path] = name
        target_exists = target_path.is_dir()
        findings.append(
            Finding(
                f"skillshare.target.{name}",
                Severity.OK if target_exists else Severity.WARN,
                (
                    "skillshare.target_ready"
                    if target_exists
                    else "skillshare.target_directory_missing"
                ),
                (
                    f"Configured Skillshare target {name} directory exists in {mode} mode"
                    if target_exists
                    else f"Configured Skillshare target {name} directory is missing in {mode} mode"
                ),
                target_path,
                None
                if target_exists
                else "Create or synchronize this target with an explicit Skillshare operation.",
            ),
        )
    return findings


def _path_within(file_path: Path, directory: Path) -> bool:
    try:
        return file_path.is_relative_to(directory)
    except OSError, ValueError:
        return False


def _mise_skillshare_installations(home: Path) -> list[tuple[str, Path, bool]]:
    mise = canonical_mise_executable(home)
    if mise is None:
        return []
    command = (
        mise,
        "ls",
        SKILLSHARE_MISE_TOOL,
        "--installed",
        "--json",
    )
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            env=canonical_mise_environment(home),
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(
            f"Mise Skillshare inventory could not run: {error}"
        ) from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        reason = f"Mise Skillshare inventory exited {completed.returncode}"
        raise RuntimeError(f"{reason}: {detail}" if detail else reason)
    try:
        document = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Mise Skillshare inventory returned invalid JSON: {error}"
        ) from error
    if not isinstance(document, list):
        raise RuntimeError("Mise Skillshare inventory must be a JSON array")

    installations: list[tuple[str, Path, bool]] = []
    for raw_installation in document:
        if not isinstance(raw_installation, dict):
            raise RuntimeError("Mise Skillshare inventory contains a non-object entry")
        version = raw_installation.get("version")
        install_path = raw_installation.get("install_path")
        installed = raw_installation.get("installed")
        active = raw_installation.get("active")
        if (
            not isinstance(version, str)
            or not version
            or not isinstance(install_path, str)
            or not install_path
            or not isinstance(installed, bool)
            or not isinstance(active, bool)
        ):
            raise RuntimeError("Mise Skillshare inventory contains invalid fields")
        if installed:
            installations.append((version, Path(install_path), active))
    return installations


def _candidate_skillshare_owners(
    home: Path,
    executable: Path | None,
    mise_installations: list[tuple[str, Path, bool]],
) -> dict[str, tuple[str, Path]]:
    candidates = [home / ".local/bin/skillshare", *SKILLSHARE_SYSTEM_PATHS]
    if executable is not None:
        candidates.append(executable)
    canonical_mise = canonical_mise_path(home).resolve()
    owners: dict[str, tuple[str, Path]] = {}
    for candidate in candidates:
        try:
            if not candidate.is_file() or not os.access(candidate, os.X_OK):
                continue
            resolved = candidate.resolve(strict=True)
        except OSError:
            continue
        if resolved == canonical_mise:
            # A Mise shim is a dispatcher, not an independent Skillshare owner.
            continue
        if any(
            _path_within(resolved, install_path.resolve())
            for _version, install_path, _active in mise_installations
        ):
            continue
        identity = str(resolved)
        if "Cellar/skillshare" in identity:
            label = f"Homebrew at {candidate} -> {resolved}"
        elif candidate == home / ".local/bin/skillshare":
            label = f"standalone at {candidate}"
        else:
            label = f"system/PATH at {candidate} -> {resolved}"
        owners.setdefault(identity, (label, candidate))
    return owners


def _skillshare_ownership_finding(
    home: Path,
    executable: Path | None,
) -> Finding | None:
    ownership_action = (
        f"Inspect with {canonical_mise_path(home)} ls {SKILLSHARE_MISE_TOOL} "
        "--installed --json and brew list --versions skillshare, then retain one owner."
    )
    try:
        mise_installations = _mise_skillshare_installations(home)
    except RuntimeError as error:
        return Finding(
            "skillshare.ownership",
            Severity.WARN,
            "skillshare.ownership_unavailable",
            str(error),
            canonical_mise_path(home),
            ownership_action,
        )

    owners = _candidate_skillshare_owners(home, executable, mise_installations)
    descriptions = (
        [
            "Mise "
            + ", ".join(
                f"{version} ({'active' if active else 'inactive'}) at {install_path}"
                for version, install_path, active in mise_installations
            )
        ]
        if mise_installations
        else []
    )
    descriptions.extend(label for label, _path in owners.values())
    owner_count = bool(mise_installations) + len(owners)
    if owner_count == 0:
        return None
    path = (
        next(candidate for _label, candidate in owners.values())
        if owners
        else mise_installations[0][1]
    )
    if owner_count > 1:
        return Finding(
            "skillshare.ownership",
            Severity.WARN,
            "skillshare.ownership_multiple",
            f"Multiple independent Skillshare owners coexist: {'; '.join(descriptions)}",
            path,
            ownership_action,
        )
    return Finding(
        "skillshare.ownership",
        Severity.OK,
        "skillshare.ownership_single",
        f"Skillshare has one installation owner: {descriptions[0]}",
        path,
    )
