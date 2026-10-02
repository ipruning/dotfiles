"""Inspect the Herdr installation conflicts observed on managed hosts."""

from __future__ import annotations

import hashlib
import platform
import tomllib
from pathlib import Path

from .models import Finding, Severity


def inspect_herdr(
    home: Path,
    *,
    system_paths: tuple[Path, ...] = tuple(
        Path("/").joinpath(*parts)
        for parts in (
            ("opt", "homebrew", "bin", "herdr"),
            ("usr", "local", "bin", "herdr"),
        )
    ),
) -> list[Finding]:
    """Read known candidates and verify the locked active Mise artifact."""
    findings: list[Finding] = []
    installations = home / ".local/share/mise/installs/herdr"
    owners: dict[str, Path] = {}
    try:
        if installations.is_dir() and any(installations.glob("*/herdr")):
            owners["mise"] = installations
        for executable in (home / ".local/bin/herdr", *system_paths):
            if not executable.is_file():
                continue
            resolved = executable.resolve()
            if resolved.is_relative_to(installations):
                continue
            owner = "Homebrew" if "Cellar" in resolved.parts else str(resolved)
            owners[owner] = executable
        if len(owners) > 1:
            findings.append(
                Finding(
                    "herdr.ownership",
                    Severity.WARN,
                    "herdr.multiple_owners",
                    "Herdr has multiple installation owners: "
                    + "; ".join(f"{owner}: {path}" for owner, path in owners.items()),
                    installations,
                    "Keep the selected owner; explicitly uninstall the other copy "
                    "with its original installer after checking running sessions.",
                )
            )
        lock = home / ".config/mise/mise.lock"
        if not lock.is_file():
            return findings
        document = tomllib.loads(lock.read_text())
        entries = document.get("tools", {}).get("herdr", [])
        target = (
            "macos-arm64"
            if platform.system() == "Darwin" and platform.machine() == "arm64"
            else "macos-x64"
            if platform.system() == "Darwin"
            else "linux-arm64"
            if platform.machine() in {"aarch64", "arm64"}
            else "linux-x64"
        )
        for entry in entries:
            binary = installations / entry["version"] / "herdr"
            checksum = entry.get(f"platforms.{target}", {}).get("checksum", "")
            if not binary.is_file() or not checksum.startswith("sha256:"):
                continue
            actual = "sha256:" + hashlib.sha256(binary.read_bytes()).hexdigest()
            if actual != checksum:
                findings.append(
                    Finding(
                        "herdr.artifact",
                        Severity.ERROR,
                        "herdr.checksum_mismatch",
                        f"Herdr binary differs from its lock: expected {checksum}; actual {actual}",
                        binary,
                        "Inspect running sessions, then explicitly reinstall this "
                        "locked Herdr version with Mise; do not run herdr update on it.",
                    )
                )
    except (OSError, ValueError, KeyError, TypeError) as error:
        findings.append(
            Finding(
                "herdr.inspection",
                Severity.WARN,
                "herdr.inspection_failed",
                f"Herdr ownership inspection failed: {error}",
                installations,
                "Inspect the candidate paths and the global Mise lockfile.",
            )
        )
    return findings
