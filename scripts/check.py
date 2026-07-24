"""Inspect host capabilities without installing or changing them."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import stat
import subprocess
from pathlib import Path

from .check_macos import (
    _bag_mode_findings,
    _maxfiles_findings,
    _session_health_findings,
)
from .check_mise import (
    _mise_installation_findings,
    _mise_runtime_binding_finding,
    _mise_shim_finding,
    _mise_systemd_shim_findings,
)
from .check_skillshare import _skillshare_doctor_finding, _skillshare_findings
from .mise import canonical_mise_executable
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
    """Report $HOME symlinks into the repository whose targets are gone."""
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
