"""Path confinement shared by restore (reference -> live) and adopt (live -> reference)."""

from __future__ import annotations

from pathlib import Path


def path_exists(path: Path) -> bool:
    """Treat a dangling symlink as an existing path."""
    return path.exists() or path.is_symlink()


def relative_path(path: Path, root: Path, label: str, error: type[Exception]) -> Path:
    try:
        relative = path.absolute().relative_to(root.absolute())
    except ValueError as cause:
        raise error(f"{label} is outside {root}: {path}") from cause
    if ".." in relative.parts:
        raise error(f"{label} traverses outside {root}: {path}")
    return relative


def validate_live_parent(live_path: Path, home: Path, error: type[Exception]) -> None:
    """Refuse live paths whose parent chain escapes home through a symlink.

    A leaf symlink is handled by the operation itself, but a symlinked parent
    directory would make restore link, or adopt copy, outside $HOME.
    """
    existing = live_path.parent
    while not path_exists(existing):
        if existing == existing.parent:
            raise error(f"live parent has no existing ancestor: {live_path}")
        existing = existing.parent
    relative_path(existing.resolve(), home.resolve(), "live parent", error)
