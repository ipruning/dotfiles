"""Shared ownership policy for the mise executable."""

from __future__ import annotations

import os
from pathlib import Path

from .host_policy import configured_mise_path

MISE_RELATIVE_PATH = Path(".local/bin/mise")


def canonical_mise_path(home: Path) -> Path:
    return configured_mise_path(home) or home / MISE_RELATIVE_PATH


def canonical_mise_executable(home: Path) -> str | None:
    """Return the owner-selected Mise binary when it is an executable file."""
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
