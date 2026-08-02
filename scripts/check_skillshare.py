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
SKILLSHARE_OWNERSHIP_ACTION = (
    "Inspect with ~/.local/bin/mise ls github:runkids/skillshare --installed "
    "--json and brew list --versions skillshare, then retain one owner."
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
    if not isinstance(mode, str):
        raise TypeError(f"targets.{name}.skills.mode must be a string")
    return _expand_home(path_value, home), mode or "merge"


def _target_skill_entries(
    target_path: Path,
    source: Path,
) -> tuple[list[str], list[str], list[str]]:
    local: list[str] = []
    broken_links: list[str] = []
    external_links: list[str] = []
    for entry in sorted(target_path.iterdir(), key=lambda item: item.name):
        if entry.name.startswith("."):
            continue
        if entry.is_symlink():
            if not entry.exists():
                broken_links.append(entry.name)
            elif not _path_within(entry.resolve(), source.resolve()):
                external_links.append(entry.name)
            continue
        if entry.is_dir() and (entry / "SKILL.md").is_file():
            local.append(entry.name)
    return local, broken_links, external_links


def _skillshare_target_findings(
    document: object,
    home: Path,
    source: Path,
) -> list[Finding]:
    findings: list[Finding] = []
    config_path = home / ".config/skillshare/config.yaml"
    targets = document.get("targets") if isinstance(document, dict) else None
    if not isinstance(targets, dict) or not targets:
        return [
            Finding(
                "skillshare.targets",
                Severity.WARN,
                "skillshare.targets_missing",
                "Skillshare configuration declares no Skill targets to inspect",
                config_path,
                "Declare host-specific targets before synchronizing Skills.",
            ),
        ]

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
        except TypeError as error:
            findings.append(
                Finding(
                    f"skillshare.target.{name}",
                    Severity.WARN,
                    "skillshare.target_invalid",
                    f"Skillshare target {name} is invalid: {error}",
                    config_path,
                    "Inspect the host-specific Skillshare target configuration.",
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
        if not target_path.is_dir():
            findings.append(
                Finding(
                    f"skillshare.target.{name}",
                    Severity.WARN,
                    "skillshare.target_directory_missing",
                    f"Skillshare target {name} directory is missing",
                    target_path,
                    "Inspect with skillshare target list --json.",
                ),
            )
            continue

        try:
            local, broken_links, external_links = _target_skill_entries(
                target_path,
                source,
            )
        except OSError as error:
            findings.append(
                Finding(
                    f"skillshare.target.{name}",
                    Severity.WARN,
                    "skillshare.target_inspection_unavailable",
                    f"Skillshare target {name} could not be inspected: {error}",
                    target_path,
                    "Inspect the target directory permissions and accessibility.",
                ),
            )
            continue
        if local:
            findings.append(
                Finding(
                    f"skillshare.target.{name}",
                    Severity.WARN,
                    "skillshare.target_local_skills",
                    f"Skillshare target {name} has {len(local)} non-symlink Skill entries: {', '.join(local)}",
                    target_path,
                    "Preview actual sync behavior with skillshare sync --all --global --dry-run --force --json and report local and pruned separately. local > 0 with pruned == 0 is preserved but still needs Operator ownership; pruned > 0 is planned deletion and requires explicit confirmation. If the preview fails, report that inspection is incomplete.",
                ),
            )
        if broken_links:
            findings.append(
                Finding(
                    f"skillshare.target.{name}",
                    Severity.WARN,
                    "skillshare.target_broken_links",
                    f"Skillshare target {name} has {len(broken_links)} broken Skill links: {', '.join(broken_links)}",
                    target_path,
                    "Inspect the configured source and target before an explicit synchronization.",
                ),
            )
        if external_links:
            findings.append(
                Finding(
                    f"skillshare.target.{name}",
                    Severity.WARN,
                    "skillshare.target_external_links",
                    f"Skillshare target {name} has {len(external_links)} Skill links outside the configured source: {', '.join(external_links)}",
                    target_path,
                    "Inspect link ownership before an explicit synchronization.",
                ),
            )
        if not local and not broken_links and not external_links:
            findings.append(
                Finding(
                    f"skillshare.target.{name}",
                    Severity.OK,
                    "skillshare.target_inspected",
                    f"Skillshare target {name} is configured at {target_path} in {mode} mode; no target-local Skills, broken links, or links outside the configured source were observed",
                    target_path,
                ),
            )
    return findings


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
        document = YAML(typ="safe").load(config_path)
        source_value = document["sources"]["skills"]
        if not isinstance(source_value, str):
            raise TypeError("sources.skills must be a string")
        source = _expand_home(source_value, home)
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
    findings = [
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
    findings.extend(_skillshare_target_findings(document, home, source))
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
    try:
        mise_installations = _mise_skillshare_installations(home)
    except RuntimeError as error:
        return Finding(
            "skillshare.ownership",
            Severity.WARN,
            "skillshare.ownership_unavailable",
            str(error),
            canonical_mise_path(home),
            SKILLSHARE_OWNERSHIP_ACTION,
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
            SKILLSHARE_OWNERSHIP_ACTION,
        )
    return Finding(
        "skillshare.ownership",
        Severity.OK,
        "skillshare.ownership_single",
        f"Skillshare has one installation owner: {descriptions[0]}",
        path,
    )
