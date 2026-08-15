"""Read-only Skillshare configuration and ownership checks."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

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


def _skillshare_status(executable: Path, home: Path) -> dict[str, object]:
    command = (str(executable), "status", "--global", "--json")
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            env=environment,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f"Skillshare status could not run: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        reason = f"Skillshare status exited {completed.returncode}"
        raise RuntimeError(f"{reason}: {detail}" if detail else reason)
    try:
        document = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Skillshare status returned invalid JSON: {error}"
        ) from error
    if not isinstance(document, dict):
        raise RuntimeError("Skillshare status must be a JSON object")
    return document


def _skillshare_findings(home: Path, executable: Path | None) -> list[Finding]:
    if executable is None:
        return []
    config_path = home / ".config/skillshare/config.yaml"
    try:
        document = _skillshare_status(executable, home)
        source = document.get("source")
        targets = document.get("targets")
        tracked_repos = document.get("tracked_repos")
        if not isinstance(source, dict):
            raise RuntimeError("Skillshare status source must be an object")
        source_path = source.get("path")
        source_exists = source.get("exists")
        if not isinstance(source_path, str) or not source_path:
            raise RuntimeError("Skillshare status source.path must be a string")
        if not isinstance(source_exists, bool):
            raise RuntimeError("Skillshare status source.exists must be a boolean")
        if not isinstance(targets, list):
            raise RuntimeError("Skillshare status targets must be an array")
        if not isinstance(tracked_repos, list):
            raise RuntimeError("Skillshare status tracked_repos must be an array")
    except RuntimeError as error:
        return [
            Finding(
                "skillshare.status",
                Severity.WARN,
                "skillshare.status_unavailable",
                str(error),
                executable,
                f"Inspect with {executable} status --global --json.",
            ),
        ]

    findings = [
        Finding(
            "skillshare.config",
            Severity.OK,
            "skillshare.config_ready",
            "Skillshare accepted the global configuration",
            config_path,
        ),
        Finding(
            "skillshare.source",
            Severity.OK if source_exists else Severity.WARN,
            "skillshare.source_ready" if source_exists else "skillshare.source_missing",
            (
                "Skillshare reports that the configured source exists"
                if source_exists
                else "Skillshare reports that the configured source is missing"
            ),
            Path(source_path),
            None if source_exists else "Restore the source reported by Skillshare.",
        ),
    ]

    dirty_repos: list[str] = []
    for entry in tracked_repos:
        if not isinstance(entry, dict):
            return [
                _invalid_skillshare_status(executable, "tracked repo is not an object")
            ]
        name = entry.get("name")
        dirty = entry.get("dirty")
        skill_count = entry.get("skill_count")
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(dirty, bool)
            or type(skill_count) is not int
            or skill_count < 0
        ):
            return [
                _invalid_skillshare_status(
                    executable, "tracked repo has invalid fields"
                )
            ]
        if dirty:
            dirty_repos.append(name)
    findings.append(
        Finding(
            "skillshare.tracked_repos",
            Severity.WARN if dirty_repos else Severity.OK,
            (
                "skillshare.tracked_repos_dirty"
                if dirty_repos
                else "skillshare.tracked_repos_clean"
            ),
            (
                f"Skillshare reports dirty tracked repositories: {', '.join(dirty_repos)}"
                if dirty_repos
                else f"Skillshare reports {len(tracked_repos)} clean tracked repositories"
            ),
            Path(source_path),
            (
                "Inspect the tracked repositories before updating or synchronizing."
                if dirty_repos
                else None
            ),
        ),
    )

    if not targets:
        findings.append(
            Finding(
                "skillshare.targets",
                Severity.WARN,
                "skillshare.targets_missing",
                "Skillshare reports no configured Skill targets",
                config_path,
                "Declare host-specific targets before synchronizing Skills.",
            ),
        )
    for entry in targets:
        if not isinstance(entry, dict):
            return [_invalid_skillshare_status(executable, "target is not an object")]
        name = entry.get("name")
        path = entry.get("path")
        mode = entry.get("mode")
        status = entry.get("status")
        synced_count = entry.get("synced_count")
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(path, str)
            or not path
            or not isinstance(mode, str)
            or not mode
            or not isinstance(status, str)
            or not status
            or type(synced_count) is not int
            or synced_count < 0
        ):
            return [_invalid_skillshare_status(executable, "target has invalid fields")]
        ready = status in {"linked", "merged", "synced"}
        findings.append(
            Finding(
                f"skillshare.target.{name}",
                Severity.OK if ready else Severity.WARN,
                "skillshare.target_ready" if ready else "skillshare.target_unhealthy",
                f"Skillshare target {name} is {status} in {mode} mode with {synced_count} synced Skills",
                Path(path),
                None
                if ready
                else "Inspect with skillshare target list --global --json before synchronizing.",
            ),
        )
    return findings


def _invalid_skillshare_status(executable: Path, detail: str) -> Finding:
    return Finding(
        "skillshare.status",
        Severity.WARN,
        "skillshare.status_invalid",
        f"Skillshare status contains invalid fields: {detail}",
        executable,
        f"Inspect with {executable} status --global --json.",
    )


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
