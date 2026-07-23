"""Inspect host capabilities without installing or changing them."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import re
import shutil
import stat
import subprocess
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from .mise import canonical_mise_executable, canonical_mise_path
from .models import CheckReport, ExecutableFinder, Finding, Severity
from .profiles import HostProfile, resolve_profile
from .render import finding_document, render_findings
from .runtime import (
    COMPLETION_SPECS,
    FUNCTION_SPECS,
    LOCAL_BINARY_SPECS,
    PLUGIN_SPECS,
    WASM_SPECS,
    file_sha256,
    repo_aware_finder,
)


def _check_executable(
    tool: str,
    *,
    required: bool,
    executable_finder: ExecutableFinder,
) -> Finding:
    executable = executable_finder(tool)
    if executable:
        return Finding(
            f"executable.{tool}",
            Severity.OK,
            f"executable.{tool}.ready",
            f"{tool} is available",
            Path(executable),
        )
    severity = Severity.ERROR if required else Severity.WARN
    return Finding(
        f"executable.{tool}",
        severity,
        f"executable.{tool}.missing",
        f"{tool} is not available on PATH",
        action=f"Install {tool} if this host needs that capability.",
    )


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


def _mise_systemd_shim_findings(
    home: Path,
    *,
    system_unit_directory: Path = Path("/etc/systemd/system"),
) -> list[Finding]:
    unit_directories = (system_unit_directory, home / ".config/systemd/user")
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
                    risky_units.append((unit_file, directive))
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
            f"{unit_file.name} directly depends on a global Mise shim: {directive}",
            unit_file,
            (
                "Bind the service to a project config with ~/.local/bin/mise -C "
                "<project> exec -- <tool>, or use a system package; then reload systemd."
            ),
        )
        for unit_file, directive in risky_units
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


def _git_config_defines_identity(config_path: Path) -> bool:
    for key in ("user.name", "user.email"):
        try:
            completed = subprocess.run(
                ["git", "config", "--file", str(config_path), "--get", key],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            return False
        if completed.returncode != 0 or not completed.stdout.strip():
            return False
    return True


def _private_git_identity_ready(private_config: Path, home: Path) -> bool:
    if _git_config_defines_identity(private_config):
        return True
    try:
        completed = subprocess.run(
            [
                "git",
                "config",
                "--file",
                str(private_config),
                "--get-regexp",
                "-z",
                r"^includeif\..*\.path$",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    if completed.returncode != 0:
        return False
    identity_configs: list[Path] = []
    for record in completed.stdout.split("\0"):
        if not record:
            continue
        _, _, raw_path = record.partition("\n")
        if not raw_path:
            return False
        if raw_path.startswith("~/"):
            config_path = home / raw_path[2:]
        else:
            config_path = Path(raw_path)
            if not config_path.is_absolute():
                config_path = private_config.parent / config_path
        identity_configs.append(config_path)
    return bool(identity_configs) and all(
        _git_config_defines_identity(config_path) for config_path in identity_configs
    )


def _private_git_findings(home: Path) -> list[Finding]:
    gitconfig = home / ".gitconfig"
    private_config = home / ".private.gitconfig"
    include_present = False
    if gitconfig.is_file():
        try:
            completed = subprocess.run(
                [
                    "git",
                    "config",
                    "--file",
                    str(gitconfig),
                    "--get-all",
                    "include.path",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            include_present = "~/.private.gitconfig" in completed.stdout.splitlines()
        except OSError:
            include_present = False
    findings = [
        Finding(
            "git.private_include",
            Severity.OK if include_present else Severity.WARN,
            (
                "git.private_include_ready"
                if include_present
                else "git.private_include_missing"
            ),
            (
                "Git includes ~/.private.gitconfig"
                if include_present
                else "Git does not include ~/.private.gitconfig"
            ),
            gitconfig,
            None if include_present else "Add the private include to ~/.gitconfig.",
        ),
    ]
    if not private_config.is_file():
        findings.append(
            Finding(
                "git.private_file",
                Severity.WARN,
                "git.private_file_missing",
                "The private Git configuration is missing",
                private_config,
                "Create ~/.private.gitconfig with this host's Git identity.",
            ),
        )
        return findings
    writable_by_others = private_config.stat().st_mode & (stat.S_IWGRP | stat.S_IWOTH)
    findings.append(
        Finding(
            "git.private_file",
            Severity.WARN if writable_by_others else Severity.OK,
            (
                "git.private_file_permissions"
                if writable_by_others
                else "git.private_file_ready"
            ),
            (
                "The private Git configuration is group or world writable"
                if writable_by_others
                else "The private Git configuration exists with safe permissions"
            ),
            private_config,
            "Remove group and world write permission." if writable_by_others else None,
        ),
    )
    identity_ready = _private_git_identity_ready(private_config, home)
    findings.append(
        Finding(
            "git.private_identity",
            Severity.OK if identity_ready else Severity.WARN,
            (
                "git.private_identity_ready"
                if identity_ready
                else "git.private_identity_missing"
            ),
            (
                "The private Git configuration provides complete Git identities"
                if identity_ready
                else "The private Git configuration does not provide complete Git identities"
            ),
            private_config,
            (
                None
                if identity_ready
                else "Define user.name and user.email directly or in every conditional identity include."
            ),
        ),
    )
    return findings


def _expand_home(value: str, home: Path) -> Path:
    if value == "~":
        return home
    if value.startswith("~/"):
        return home / value[2:]
    return Path(value)


def _configured_skillshare_source(config_path: Path, home: Path) -> Path:
    document = YAML(typ="safe").load(config_path)
    source_value = document["sources"]["skills"]
    if not isinstance(source_value, str):
        raise TypeError("sources.skills must be a string")
    return _expand_home(source_value, home)


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
        source = _configured_skillshare_source(config_path, home)
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
    return [
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


def _skillshare_resource_containers(details: object, home: Path) -> bool:
    if not isinstance(details, list) or not details:
        return False
    containers: list[str] = []
    for detail in details:
        if not isinstance(detail, str):
            return False
        containers.append(detail)
    config_path = home / ".config/skillshare/config.yaml"
    try:
        source = _configured_skillshare_source(config_path, home)
    except OSError, KeyError, TypeError, YAMLError:
        return False
    for detail in containers:
        if detail == "extras":
            continue
        relative = Path(detail)
        if relative.is_absolute() or ".." in relative.parts:
            return False
        container = source / relative
        try:
            if not any(
                (child / "SKILL.md").is_file()
                for child in container.iterdir()
                if child.is_dir()
            ):
                return False
        except OSError:
            return False
    return True


def _skillshare_doctor_finding(executable: Path, home: Path) -> Finding:
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    try:
        completed = subprocess.run(
            [str(executable), "doctor", "--json"],
            cwd=home,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return Finding(
            "skillshare.doctor",
            Severity.WARN,
            "skillshare.doctor_unavailable",
            f"Skillshare doctor could not run: {error}",
            action="Run skillshare doctor --json and resolve reported errors.",
        )
    try:
        document = json.loads(completed.stdout)
        summary = document["summary"]
        warnings = summary["warnings"]
        errors = summary["errors"]
        if not isinstance(warnings, int) or not isinstance(errors, int):
            raise TypeError("summary counts must be integers")
        raw_checks = document.get("checks")
        issues: list[str] = []
        if isinstance(raw_checks, list):
            ignored_warnings = {"git_status", "theme"}
            actionable_warnings = 0
            reported_errors = 0
            for raw_check in raw_checks:
                if not isinstance(raw_check, dict):
                    raise TypeError("checks must contain objects")
                name = raw_check.get("name")
                check_status = raw_check.get("status")
                if not isinstance(name, str) or not isinstance(check_status, str):
                    raise TypeError("check name and status must be strings")
                details = raw_check.get("details")
                raw_message = raw_check.get("message")
                if raw_message is not None and not isinstance(raw_message, str):
                    raise TypeError("check message must be a string")
                known_resource_warning = (
                    name == "skills_validity"
                    and _skillshare_resource_containers(details, home)
                )
                description = name
                if raw_message:
                    description = f"{name}: {' '.join(raw_message.split())}"
                elif isinstance(details, list) and all(
                    isinstance(detail, str) for detail in details
                ):
                    description = f"{name}: {', '.join(details)}"
                if check_status == "error":
                    reported_errors += 1
                    issues.append(description)
                elif (
                    check_status == "warning"
                    and name not in ignored_warnings
                    and not known_resource_warning
                ):
                    actionable_warnings += 1
                    issues.append(description)
            warnings = actionable_warnings
            errors = reported_errors
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        return Finding(
            "skillshare.doctor",
            Severity.WARN,
            "skillshare.doctor_invalid",
            f"Skillshare doctor returned invalid JSON: {error}",
            action="Run skillshare doctor --json and inspect its output.",
        )
    if errors or completed.returncode != 0:
        return Finding(
            "skillshare.doctor",
            Severity.WARN,
            "skillshare.doctor_failed",
            f"Skillshare doctor reports {errors} error(s) and "
            f"{warnings} actionable warning(s)"
            + (f": {'; '.join(issues)}" if issues else ""),
            action="Resolve doctor errors before treating Skillshare as ready.",
        )
    if warnings:
        return Finding(
            "skillshare.doctor",
            Severity.WARN,
            "skillshare.doctor_warnings",
            f"Skillshare doctor reports {warnings} actionable warning(s)"
            + (f": {'; '.join(issues)}" if issues else ""),
            action="Run skillshare doctor --json and resolve the listed warnings.",
        )
    return Finding(
        "skillshare.doctor",
        Severity.OK,
        "skillshare.doctor_ready",
        "Skillshare doctor reports no errors or warnings",
    )


def _file_capability(
    check: str,
    file_path: Path,
    label: str,
    missing_action: str | None = None,
) -> Finding:
    exists = file_path.is_file()
    return Finding(
        check,
        Severity.OK if exists else Severity.WARN,
        f"{check}_{'ready' if exists else 'missing'}",
        f"{label} {'exists' if exists else 'is missing'}",
        file_path,
        None if exists else missing_action,
    )


def _owned_generated_capability(
    check: str,
    file_path: Path,
    label: str,
    *,
    tool_available: bool,
) -> Finding | None:
    action = "Run mise run runtime, then mise run runtime -- --apply."
    if tool_available:
        return _file_capability(check, file_path, label, action)
    if file_path.exists() or file_path.is_symlink():
        return Finding(
            check,
            Severity.WARN,
            f"{check}_stale",
            f"{label} is stale because its generator is not available",
            file_path,
            action,
        )
    return None


def _binary_capability(check: str, file_path: Path, label: str) -> Finding:
    try:
        ready = (
            file_path.is_file()
            and file_path.stat().st_size > 0
            and os.access(file_path, os.X_OK)
        )
    except OSError:
        ready = False
    if ready:
        return Finding(
            check,
            Severity.OK,
            f"{check}_ready",
            f"{label} is present and executable",
            file_path,
        )
    return Finding(
        check,
        Severity.WARN,
        f"{check}_invalid",
        f"{label} is missing, empty, or not executable",
        file_path,
        "Run mise run runtime -- --build, then mise run runtime -- --build --apply.",
    )


def _generated_directory_finding(directory_path: Path, label: str) -> Finding:
    if directory_path.is_symlink():
        return Finding(
            f"shell.{label}",
            Severity.WARN,
            f"shell.{label}_symlinked",
            f"Generated shell {label} directory is a symlink",
            directory_path,
            "Remove the symlink before refreshing repository-owned runtime state.",
        )
    if not directory_path.is_dir():
        return Finding(
            f"shell.{label}",
            Severity.WARN,
            f"shell.{label}_missing",
            f"Generated shell {label} directory is missing",
            directory_path,
            "Run the generator that owns this shell runtime state.",
        )
    populated = any(
        child.name != ".gitkeep"
        for child in directory_path.rglob("*")
        if child.is_file() or child.is_symlink()
    )
    return Finding(
        f"shell.{label}",
        Severity.OK if populated else Severity.WARN,
        f"shell.{label}_{'ready' if populated else 'empty'}",
        f"Generated shell {label} directory "
        f"{'contains runtime data' if populated else 'contains no runtime data'}",
        directory_path,
        None if populated else "Generate this shell runtime state if the host uses it.",
    )


# Deep enough to reach XDG app configs such as ~/.config/Code/User/settings.json
# (mapped by mackup/applications/visual-studio-code.cfg); deeper macOS paths
# under Library are covered by the dedicated area scan below.
HOME_LINK_SCAN_DEPTH = 4
LIBRARY_LINK_SCAN_DEPTH = 4
LIBRARY_LINK_SCAN_AREAS = ("Library/Application Support", "Library/Preferences")


def _collect_symlinks(
    root: Path, depth: int, *, skip_names: frozenset[str]
) -> list[Path]:
    links: list[Path] = []
    pending: list[tuple[Path, int]] = [(root, depth)]
    while pending:
        directory, remaining = pending.pop()
        try:
            entries = list(os.scandir(directory))
        except OSError:
            continue
        for entry in entries:
            entry_path = Path(entry.path)
            try:
                if entry.is_symlink():
                    links.append(entry_path)
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if directory == root and entry.name in skip_names:
                        continue
                    if remaining > 1:
                        pending.append((entry_path, remaining - 1))
            except OSError:
                continue
    return links


def _dangling_repo_link_findings(repo_root: Path, home: Path) -> list[Finding]:
    """Report $HOME symlinks into the repository whose targets are gone.

    Restore and adopt only observe currently mapped applications, so links
    left behind by removed mappings or renamed repository roots are invisible
    to diff; this is the one place that still looks for them.
    """
    repository = repo_root.resolve()
    links = _collect_symlinks(
        home, HOME_LINK_SCAN_DEPTH, skip_names=frozenset({"Library"})
    )
    for area in LIBRARY_LINK_SCAN_AREAS:
        area_root = home / area
        if area_root.is_dir():
            links.extend(
                _collect_symlinks(
                    area_root, LIBRARY_LINK_SCAN_DEPTH, skip_names=frozenset()
                )
            )
    findings = []
    for link in sorted(links):
        try:
            raw_target = os.readlink(link)
        except OSError:
            continue
        target = Path(raw_target)
        if not target.is_absolute():
            target = link.parent / target
        target = Path(os.path.normpath(target))
        if not target.is_relative_to(repository) or link.exists():
            continue
        findings.append(
            Finding(
                "home.repo_links",
                Severity.WARN,
                "home.dangling_repo_link",
                f"Symlink into the repository is dangling (-> {raw_target})",
                link,
                "Remove the link, or restore its application with "
                "mise run restore -- <application> --apply.",
            ),
        )
    if not findings:
        findings.append(
            Finding(
                "home.repo_links",
                Severity.OK,
                "home.repo_links_clean",
                "No dangling repository symlinks under $HOME",
            ),
        )
    return findings


def _bash_integration_finding(repo_root: Path, home: Path) -> Finding:
    bashrc = home / ".bashrc"
    module_path = repo_root.resolve() / "modules/bash/init.bash"
    try:
        configured = bashrc.is_file() and str(module_path) in bashrc.read_text()
    except OSError:
        configured = False
    return Finding(
        "shell.bash",
        Severity.OK if configured else Severity.WARN,
        "shell.bash_ready" if configured else "shell.bash_missing",
        "Bash loads the Linux Lite module"
        if configured
        else "Bash does not load the Linux Lite module",
        bashrc,
        None
        if configured
        else (
            "Preview with mise run setup -- --profile linux-lite, then apply with "
            "mise run setup -- --profile linux-lite --apply."
        ),
    )


def _legacy_repo_path_finding(repo_root: Path) -> Finding:
    legacy_directories = (
        (repo_root / "modules/bin").resolve(),
        (repo_root / "generated/bin").resolve(),
    )
    active_directories = {
        Path(entry).expanduser().resolve()
        for entry in os.environ.get("PATH", "").split(os.pathsep)
        if entry
    }
    exposed = next(
        (
            directory
            for directory in legacy_directories
            if directory in active_directories
        ),
        None,
    )
    return Finding(
        "shell.repo_commands",
        Severity.WARN if exposed else Severity.OK,
        ("shell.repo_commands_exposed" if exposed else "shell.repo_commands_isolated"),
        (
            "Linux PATH exposes repository commands from a legacy configuration"
            if exposed
            else "Linux PATH does not expose repository command directories"
        ),
        exposed,
        (
            "Remove dotfiles modules/bin and generated/bin from Bash or global mise PATH configuration."
            if exposed
            else None
        ),
    )


SESSION_HEALTH_SNAPSHOT_MAX_AGE = dt.timedelta(minutes=30)
SESSION_HEALTH_FAILURE_STREAK = 3


def _session_health_findings(
    executable_finder: ExecutableFinder,
    *,
    now: dt.datetime | None = None,
) -> list[Finding]:
    executable = executable_finder("macos-session-health")
    if executable is None:
        return [
            Finding(
                "session_health.agent",
                Severity.WARN,
                "session_health.missing",
                "macos-session-health is not installed",
                action=(
                    "Run modules/macos-session-health/macos-session-health install."
                ),
            ),
        ]
    try:
        completed = subprocess.run(
            [str(executable), "status", "--format", "json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return [
            Finding(
                "session_health.agent",
                Severity.WARN,
                "session_health.status_unavailable",
                f"macos-session-health status could not run: {error}",
                action="Run macos-session-health status and resolve the failure.",
            ),
        ]
    if completed.returncode != 0 and not completed.stdout.strip():
        detail = completed.stderr.strip() or f"exit {completed.returncode}"
        return [
            Finding(
                "session_health.agent",
                Severity.WARN,
                "session_health.status_unavailable",
                f"macos-session-health status failed: {detail}",
                action="Run macos-session-health status and resolve the failure.",
            ),
        ]
    try:
        records = json.loads(completed.stdout)
        record = records[0]
        installed = bool(record["installed"])
        loaded = bool(record["loaded"])
        last_snapshot_at = str(record.get("last_snapshot_at") or "")
        failures = int(record.get("consecutive_delivery_failures") or 0)
        configured = bool(record.get("notification_configured"))
    except (json.JSONDecodeError, LookupError, TypeError, ValueError) as error:
        return [
            Finding(
                "session_health.agent",
                Severity.WARN,
                "session_health.status_invalid",
                f"macos-session-health status returned an invalid report: {error}",
                action="Run macos-session-health status --format json.",
            ),
        ]

    agent_ready = installed and loaded
    if completed.returncode != 0 and agent_ready:
        return [
            Finding(
                "session_health.agent",
                Severity.WARN,
                "session_health.status_unavailable",
                f"macos-session-health status contradicted exit {completed.returncode}",
                action="Run macos-session-health status and resolve the failure.",
            )
        ]
    findings = [
        Finding(
            "session_health.agent",
            Severity.OK if agent_ready else Severity.WARN,
            "session_health.agent_ready"
            if agent_ready
            else "session_health.agent_down",
            "session-health launch agent is installed and loaded"
            if agent_ready
            else "session-health launch agent is not running",
            action=(
                None
                if agent_ready
                else "Run modules/macos-session-health/macos-session-health install."
            ),
        ),
    ]

    snapshot_fresh = False
    if last_snapshot_at:
        try:
            last = dt.datetime.fromisoformat(last_snapshot_at.replace("Z", "+00:00"))
            current = now or dt.datetime.now(dt.timezone.utc)
            snapshot_fresh = current - last <= SESSION_HEALTH_SNAPSHOT_MAX_AGE
        except ValueError, TypeError:
            snapshot_fresh = False
    findings.append(
        Finding(
            "session_health.snapshot",
            Severity.OK if snapshot_fresh else Severity.WARN,
            "session_health.snapshot_recent"
            if snapshot_fresh
            else "session_health.snapshot_stale",
            f"last snapshot: {last_snapshot_at}"
            if last_snapshot_at
            else "no snapshot has been recorded",
            action=(
                None
                if snapshot_fresh
                else "Inspect launchd logs; the agent may have silently stopped."
            ),
        ),
    )

    if not configured:
        findings.append(
            Finding(
                "session_health.notifications",
                Severity.WARN,
                "session_health.notifications_unconfigured",
                "notification delivery is not configured",
                action="Provide BRRR_SECRET via ~/.config/brrr/env.",
            ),
        )
    elif failures >= SESSION_HEALTH_FAILURE_STREAK:
        findings.append(
            Finding(
                "session_health.notifications",
                Severity.WARN,
                "session_health.notifications_failing",
                f"last {failures} notification deliveries failed",
                action="Run macos-session-health notify-test --dry-run.",
            ),
        )
    else:
        findings.append(
            Finding(
                "session_health.notifications",
                Severity.OK,
                "session_health.notifications_ready",
                "notification delivery is configured and recently healthy",
            ),
        )
    return findings


def _module_source_constant(source: Path, name: str) -> str | None:
    try:
        for line in source.read_text().splitlines():
            if line.startswith(f'{name}="') and line.rstrip().endswith('"'):
                return line.rstrip()[len(name) + 2 : -1]
    except OSError:
        return None
    return None


def _bag_mode_findings(
    executable_finder: ExecutableFinder,
    repo_root: Path,
) -> list[Finding]:
    executable = executable_finder("bag-mode")
    if executable is None:
        return [
            Finding(
                "bag_mode.lifecycle",
                Severity.WARN,
                "bag_mode.missing",
                "bag-mode is not installed",
                action="Run modules/bag-mode/bag-mode install if this host needs lid-closed sessions.",
            ),
        ]
    try:
        completed = subprocess.run(
            [str(executable), "status", "--json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"status exited {completed.returncode}")
        record = json.loads(completed.stdout)
        enabled = bool(record["enabled"])
        phase = str(record["phase"])
        recovery_required = bool(record["recovery_required"])
        brightness_pending = bool(record["brightness_pending"])
    except (
        OSError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        LookupError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        return [
            Finding(
                "bag_mode.lifecycle",
                Severity.WARN,
                "bag_mode.status_unavailable",
                f"bag-mode status could not be read: {error}",
                action="Run bag-mode status --json and resolve the failure.",
            ),
        ]

    if recovery_required or brightness_pending:
        lifecycle = Finding(
            "bag_mode.lifecycle",
            Severity.WARN,
            "bag_mode.recovery_pending",
            "bag-mode has unrestored captured settings",
            action="Run bag-mode recover.",
        )
    elif enabled and phase != "running":
        lifecycle = Finding(
            "bag_mode.lifecycle",
            Severity.WARN,
            "bag_mode.stalled",
            f"bag-mode is enabled but its controller phase is {phase}",
            action="Inspect bag-mode logs, then run bag-mode status.",
        )
    elif enabled:
        lifecycle = Finding(
            "bag_mode.lifecycle",
            Severity.OK,
            "bag_mode.running",
            "bag-mode is enabled and its controller is running",
        )
    else:
        lifecycle = Finding(
            "bag_mode.lifecycle",
            Severity.OK,
            "bag_mode.stopped",
            "bag-mode is stopped; the Mac sleeps normally when the lid closes",
        )
    findings = [lifecycle]

    repo_version = _module_source_constant(
        repo_root / "modules/bag-mode/bag-mode",
        "VERSION",
    )
    if repo_version:
        version_error = ""
        try:
            completed = subprocess.run(
                [str(executable), "version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            reported = completed.stdout.strip()
            if completed.returncode != 0:
                detail = completed.stderr.strip() or completed.stdout.strip()
                version_error = f"command exited {completed.returncode}"
                if detail:
                    version_error += f": {detail}"
                reported = ""
        except (OSError, subprocess.TimeoutExpired) as error:
            reported = ""
            version_error = str(error)
        installed_version = reported.removeprefix("bag-mode ").strip()
        drifted = installed_version != repo_version
        findings.append(
            Finding(
                "bag_mode.version",
                Severity.WARN if drifted or version_error else Severity.OK,
                (
                    "bag_mode.version_unavailable"
                    if version_error
                    else (
                        "bag_mode.version_drift"
                        if drifted
                        else "bag_mode.version_current"
                    )
                ),
                (
                    f"could not read installed bag-mode version: {version_error}"
                    if version_error
                    else (
                        f"installed bag-mode {installed_version or 'unknown'} differs "
                        f"from repository version {repo_version}"
                        if drifted
                        else f"installed bag-mode matches repository version {repo_version}"
                    )
                ),
                action=(
                    "Run bag-mode version, then inspect or upgrade the installation."
                    if version_error
                    else ("Run modules/bag-mode/bag-mode upgrade." if drifted else None)
                ),
            ),
        )
    return findings


def _limit_satisfied(actual: str, expected: str) -> bool:
    """A launchd limit satisfies its target when it meets or exceeds it.

    launchd reports an unbounded hard limit as the word "unlimited" even after
    a numeric limit was applied, so that value always satisfies the target.
    """
    if actual == expected or actual == "unlimited":
        return True
    try:
        return int(actual) >= int(expected)
    except ValueError:
        return False


def _maxfiles_findings(
    executable_finder: ExecutableFinder,
    repo_root: Path,
) -> list[Finding]:
    executable = executable_finder("macos-maxfiles")
    if executable is None:
        return [
            Finding(
                "maxfiles.agent",
                Severity.WARN,
                "maxfiles.missing",
                "macos-maxfiles is not installed",
                action="Run modules/macos-maxfiles/macos-maxfiles install.",
            ),
        ]
    try:
        completed = subprocess.run(
            [str(executable), "status", "--json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        record = json.loads(completed.stdout)
        installed = bool(record["installed"])
        loaded = bool(record["loaded"])
        soft_limit = str(record.get("soft_limit") or "")
        hard_limit = str(record.get("hard_limit") or "")
    except (
        OSError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        LookupError,
        TypeError,
        ValueError,
    ) as error:
        return [
            Finding(
                "maxfiles.agent",
                Severity.WARN,
                "maxfiles.status_unavailable",
                f"macos-maxfiles status could not be read: {error}",
                action="Run macos-maxfiles status --json and resolve the failure.",
            ),
        ]

    agent_ready = installed and loaded
    if completed.returncode != 0 and agent_ready:
        return [
            Finding(
                "maxfiles.agent",
                Severity.WARN,
                "maxfiles.status_unavailable",
                f"macos-maxfiles status contradicted exit {completed.returncode}",
                action="Run macos-maxfiles status --json and resolve the failure.",
            )
        ]
    findings = [
        Finding(
            "maxfiles.agent",
            Severity.OK if agent_ready else Severity.WARN,
            "maxfiles.agent_ready" if agent_ready else "maxfiles.agent_down",
            "maxfiles LaunchDaemon is installed and loaded"
            if agent_ready
            else "maxfiles LaunchDaemon is not loaded",
            action=(
                None
                if agent_ready
                else "Run modules/macos-maxfiles/macos-maxfiles install."
            ),
        ),
    ]
    source = repo_root / "modules/macos-maxfiles/macos-maxfiles"
    expected_soft = _module_source_constant(source, "SOFT_LIMIT")
    expected_hard = _module_source_constant(source, "HARD_LIMIT")
    if agent_ready and expected_soft and expected_hard:
        matches = _limit_satisfied(soft_limit, expected_soft) and _limit_satisfied(
            hard_limit, expected_hard
        )
        findings.append(
            Finding(
                "maxfiles.limits",
                Severity.OK if matches else Severity.WARN,
                "maxfiles.limits_effective" if matches else "maxfiles.limits_drift",
                (
                    f"effective maxfiles limits {soft_limit}/{hard_limit} satisfy "
                    f"the configured {expected_soft}/{expected_hard}"
                    if matches
                    else (
                        f"effective maxfiles limits {soft_limit or 'unknown'}/"
                        f"{hard_limit or 'unknown'} fall below the configured "
                        f"{expected_soft}/{expected_hard}"
                    )
                ),
                action=(
                    None
                    if matches
                    else "Run modules/macos-maxfiles/macos-maxfiles install to reapply the limit."
                ),
            ),
        )
    return findings


def inspect_host(
    repo_root: Path,
    home: Path,
    *,
    executable_finder: ExecutableFinder = shutil.which,
    system_name: str | None = None,
    profile: str | HostProfile = HostProfile.AUTO,
) -> CheckReport:
    """Return explicit required and optional capabilities for this host."""
    active_system = system_name or platform.system()
    active_profile = resolve_profile(profile, active_system)
    required_commands = (
        ("git", "mise")
        if active_profile is HostProfile.LINUX_LITE
        else ("git", "python", "uv", "mise")
    )
    findings = [
        _check_executable(
            command,
            required=True,
            executable_finder=executable_finder,
        )
        for command in required_commands
    ]
    findings.extend(
        _mise_installation_findings(
            home,
            executable_finder=executable_finder,
            scan_host_path=executable_finder is shutil.which,
        ),
    )
    if mise_shims := _mise_shim_finding(home):
        findings.append(mise_shims)
    if active_system == "Linux":
        findings.extend(_mise_systemd_shim_findings(home))
    findings.extend(_private_git_findings(home))
    skillshare_finding = _check_executable(
        "skillshare",
        required=False,
        executable_finder=executable_finder,
    )
    findings.append(skillshare_finding)
    findings.extend(_skillshare_findings(home))
    if skillshare_finding.path and (home / ".config/skillshare/config.yaml").is_file():
        findings.append(_skillshare_doctor_finding(skillshare_finding.path, home))
    findings.extend(_dangling_repo_link_findings(repo_root, home))
    if active_profile is HostProfile.LINUX_LITE:
        findings.append(_bash_integration_finding(repo_root, home))
        findings.append(_legacy_repo_path_finding(repo_root))
        return CheckReport(
            schema_version=1,
            findings=tuple(findings),
            profile=active_profile,
        )
    if active_system == "Darwin":
        findings.extend(_session_health_findings(executable_finder))
        findings.extend(_bag_mode_findings(executable_finder, repo_root))
        findings.extend(_maxfiles_findings(executable_finder, repo_root))
    findings.append(
        _check_executable(
            "tv",
            required=False,
            executable_finder=executable_finder,
        ),
    )
    findings.append(
        _file_capability(
            "television.config",
            home / ".config/television/config.toml",
            "Television configuration",
        ),
    )
    for directory in ("plugins", "completions", "functions"):
        findings.append(
            _generated_directory_finding(
                repo_root / "generated" / directory, directory
            ),
        )
    mise_binding = _mise_runtime_binding_finding(
        repo_root / "generated/functions/_mise.zsh",
        home,
    )
    if mise_binding:
        findings.append(mise_binding)
    owned_tool_finder = repo_aware_finder(repo_root, executable_finder)
    for tool, _command, filename in FUNCTION_SPECS:
        tool_available = (
            canonical_mise_executable(home) is not None
            if tool == "mise"
            else owned_tool_finder(tool) is not None
        )
        finding = _owned_generated_capability(
            f"runtime.function.{tool}",
            repo_root / "generated/functions" / filename,
            f"Generated {tool} Zsh initialization",
            tool_available=tool_available,
        )
        if finding:
            findings.append(finding)
    for name, tool, _command, filename, _environment in COMPLETION_SPECS:
        finding = _owned_generated_capability(
            f"runtime.completion.{name}",
            repo_root / "generated/completions" / filename,
            f"Generated {name} completion",
            tool_available=owned_tool_finder(tool) is not None,
        )
        if finding:
            findings.append(finding)
    for name, _source, entrypoint in PLUGIN_SPECS:
        findings.append(
            _file_capability(
                f"runtime.plugin.{name}",
                repo_root / "generated/plugins" / name / entrypoint,
                f"Zsh plugin {name}",
                "Run mise run runtime, then mise run runtime -- --apply.",
            ),
        )
    generated_plugins = repo_root / "generated/plugins"
    owned_plugins = {name for name, _source, _entrypoint in PLUGIN_SPECS} | {
        f"{name}.wasm" for name, _source, _sha256 in WASM_SPECS
    }
    if generated_plugins.is_dir():
        for plugin_path in sorted(generated_plugins.iterdir()):
            if plugin_path.name in owned_plugins or plugin_path.name == ".gitkeep":
                continue
            findings.append(
                Finding(
                    f"runtime.plugin.{plugin_path.name}",
                    Severity.WARN,
                    f"runtime.plugin.{plugin_path.name}_unowned",
                    f"Generated plugin {plugin_path.name} has no repository owner",
                    plugin_path,
                    "Remove it explicitly if obsolete, or define its runtime owner.",
                ),
            )
    for name, _source, sha256 in WASM_SPECS:
        plugin_name = f"{name}.wasm"
        plugin_path = generated_plugins / plugin_name
        actual_sha256 = file_sha256(plugin_path)
        if actual_sha256 == sha256:
            findings.append(
                Finding(
                    f"zellij.{plugin_name}",
                    Severity.OK,
                    f"zellij.{plugin_name}_ready",
                    f"Zellij plugin {plugin_name} matches its pinned checksum",
                    plugin_path,
                ),
            )
        else:
            code = "missing" if actual_sha256 is None else "checksum_mismatch"
            message = (
                f"Zellij plugin {plugin_name} is missing"
                if actual_sha256 is None
                else f"Zellij plugin {plugin_name} does not match its pinned checksum"
            )
            findings.append(
                Finding(
                    f"zellij.{plugin_name}",
                    Severity.WARN,
                    f"zellij.{plugin_name}_{code}",
                    message,
                    plugin_path,
                    "Run mise run runtime, then mise run runtime -- --apply.",
                ),
            )
    generated_bin = repo_root / "generated/bin"
    owned_binaries = {name for name, _source, _command, _artifact in LOCAL_BINARY_SPECS}
    for binary_name in sorted(owned_binaries):
        findings.append(
            _binary_capability(
                f"runtime.binary.{binary_name}",
                generated_bin / binary_name,
                f"Generated binary {binary_name}",
            ),
        )
    if generated_bin.is_dir():
        for file_path in sorted(generated_bin.iterdir()):
            if (
                file_path.name in owned_binaries
                or file_path.name == ".gitkeep"
                or not (file_path.is_file() or file_path.is_symlink())
            ):
                continue
            findings.append(
                Finding(
                    f"runtime.binary.{file_path.name}",
                    Severity.WARN,
                    f"runtime.binary.{file_path.name}_unowned",
                    f"Generated binary {file_path.name} has no repository owner",
                    file_path,
                    "Define its build or install owner before treating it as reproducible.",
                ),
            )
    if active_system == "Darwin":
        findings.append(
            _check_executable(
                "launchctl",
                required=False,
                executable_finder=executable_finder,
            ),
        )
    else:
        findings.append(
            Finding(
                "macos.launchctl",
                None,
                "macos.launchctl_skipped",
                f"launchctl is not applicable on {active_system}",
            ),
        )
    return CheckReport(
        schema_version=1,
        findings=tuple(findings),
        profile=active_profile,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect this host's capabilities.")
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit the report as JSON on stdout",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat warn findings as failures",
    )
    parser.add_argument(
        "--profile",
        choices=[profile.value for profile in HostProfile],
        default=HostProfile.AUTO.value,
        help="host profile that selects which capabilities to inspect",
    )
    parser.add_argument(
        "--include-ok",
        action="store_true",
        help="also list ok findings (default: warn, error, and skipped only)",
    )
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    report = inspect_host(repo_root, Path.home(), profile=args.profile)
    if args.as_json:
        document = finding_document(
            report,
            operation="check",
            strict=args.strict,
        )
        document["profile"] = report.profile.value
        print(
            json.dumps(
                document,
                indent=2,
                sort_keys=True,
            ),
        )
    else:
        print(f"Profile: {report.profile.value}")
        render_findings(report, include_ok=args.include_ok)
    return 0 if report.is_ok(strict=args.strict) else 1


if __name__ == "__main__":
    raise SystemExit(main())
