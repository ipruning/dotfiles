"""Shared fixtures for repository behavior tests."""

from __future__ import annotations

import os
import subprocess
import sys
from functools import cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def mackup_cfg(applications: str = "") -> str:
    """Return a minimal Mackup storage config selecting the given applications."""
    return (
        "[storage]\nengine = file_system\npath = dotfiles\n"
        f"directory = reference\n[applications_to_sync]\n{applications}"
    )


@cache
def _uv_environment() -> tuple[str, str]:
    uv_dir = Path(
        subprocess.run(
            ["mise", "which", "uv"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
    ).parent
    uv_cache = subprocess.run(
        [uv_dir / "uv", "cache", "dir"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return str(uv_dir), uv_cache


def run_scripts_module(
    module: str,
    home: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    """Run a scripts.<module> CLI against an isolated home with real uv access."""
    uv_dir, uv_cache = _uv_environment()
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    environment["XDG_CONFIG_HOME"] = str(home / ".config")
    environment["PATH"] = f"{uv_dir}{os.pathsep}{environment['PATH']}"
    environment["UV_CACHE_DIR"] = uv_cache
    return subprocess.run(
        [sys.executable, "-m", f"scripts.{module}", *arguments],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
