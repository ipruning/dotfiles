"""Read-only Mise ownership and service dependency checks."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from .mise import (
    canonical_mise_environment,
    canonical_mise_executable,
    canonical_mise_path,
)
from .models import ExecutableFinder, Finding, Severity

MISE_COMMON_LOCATIONS = tuple(
    Path("/").joinpath(*parts)
    for parts in (
        ("opt", "homebrew", "bin", "mise"),
        ("usr", "local", "bin", "mise"),
        ("home", "linuxbrew", ".linuxbrew", "bin", "mise"),
        ("usr", "bin", "mise"),
        ("snap", "bin", "mise"),
    )
)
MISE_BINDING_PATTERN = re.compile(r"(?<![\w])(/[^\s\"'()]+/mise)(?=[\s\"'();]|$)")
SYSTEMD_SERVICE_EXEC_DIRECTIVES = {
    "ExecCondition",
    "ExecStartPre",
    "ExecStart",
    "ExecStartPost",
    "ExecReload",
    "ExecStop",
    "ExecStopPost",
}


def _executable_file(file_path: Path) -> bool:
    try:
        return file_path.is_file() and os.access(file_path, os.X_OK)
    except OSError:
        return False


def _same_file(left: Path, right: Path) -> bool:
    try:
        return left.samefile(right)
    except OSError:
        return False


def _mise_candidate_paths(
    executable_finder: ExecutableFinder,
    *,
    scan_host_path: bool,
) -> tuple[Path, ...]:
    candidates: list[Path] = []
    if found := executable_finder("mise"):
        candidates.append(Path(found).expanduser())
    if scan_host_path:
        candidates.extend(
            Path(entry).expanduser() / "mise"
            for entry in os.environ.get("PATH", "").split(os.pathsep)
            if entry
        )
        candidates.extend(MISE_COMMON_LOCATIONS)
    return tuple(candidates)


def _mise_installation_findings(
    home: Path,
    *,
    executable_finder: ExecutableFinder,
    scan_host_path: bool,
) -> list[Finding]:
    canonical = canonical_mise_path(home)
    canonical_ready = canonical_mise_executable(home) is not None
    if canonical_ready:
        canonical_finding = Finding(
            "mise.canonical",
            Severity.OK,
            "mise.canonical_ready",
            "The standalone mise executable is ready at its canonical location",
            canonical,
        )
    else:
        state = "symlinked" if canonical.is_symlink() else "missing_or_invalid"
        canonical_finding = Finding(
            "mise.canonical",
            Severity.WARN,
            f"mise.canonical_{state}",
            "The canonical standalone mise executable is missing, symlinked, or not executable",
            canonical,
            "Install standalone mise at ~/.local/bin/mise with https://mise.run.",
        )

    alternatives: dict[str, Path] = {}
    for candidate in _mise_candidate_paths(
        executable_finder,
        scan_host_path=scan_host_path,
    ):
        if candidate == canonical or not _executable_file(candidate):
            continue
        if canonical_ready and _same_file(candidate, canonical):
            continue
        try:
            identity = str(candidate.resolve(strict=True))
        except OSError:
            identity = str(candidate.absolute())
        alternatives.setdefault(identity, candidate)

    if alternatives:
        paths = ", ".join(str(file_path) for file_path in alternatives.values())
        installations_finding = Finding(
            "mise.installations",
            Severity.WARN,
            "mise.installations_multiple",
            f"Additional mise executable installations exist outside the canonical path: {paths}",
            next(iter(alternatives.values())),
            "Remove package-managed mise copies after ~/.local/bin/mise is ready.",
        )
    else:
        installations_finding = Finding(
            "mise.installations",
            Severity.OK,
            "mise.installations_single",
            "No alternate mise executable installation was found",
            canonical,
        )
    return [canonical_finding, installations_finding]


def _mise_shim_finding(home: Path) -> Finding | None:
    shims_directory = home / ".local/share/mise/shims"
    if not shims_directory.exists():
        return None
    canonical = canonical_mise_path(home)
    canonical_ready = canonical_mise_executable(home) is not None
    canonical_count = 0
    stale: list[tuple[Path, Path]] = []
    try:
        entries = sorted(shims_directory.iterdir())
        for shim in entries:
            if not shim.is_symlink():
                continue
            raw_target = Path(os.readlink(shim))
            target = (
                raw_target if raw_target.is_absolute() else shim.parent / raw_target
            )
            if target.name != "mise":
                continue
            if canonical_ready and _same_file(target, canonical):
                canonical_count += 1
            else:
                stale.append((shim, target))
    except OSError as error:
        return Finding(
            "mise.shims",
            Severity.WARN,
            "mise.shims_unreadable",
            f"Mise shim ownership cannot be inspected: {error}",
            shims_directory,
            "Make the shim directory readable, then run mise run check again.",
        )
    if stale:
        targets = ", ".join(sorted({str(target) for _shim, target in stale}))
        return Finding(
            "mise.shims",
            Severity.WARN,
            "mise.shims_stale",
            f"Mise shims are not owned by the valid canonical executable; targets: {targets}",
            stale[0][0],
            (
                "Run mise run mise-sync, then mise run mise-sync -- --apply."
                if canonical_ready
                else "Install standalone mise at ~/.local/bin/mise before rebuilding shims."
            ),
        )
    if canonical_count:
        return Finding(
            "mise.shims",
            Severity.OK,
            "mise.shims_ready",
            f"All {canonical_count} mise-owned shims target the canonical executable",
            shims_directory,
        )
    return None


def _mise_project_uv_finding(repo_root: Path, home: Path) -> Finding | None:
    config_path = repo_root / "mise.toml"
    executable = canonical_mise_executable(home)
    if not config_path.is_file() or executable is None:
        return None
    command = (executable, "which", "uv", "-C", str(repo_root))
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            env=canonical_mise_environment(home),
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        reason = "the read-only lookup timed out after 10s"
    except OSError as error:
        reason = f"the read-only lookup could not run: {error}"
    else:
        resolved = completed.stdout.strip()
        if completed.returncode == 0 and resolved:
            return Finding(
                "mise.project_uv",
                Severity.OK,
                "mise.project_uv_ready",
                "Canonical Mise resolves the project's locked uv executable",
                Path(resolved),
            )
        reason = f"mise which uv exited {completed.returncode}"
    return Finding(
        "mise.project_uv",
        Severity.WARN,
        "mise.project_uv_unresolved",
        f"Canonical Mise cannot resolve the project's locked uv executable: {reason}",
        config_path,
        (
            "Inspect with ~/.local/bin/mise ls uv --installed --json and "
            "~/.local/bin/mise which uv. Reinstall the exact locked uv version if "
            "its recorded backend no longer matches its executable layout."
        ),
    )


def _mise_systemd_shim_findings(
    home: Path,
    *,
    system_unit_directory: Path = Path("/etc/systemd/system"),
) -> list[Finding]:
    unit_directories = (
        system_unit_directory,
        system_unit_directory.parent / "user",
        home / ".config/systemd/user",
        home / ".local/share/systemd/user",
    )
    risky_units: list[tuple[Path, str]] = []
    for unit_directory in unit_directories:
        try:
            unit_files = sorted(
                [
                    *unit_directory.glob("*.service"),
                    *unit_directory.glob("*.service.d/*.conf"),
                ],
            )
        except OSError:
            continue
        for unit_file in unit_files:
            try:
                lines = unit_file.read_text().splitlines()
            except OSError:
                continue
            for line in lines:
                directive = line.strip()
                key, separator, value = directive.partition("=")
                if (
                    separator
                    and key.strip() in SYSTEMD_SERVICE_EXEC_DIRECTIVES
                    and ".local/share/mise/shims/" in value
                ):
                    risky_units.append((unit_file, key.strip()))
                    break
    if not risky_units:
        return [
            Finding(
                "mise.systemd_shims",
                Severity.OK,
                "mise.systemd_shims_clean",
                "No readable custom systemd service directly uses a global Mise shim",
            ),
        ]
    return [
        Finding(
            "mise.systemd_shims",
            Severity.WARN,
            "mise.systemd_shim_dependency",
            f"{unit_file.name} uses a global Mise shim in {directive_name}",
            unit_file,
            (
                "Bind the service to a project config with ~/.local/bin/mise -C "
                "<project> exec -- <tool>, or use a system package; then reload systemd."
            ),
        )
        for unit_file, directive_name in risky_units
    ]


def _mise_runtime_binding_finding(
    generated_function: Path,
    home: Path,
) -> Finding | None:
    if not generated_function.is_file():
        return None
    try:
        content = generated_function.read_text()
    except OSError as error:
        return Finding(
            "runtime.function.mise_binding",
            Severity.WARN,
            "runtime.function.mise_binding_unreadable",
            f"Generated mise Zsh initialization cannot be read: {error}",
            generated_function,
            "Run mise run runtime, then mise run runtime -- --apply.",
        )
    expected = str(canonical_mise_path(home))
    bindings = sorted(set(MISE_BINDING_PATTERN.findall(content)))
    if bindings == [expected]:
        return Finding(
            "runtime.function.mise_binding",
            Severity.OK,
            "runtime.function.mise_binding_ready",
            "Generated mise Zsh initialization is bound to the canonical executable",
            generated_function,
        )
    actual = ", ".join(bindings) if bindings else "no absolute mise executable"
    return Finding(
        "runtime.function.mise_binding",
        Severity.WARN,
        "runtime.function.mise_binding_mismatch",
        f"Generated mise Zsh initialization is not bound only to {expected}: {actual}",
        generated_function,
        "Run mise run runtime, then mise run runtime -- --apply.",
    )
