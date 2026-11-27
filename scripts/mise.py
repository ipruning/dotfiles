"""Shared ownership policy for the mise executable."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .host_policy import configured_mise_path

MISE_RELATIVE_PATH = Path(".local/bin/mise")
PREFERRED_GITHUB_USERS = ("alex-jhs",)


def canonical_mise_path(home: Path) -> Path:
    return configured_mise_path(home) or home / MISE_RELATIVE_PATH


def canonical_mise_executable(home: Path) -> str | None:
    """Return the owner-selected mise binary when it is an executable file."""
    executable = canonical_mise_path(home)
    try:
        if not executable.is_file():
            return None
        if not os.access(executable, os.X_OK):
            return None
    except OSError:
        return None
    return str(executable)


def canonical_mise_environment(home: Path) -> dict[str, str]:
    """Return an environment where mise cannot choose another owner from PATH."""
    environment = os.environ.copy()
    canonical_directory = str(canonical_mise_path(home).parent)
    current_entries = environment.get("PATH", "").split(os.pathsep)
    environment["PATH"] = os.pathsep.join(
        [
            canonical_directory,
            *[
                entry
                for entry in current_entries
                if entry and entry != canonical_directory
            ],
        ],
    )
    return environment


def mise_github_environment(home: Path) -> dict[str, str]:
    """Return canonical mise env with a dynamic gh token when no static token is set."""
    environment = canonical_mise_environment(home)
    if environment.get("MISE_GITHUB_TOKEN") or environment.get("GH_TOKEN"):
        return environment
    gh = shutil.which("gh", path=environment.get("PATH", ""))
    if gh is None:
        return environment
    candidates: list[list[str]] = [
        [gh, "auth", "token", "--user", user] for user in PREFERRED_GITHUB_USERS
    ]
    candidates.append([gh, "auth", "token"])
    for command in candidates:
        try:
            completed = subprocess.run(
                command,
                env=environment,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except OSError, subprocess.TimeoutExpired:
            continue
        token = completed.stdout.strip()
        if completed.returncode == 0 and token:
            environment["MISE_GITHUB_TOKEN"] = token
            break
    return environment
