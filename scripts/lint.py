"""Inspect repository invariants without changing tracked files."""

from __future__ import annotations

import argparse
import configparser
import json
import re
from pathlib import Path

from .models import Finding, LintReport, Severity

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
    ".DS_Store",
}
SKIP_PREFIXES = ("generated/", "reference/Library/")
FULL_HOME_REQUIRED_FILES = {
    "reference/.config/zellij/config.kdl": (
        "zellij-sessionizer paths do not expand home variables"
    ),
}
OPTIONAL_PATHS = {
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
    (
        "modules/macos-session-health/macos-session-health",
        "/Applications/ChatGPT\\.app/Contents/MacOS/ChatGPT$",
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
) -> Finding:
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
        if not (raw == str(home) or raw.startswith(f"{home}/")):
            return _finding(
                Severity.ERROR,
                "path.absolute_home",
                f"absolute user path does not match HOME={home}",
                source,
                line=line,
                value=raw,
            )
        if relative in FULL_HOME_REQUIRED_FILES:
            return _finding(
                Severity.OK,
                "path.full_home_required",
                FULL_HOME_REQUIRED_FILES[relative],
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
        severity = Severity.OK if repo_root.resolve() == expected else Severity.ERROR
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
            Severity.OK if _path_exists(raw, home) else Severity.WARN,
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


def _path_findings(repo_root: Path, home: Path) -> list[Finding]:
    findings: list[Finding] = []
    for file_path in _iter_text_files(repo_root):
        relative = file_path.relative_to(repo_root).as_posix()
        try:
            lines = file_path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            for match in PATH_RE.finditer(line):
                raw = match.group("path").rstrip(".,:")
                if "http://" in raw or "https://" in raw:
                    continue
                findings.append(
                    _classify_path(
                        repo_root,
                        home,
                        relative,
                        file_path,
                        line_number,
                        raw,
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
    findings: list[Finding] = []
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
        if not any(candidate.exists() for candidate in candidates):
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


def _symlink_findings(repo_root: Path) -> list[Finding]:
    return [
        _finding(
            Severity.ERROR,
            "repository.dangling_symlink",
            "symlink target does not exist",
            file_path,
        )
        for file_path in repo_root.rglob("*")
        if file_path.is_symlink() and not file_path.exists()
    ]


def inspect_repository(repo_root: Path, home: Path) -> LintReport:
    """Return repository path, mapping, and symlink invariants."""
    findings = _path_findings(repo_root, home)
    findings.extend(_mackup_findings(repo_root))
    findings.extend(_symlink_findings(repo_root))
    return LintReport(schema_version=1, findings=tuple(findings))


def _document(report: LintReport) -> dict[str, object]:
    return {
        "schema_version": report.schema_version,
        "ok": report.ok,
        "findings": [
            {
                "check": finding.check,
                "severity": finding.severity.value,
                "code": finding.code,
                "message": finding.message,
                "path": str(finding.path) if finding.path else None,
                "action": finding.action,
            }
            for finding in report.findings
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect repository invariants.")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--include-info", action="store_true")
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    report = inspect_repository(repo_root, Path.home())
    if args.as_json:
        print(json.dumps(_document(report), indent=2, sort_keys=True))
    else:
        visible = [
            finding
            for finding in report.findings
            if args.include_info or finding.severity is not Severity.OK
        ]
        if not visible:
            print("No repository findings.")
        for finding in visible:
            print(f"{finding.severity.value.upper():7} {finding.code}")
            print(f"        {finding.message}")
        counts = {
            severity.value: sum(
                finding.severity is severity for finding in report.findings
            )
            for severity in Severity
        }
        print(
            "Summary: "
            + ", ".join(f"{count} {name}" for name, count in counts.items()),
        )
    return 0 if report.is_ok(strict=args.strict) else 1


if __name__ == "__main__":
    raise SystemExit(main())
