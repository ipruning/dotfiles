"""Inspect repository invariants without changing tracked files."""

from __future__ import annotations

import argparse
import configparser
import json
import platform
import re
import subprocess
from pathlib import Path

from ruamel.yaml import YAML

from .models import Finding, LintReport, Severity
from .render import finding_document, render_findings

PATH_RE = re.compile(
    r"(?P<path>"
    r"/Applications/[^\"'<>),;\]]+?\.app(?:/(?:\\ |[^\s\"'<>),;:\]\}])*)?"
    r"|/(?:Users|home)/[A-Za-z0-9._-]+(?:/(?:\\ |[^\s\"'<>),;:\]\}])*)?"
    r"|/root(?:/(?:\\ |[^\s\"'<>),;:\]\}])*)?"
    r"|/opt/homebrew(?:/(?:\\ |[^\s\"'<>),;:\]\}])*)?"
    r"|/usr/local(?:/(?:\\ |[^\s\"'<>),;:\]\}])*)?"
    r"|(?:~|\$HOME|\$\{HOME\})/(?:\\ |[^\s\"'<>),;:\]\}])+"
    r")",
)
URL_RE = re.compile(r"https?://\S+")

SKIP_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "tests",
}
SKIP_SUFFIXES = {
    ".md",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".wasm",
    ".pyc",
}
SKIP_PREFIXES = ("generated/",)
FULL_HOME_REQUIRED_FILES = {
    "reference/.config/zellij/config.kdl": (
        "zellij-sessionizer paths do not expand home variables"
    ),
}
OPTIONAL_REFERENCE_SECTION = "dotfiles_optional_reference_files"
OPTIONAL_PATHS = {
    (
        "reference/.config/skillshare/config.yaml",
        "~/Developer/ipruning/skills",
    ),
    (
        "reference/.config/skillshare/config.yaml",
        "~/Developer/ipruning/skills/extras",
    ),
    ("reference/.zshenv", "/usr/local/sbin"),
    ("reference/.zshrc", "/usr/local/Homebrew"),
    ("reference/.zshrc", "/usr/local/Cellar"),
    ("reference/.zshrc", "/usr/local/share/zsh/site-functions"),
    ("reference/.zshrc", "/usr/local/share/info"),
    ("modules/bag-mode/bag-mode", "/opt/homebrew/bin/brightness"),
    (
        "modules/macos-session-health/macos-session-health",
        "/Applications/Codex.app/Contents/MacOS/Codex",
    ),
    (
        "modules/macos-session-health/macos-session-health",
        "/Applications/{app_name}.app/Contents/Resources/codex",
    ),
    (
        "modules/macos-session-health/macos-session-health",
        "/Applications/{app_name}.app/Contents/Resources/cua_node/bin/node_repl",
    ),
    ("modules/zsh/env.zsh", "/usr/local/bin/op"),
}


def _finding(
    severity: Severity,
    code: str,
    message: str,
    source: Path,
    *,
    line: int | None = None,
    value: str | None = None,
) -> Finding:
    location = f"{source}:{line}" if line is not None else str(source)
    detail = f"{location}: {message}"
    if value:
        detail = f"{detail} ({value})"
    return Finding("repository", severity, code, detail, source)


def _is_binary(file_path: Path) -> bool:
    try:
        return b"\0" in file_path.read_bytes()[:4096]
    except OSError:
        return True


def _iter_text_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for file_path in repo_root.rglob("*"):
        relative = file_path.relative_to(repo_root)
        relative_text = relative.as_posix()
        if any(part in SKIP_PARTS for part in relative.parts):
            continue
        if relative_text == "scripts/lint.py":
            continue
        if relative_text.startswith(SKIP_PREFIXES):
            continue
        if file_path.is_symlink() or not file_path.is_file():
            continue
        if file_path.suffix.lower() in SKIP_SUFFIXES or _is_binary(file_path):
            continue
        files.append(file_path)
    return sorted(files)


def _expand_homeish(raw: str, home: Path) -> Path | None:
    if raw.startswith("~/"):
        return home / raw[2:]
    if raw.startswith("$HOME/"):
        return home / raw[6:]
    if raw.startswith("${HOME}/"):
        return home / raw[8:]
    if raw.startswith(("/Users/", "/home/", "/root/")):
        return Path(raw)
    return None


def _path_exists(raw: str, home: Path) -> bool:
    normalized = raw.replace("\\ ", " ")
    if normalized.startswith("/Applications/") and ".app/" in normalized:
        normalized = normalized[: normalized.index(".app/") + len(".app")]
    expanded = _expand_homeish(normalized, home)
    return (expanded or Path(normalized)).exists()


def _classify_path(
    repo_root: Path,
    home: Path,
    relative: str,
    source: Path,
    line: int,
    raw: str,
    system_name: str,
) -> Finding:
    if system_name == "Linux" and (
        raw.startswith(("/Applications/", "/opt/homebrew"))
        or (raw.startswith("/Users/") and relative.startswith("reference/"))
    ):
        return _finding(
            Severity.SKIPPED,
            "path.platform_skipped",
            "macOS-only path is not evaluated on Linux",
            source,
            line=line,
            value=raw,
        )
    if (relative, raw) in OPTIONAL_PATHS:
        return _finding(
            Severity.OK,
            "path.optional_compatibility",
            "explicitly guarded compatibility path",
            source,
            line=line,
            value=raw,
        )
    if raw.startswith(("/Users/", "/home/", "/root/")):
        if relative in FULL_HOME_REQUIRED_FILES:
            matches_home = raw == str(home) or raw.startswith(f"{home}/")
            return _finding(
                Severity.OK
                if matches_home and _path_exists(raw, home)
                else Severity.WARN,
                "path.full_home_required",
                FULL_HOME_REQUIRED_FILES[relative],
                source,
                line=line,
                value=raw,
            )
        if not (raw == str(home) or raw.startswith(f"{home}/")):
            return _finding(
                Severity.ERROR,
                "path.absolute_home",
                f"absolute user path does not match HOME={home}",
                source,
                line=line,
                value=raw,
            )
        return _finding(
            Severity.ERROR,
            "path.absolute_home",
            "replace the absolute user path with a supported home-relative form",
            source,
            line=line,
            value=raw,
        )
    if raw.startswith(("~/dotfiles", "$HOME/dotfiles", "${HOME}/dotfiles")):
        expected = (home / "dotfiles").resolve()
        severity = Severity.OK if repo_root.resolve() == expected else Severity.WARN
        return _finding(
            severity,
            "path.dotfiles_root",
            f"path assumes repository location {expected}",
            source,
            line=line,
            value=raw,
        )
    if raw.startswith(
        (
            "~/Developer/",
            "$HOME/Developer/",
            "${HOME}/Developer/",
            "~/work/",
            "$HOME/work/",
            "${HOME}/work/",
        ),
    ):
        return _finding(
            Severity.OK if _path_exists(raw, home) else Severity.WARN,
            "path.personal_workspace",
            "home-relative path binds this config to a personal workspace",
            source,
            line=line,
            value=raw,
        )
    if raw.startswith(("/opt/homebrew", "/usr/local")):
        return _finding(
            (
                Severity.OK
                if system_name == "Linux" or _path_exists(raw, home)
                else Severity.WARN
            ),
            "path.toolchain",
            "machine or architecture-specific toolchain path",
            source,
            line=line,
            value=raw,
        )
    if raw.startswith("/Applications/"):
        if "\\" in raw or "{" in raw or raw.endswith("$"):
            return _finding(
                Severity.OK,
                "path.application_pattern",
                "application path pattern used for process matching",
                source,
                line=line,
                value=raw,
            )
        return _finding(
            Severity.OK if _path_exists(raw, home) else Severity.WARN,
            "path.application",
            "macOS application path",
            source,
            line=line,
            value=raw,
        )
    return _finding(
        Severity.OK,
        "path.home_relative",
        "home-relative path",
        source,
        line=line,
        value=raw,
    )


def _path_findings(
    repo_root: Path,
    home: Path,
    system_name: str,
) -> list[Finding]:
    findings: list[Finding] = []
    for file_path in _iter_text_files(repo_root):
        relative = file_path.relative_to(repo_root).as_posix()
        try:
            lines = file_path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            url_spans = [url.span() for url in URL_RE.finditer(line)]
            for match in PATH_RE.finditer(line):
                raw = match.group("path").rstrip(".,:")
                if any(begin <= match.start("path") < end for begin, end in url_spans):
                    continue
                findings.append(
                    _classify_path(
                        repo_root,
                        home,
                        relative,
                        file_path,
                        line_number,
                        raw,
                        system_name,
                    ),
                )
    return findings


class _CaseConfigParser(configparser.ConfigParser):
    def optionxform(self, optionstr: str) -> str:
        return optionstr


def _config() -> configparser.ConfigParser:
    return _CaseConfigParser(allow_no_value=True)


def _mackup_findings(repo_root: Path) -> list[Finding]:
    config_path = repo_root / "mackup/mackup.cfg"
    if not config_path.is_file():
        return [
            _finding(
                Severity.ERROR,
                "mackup.config_missing",
                "Mackup config is missing",
                config_path,
            ),
        ]
    config = _config()
    config.read(config_path)
    applications = (
        list(config.options("applications_to_sync"))
        if config.has_section("applications_to_sync")
        else []
    )
    tracked_paths = set(_tracked_paths(repo_root))

    def reference_exists(candidate: Path) -> bool:
        if not tracked_paths:
            return candidate.exists()
        return any(
            tracked == candidate or candidate in tracked.parents
            for tracked in tracked_paths
        )

    findings: list[Finding] = []
    applications_dir = repo_root / "mackup/applications"
    if applications_dir.is_dir():
        selected = set(applications)
        for mapping_path in sorted(applications_dir.glob("*.cfg")):
            if mapping_path.stem not in selected:
                findings.append(
                    _finding(
                        Severity.ERROR,
                        "mackup.mapping_unused",
                        "mapping is not selected in applications_to_sync;"
                        " adopt the application or delete the mapping",
                        mapping_path,
                    ),
                )
    for application in applications:
        app_path = repo_root / "mackup/applications" / f"{application}.cfg"
        if not app_path.is_file():
            findings.append(
                _finding(
                    Severity.ERROR,
                    "mackup.application_missing",
                    f"selected application {application} has no mapping",
                    app_path,
                ),
            )
            continue
        app_config = _config()
        app_config.read(app_path)
        candidates: list[Path] = []
        if app_config.has_section("configuration_files"):
            candidates.extend(
                repo_root / "reference" / item
                for item in app_config.options("configuration_files")
            )
        if app_config.has_section("xdg_configuration_files"):
            candidates.extend(
                repo_root / "reference/.config" / item
                for item in app_config.options("xdg_configuration_files")
            )
        optional_candidates = (
            {
                repo_root / "reference" / item
                for item in app_config.options(OPTIONAL_REFERENCE_SECTION)
            }
            if app_config.has_section(OPTIONAL_REFERENCE_SECTION)
            else set()
        )
        candidate_set = set(candidates)
        for candidate in sorted(optional_candidates - candidate_set):
            findings.append(
                _finding(
                    Severity.ERROR,
                    "mackup.optional_reference_unmapped",
                    f"selected application {application} marks an unmapped candidate optional",
                    candidate,
                ),
            )
        missing_candidates = [
            candidate for candidate in candidates if not reference_exists(candidate)
        ]
        for candidate in (
            candidate
            for candidate in missing_candidates
            if candidate not in optional_candidates
        ):
            findings.append(
                _finding(
                    Severity.ERROR,
                    "mackup.reference_missing",
                    f"selected application {application} maps missing reference data",
                    candidate,
                ),
            )
        if candidates and len(missing_candidates) == len(candidates):
            findings.append(
                _finding(
                    Severity.ERROR,
                    "mackup.application_empty",
                    f"selected application {application} has no reference data",
                    app_path,
                ),
            )
    if not findings:
        findings.append(
            _finding(
                Severity.OK,
                "mackup.mapping_ready",
                f"{len(applications)} selected applications have reference data",
                config_path,
            ),
        )
    return findings


def _tracked_paths(repo_root: Path) -> list[Path]:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        return []
    return [repo_root / item.decode() for item in completed.stdout.split(b"\0") if item]


def _tracked_file_findings(repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for file_path in _tracked_paths(repo_root):
        if not file_path.exists():
            continue
        relative = file_path.relative_to(repo_root).as_posix()
        basename = file_path.name.lower()
        if (
            "private" in basename
            and ".tpl." not in basename
            and ".template." not in basename
        ):
            findings.append(
                _finding(
                    Severity.ERROR,
                    "repository.private_tracked",
                    "materialized private file must not be tracked",
                    file_path,
                ),
            )
        if relative.startswith("generated/"):
            findings.append(
                _finding(
                    Severity.ERROR,
                    "repository.generated_tracked",
                    "generated file has no repository regeneration task",
                    file_path,
                ),
            )
    return findings


LEGACY_REFERENCES = (
    "~/dotfiles/home/",
    "$HOME/dotfiles/home/",
    "${HOME}/dotfiles/home/",
    "modules/mackup/",
    "modules/bin/dotfiles-backup",
    "modules/bin/dotfiles-doctor",
    "modules/bin/dotfiles-init",
    "modules/bin/dotfiles-restore",
    "modules/bin/dotfiles-sync",
    "modules/bin/dotfiles-up",
    "modules/bin/dotfiles-zsh-profile",
    "modules/bin/ss",
    "modules/bin/_lib/core.sh",
    "modules/bin/_lib/load.sh",
    "modules/bin/_lib/log.sh",
    "mise run backup",
    "mise run doctor",
    "mise run init",
    "mise run sync",
    "mise run up",
)


def _contains_legacy_reference(line: str, legacy: str) -> bool:
    if legacy.startswith("mise run "):
        return re.search(rf"(?<![\w-]){re.escape(legacy)}(?![\w-])", line) is not None
    if legacy.endswith("/"):
        return legacy in line
    return re.search(rf"{re.escape(legacy)}(?![\w-])", line) is not None


def _legacy_reference_findings(repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for file_path in _tracked_paths(repo_root):
        relative = file_path.relative_to(repo_root)
        if (
            file_path == Path(__file__).resolve()
            or "tests" in relative.parts
            or not file_path.is_file()
        ):
            continue
        if _is_binary(file_path):
            continue
        try:
            lines = file_path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            for legacy in LEGACY_REFERENCES:
                if _contains_legacy_reference(line, legacy):
                    findings.append(
                        _finding(
                            Severity.ERROR,
                            "repository.legacy_reference",
                            "removed dotfiles workflow is still referenced",
                            file_path,
                            line=line_number,
                            value=legacy,
                        ),
                    )
    return findings


def _symlink_findings(repo_root: Path) -> list[Finding]:
    return [
        _finding(
            Severity.ERROR,
            "repository.dangling_symlink",
            "tracked symlink target does not exist",
            file_path,
        )
        for file_path in _tracked_paths(repo_root)
        if file_path.is_symlink() and not file_path.exists()
    ]


def _skillshare_config_findings(repo_root: Path) -> list[Finding]:
    config_path = repo_root / "reference/.config/skillshare/config.yaml"
    if not config_path.is_file():
        return []
    try:
        document = YAML(typ="safe").load(config_path)
    except Exception as error:
        return [
            _finding(
                Severity.ERROR,
                "skillshare.config_invalid",
                f"Skillshare config is not valid YAML: {error}",
                config_path,
            ),
        ]
    if not isinstance(document, dict):
        return [
            _finding(
                Severity.ERROR,
                "skillshare.config_invalid",
                "Skillshare config must be a mapping",
                config_path,
            ),
        ]

    findings: list[Finding] = []
    extras = document.get("extras", [])
    if not isinstance(extras, list):
        return [
            _finding(
                Severity.ERROR,
                "skillshare.config_invalid",
                "Skillshare extras must be a list",
                config_path,
            ),
        ]
    for extra in extras:
        if not isinstance(extra, dict):
            findings.append(
                _finding(
                    Severity.ERROR,
                    "skillshare.config_invalid",
                    "Skillshare extras entries must be mappings",
                    config_path,
                    value=str(extra),
                ),
            )
            continue
        name = extra.get("name", "<unnamed>")
        targets = extra.get("targets", [])
        if not isinstance(targets, list):
            findings.append(
                _finding(
                    Severity.ERROR,
                    "skillshare.config_invalid",
                    f"extra {name} targets must be a list",
                    config_path,
                    value=str(targets),
                ),
            )
            continue
        for target in targets:
            if not isinstance(target, dict):
                findings.append(
                    _finding(
                        Severity.ERROR,
                        "skillshare.config_invalid",
                        f"extra {name} targets must be mappings",
                        config_path,
                        value=str(target),
                    ),
                )
                continue
            target_path = target.get("path", "<missing>")
            if target.get("mode") != "copy":
                findings.append(
                    _finding(
                        Severity.ERROR,
                        "skillshare.extra_mode_unsafe",
                        f"extra {name} must use copy mode because its target contains runtime state",
                        config_path,
                        value=str(target_path),
                    ),
                )
    if not findings:
        findings.append(
            _finding(
                Severity.OK,
                "skillshare.extra_modes_safe",
                "all extras targets use non-pruning copy mode",
                config_path,
            ),
        )
    return findings


def inspect_repository(
    repo_root: Path,
    home: Path,
    *,
    system_name: str | None = None,
) -> LintReport:
    """Return repository path, mapping, and symlink invariants."""
    findings = _path_findings(repo_root, home, system_name or platform.system())
    findings.extend(_mackup_findings(repo_root))
    findings.extend(_symlink_findings(repo_root))
    findings.extend(_tracked_file_findings(repo_root))
    findings.extend(_legacy_reference_findings(repo_root))
    findings.extend(_skillshare_config_findings(repo_root))
    return LintReport(schema_version=1, findings=tuple(findings))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect repository invariants.")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--include-info", action="store_true")
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    report = inspect_repository(repo_root, Path.home())
    if args.as_json:
        print(
            json.dumps(
                finding_document(report, strict=args.strict),
                indent=2,
                sort_keys=True,
            ),
        )
    else:
        render_findings(report, include_ok=args.include_info)
    return 0 if report.is_ok(strict=args.strict) else 1


if __name__ == "__main__":
    raise SystemExit(main())
