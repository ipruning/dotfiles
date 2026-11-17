"""Inspect whether host-bound paths in the repository resolve on this host."""

from __future__ import annotations

from pathlib import Path

from .lint import HostBoundPath, host_bound_paths
from .models import Finding, Severity

MACOS_ONLY_PREFIXES = ("/Applications/", "/opt/homebrew")


def _expanded(raw: str, home: Path) -> Path:
    normalized = raw.replace("\\ ", " ")
    if normalized.startswith("/Applications/") and ".app/" in normalized:
        normalized = normalized[: normalized.index(".app/") + len(".app")]
    for prefix in ("~/", "$HOME/", "${HOME}/"):
        if normalized.startswith(prefix):
            return home / normalized[len(prefix) :]
    return Path(normalized)


def _live_counterpart(repo_root: Path, home: Path, source: Path) -> Path | None:
    try:
        relative = source.relative_to(repo_root / "reference")
    except ValueError:
        return None
    return home / relative


def _missing_reference_path(
    repo_root: Path, home: Path, system_name: str, bound: HostBoundPath
) -> Finding | None:
    live = _live_counterpart(repo_root, home, bound.source)
    if live is None or not (live.exists() or live.is_symlink()):
        return None
    if system_name != "Darwin" and bound.raw.startswith(MACOS_ONLY_PREFIXES):
        return None
    if _expanded(bound.raw, home).exists():
        return None
    location = f"{live}:{bound.line}" if bound.line is not None else str(live)
    return Finding(
        "reference.host_paths",
        Severity.WARN,
        f"reference.{bound.kind}_missing",
        f"{location} refers to {bound.raw}, which does not exist on this host",
        bound.source,
        "Create the path on this host or remove it from the reference.",
    )


def host_path_findings(repo_root: Path, home: Path, system_name: str) -> list[Finding]:
    """Report live configurations and repository paths that miss on this host."""
    bound_paths, unreadable_toml = host_bound_paths(repo_root)
    findings = [
        finding
        for bound in bound_paths
        if bound.kind != "dotfiles_root"
        and (finding := _missing_reference_path(repo_root, home, system_name, bound))
    ]
    for source in unreadable_toml:
        live = _live_counterpart(repo_root, home, source)
        if live is not None and (live.exists() or live.is_symlink()):
            findings.append(
                Finding(
                    "reference.host_paths",
                    Severity.WARN,
                    "reference.host_paths_toml_invalid",
                    f"Unable to read valid TOML from {source} for the host path check",
                    source,
                    "Inspect the reference TOML and run mise run check again.",
                )
            )
    expected_root = (home / "dotfiles").resolve()
    if repo_root.resolve() != expected_root and any(
        bound.kind == "dotfiles_root" for bound in bound_paths
    ):
        findings.append(
            Finding(
                "reference.repo_location",
                Severity.WARN,
                "reference.repo_location_mismatch",
                f"Tracked files assume the repository at {expected_root}",
                repo_root,
                f"Move the checkout to {expected_root}.",
            ),
        )
    return findings or [
        Finding(
            "reference.host_paths",
            Severity.OK,
            "reference.host_paths_resolved",
            "Host-bound paths in live configurations resolve on this host",
        ),
    ]
