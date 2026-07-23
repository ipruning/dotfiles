"""Shared ownership policy for the mise executable."""

from __future__ import annotations

import os
from pathlib import Path

MISE_RELATIVE_PATH = Path(".local/bin/mise")


def canonical_mise_path(home: Path) -> Path:
    return home / MISE_RELATIVE_PATH


def canonical_mise_executable(home: Path) -> str | None:
    """Return the standalone mise binary only when it can self-update in place."""
    executable = canonical_mise_path(home)
    try:
        if executable.is_symlink() or not executable.is_file():
            return None
        if not os.access(executable, os.X_OK):
            return None
    except OSError:
        return None
    return str(executable)
