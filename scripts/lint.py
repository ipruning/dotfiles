"""Inspect repository invariants without changing tracked files."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import starmap
from pathlib import Path

from .mappings import (
    MappingError,
    application_config_path,
    read_application_mapping,
    read_mapping_config,
    selected_applications,
)
from .models import Finding, LintReport, Severity
from .render import finding_document, render_findings

PATH_RE = re.compile(
    r"(?P<path>"
    r"/Applications/[^\"'<>),;\]]+?\.app(?:/(?:\\ |[^\s\"'<>),;:\]\}\\])*)?"
    r"|/(?:Users|home)/[A-Za-z0-9._-]+(?:/(?:\\ |[^\s\"'<>),;:\]\}\\])*)?"
    r"|/root(?:/(?:\\ |[^\s\"'<>),;:\]\}\\])*)?"
    r"|/opt/homebrew(?:/(?:\\ |[^\s\"'<>),;:\]\}\\])*)?"
    r"|/usr/local(?:/(?:\\ |[^\s\"'<>),;:\]\}\\])*)?"
    r"|(?:~|\$HOME|\$\{HOME\})/(?:\\ |[^\s\"'<>),;:\]\}\\])+"
    r")",
)
URL_RE = re.compile(r"https?://\S+")
STRUCTURED_DATA_TEXT_PARSER_RES = (
    re.compile(
        r"\b(?:grep|rg)\b[^\n]*(?:\.jsonl?|\.toml|\.ya?ml)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:grep|rg)\b[^\n]*=[^\n]*\|\s*sed\b"),
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
}
# inventory/ snapshots quote live host state (Brewfile source paths, app
# names); they are data to diff, not path references this repository maintains.
SKIP_PREFIXES = ("generated/", "inventory/")
OPTIONAL_PATHS = {
    ("reference/.zshenv", "/usr/local/sbin"),
    ("reference/.zshrc", "/usr/local/Homebrew"),
    ("reference/.zshrc", "/usr/local/Cellar"),
    ("reference/.zshrc", "/usr/local/share/zsh/site-functions"),
    ("reference/.zshrc", "/usr/local/share/info"),
}


def _located_finding(
    severity: Severity | None,
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


def _iter_text_files(repo_root: Path, candidates: list[Path]) -> list[Path]:
    files: list[Path] = []
    for file_path in candidates:
        relative = file_path.relative_to(repo_root)
        relative_text = relative.as_posix()
        if any(part in SKIP_PARTS for part in relative.parts):
            continue
        if file_path.resolve() == Path(__file__).resolve():
            continue
        if relative_text.startswith(SKIP_PREFIXES):
            continue
        if file_path.is_symlink() or not file_path.is_file():
            continue
        if file_path.suffix.lower() in SKIP_SUFFIXES or _is_binary(file_path):
            continue
        files.append(file_path)
    return sorted(files)


@dataclass(frozen=True)
class HostBoundPath:
    """A path in a tracked text file that only resolves on some hosts."""

    kind: str
    source: Path
    line: int | None
    raw: str


HOST_BOUND_KINDS = frozenset(
    {"dotfiles_root", "personal_workspace", "toolchain", "application"},
)


def _path_kind(relative: str, raw: str) -> str:
    if (relative, raw) in OPTIONAL_PATHS:
        return "optional_compatibility"
    if raw.startswith(("/Users/", "/home/", "/root/")):
        return "absolute_home"
    if raw.startswith(("~/dotfiles", "$HOME/dotfiles", "${HOME}/dotfiles")):
        return "dotfiles_root"
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
        return "personal_workspace"
    if raw.startswith(("/opt/homebrew", "/usr/local")):
        return "toolchain"
    if raw.startswith("/Applications/"):
        if "\\" in raw or "{" in raw or raw.endswith("$"):
            return "application_pattern"
        return "application"
    return "home_relative"


PATH_KIND_MESSAGES = {
    "optional_compatibility": "explicitly guarded compatibility path",
    "dotfiles_root": "path assumes the repository at ~/dotfiles",
    "personal_workspace": "home-relative path binds this config to a personal workspace",
    "toolchain": "machine or architecture-specific toolchain path",
    "application_pattern": "application path pattern used for process matching",
    "application": "macOS application path",
    "home_relative": "home-relative path",
}


def _classify_path(relative: str, source: Path, line: int | None, raw: str) -> Finding:
    kind = _path_kind(relative, raw)
    if kind == "absolute_home":
        return _located_finding(
            Severity.ERROR,
            "path.absolute_home",
            "replace the absolute user path with a supported home-relative form",
            source,
            line=line,
            value=raw,
        )
    return _located_finding(
        Severity.OK,
        f"path.{kind}",
        PATH_KIND_MESSAGES[kind],
        source,
        line=line,
        value=raw,
    )


def _toml_strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _toml_strings(key)
            yield from _toml_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _toml_strings(item)


def _path_tokens(line: str) -> Iterator[str]:
    url_spans = [url.span() for url in URL_RE.finditer(line)]
    for match in PATH_RE.finditer(line):
        if not any(begin <= match.start("path") < end for begin, end in url_spans):
            raw = match.group("path")
            assert isinstance(raw, str)
            yield raw.rstrip(".,:")


def _iter_paths(
    repo_root: Path,
    text_files: list[Path],
    *,
    unreadable_toml: list[Path] | None = None,
) -> Iterator[tuple[str, Path, int | None, str]]:
    for file_path in text_files:
        relative = file_path.relative_to(repo_root).as_posix()
        if unreadable_toml is not None and file_path.suffix.lower() == ".toml":
            try:
                with file_path.open("rb") as stream:
                    document = tomllib.load(stream)
            except OSError, UnicodeError, tomllib.TOMLDecodeError:
                unreadable_toml.append(file_path)
                continue
            for value in _toml_strings(document):
                for line in value.splitlines():
                    for raw in _path_tokens(line):
                        yield relative, file_path, None, raw
            continue
        try:
            lines = file_path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            for raw in _path_tokens(line):
                yield relative, file_path, line_number, raw


def _path_findings(repo_root: Path, text_files: list[Path]) -> list[Finding]:
    return list(starmap(_classify_path, _iter_paths(repo_root, text_files)))


def host_bound_paths(repo_root: Path) -> tuple[list[HostBoundPath], list[Path]]:
    """Return host-bound paths and TOML files that could not be parsed."""
    candidates, _finding = _tracked_paths(repo_root, include_untracked=True)
    unreadable_toml: list[Path] = []
    paths = [
        HostBoundPath(kind, file_path, line, raw)
        for relative, file_path, line, raw in _iter_paths(
            repo_root,
            _iter_text_files(repo_root, candidates),
            unreadable_toml=unreadable_toml,
        )
        if (kind := _path_kind(relative, raw)) in HOST_BOUND_KINDS
    ]
    return paths, unreadable_toml


def _structured_data_parser_findings(
    repo_root: Path, text_files: list[Path]
) -> list[Finding]:
    findings: list[Finding] = []
    for file_path in text_files:
        try:
            lines = file_path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if any(pattern.search(line) for pattern in STRUCTURED_DATA_TEXT_PARSER_RES):
                findings.append(
                    _located_finding(
                        Severity.ERROR,
                        "repository.structured_data_text_parser",
                        "use a JSON, TOML, or YAML parser instead of text matching",
                        file_path,
                        line=line_number,
                    ),
                )
    if not findings:
        findings.append(
            _located_finding(
                Severity.OK,
                "repository.structured_data_parsers",
                "no text-based JSON, TOML, or YAML parser detected",
                repo_root,
            ),
        )
    return findings


def _mackup_findings(repo_root: Path, tracked_paths: set[Path]) -> list[Finding]:
    config_path = repo_root / "mackup/mackup.cfg"
    if not config_path.is_file():
        return [
            _located_finding(
                Severity.ERROR,
                "mackup.config_missing",
                "Mackup config is missing",
                config_path,
            ),
        ]
    try:
        applications = selected_applications(read_mapping_config(config_path))
    except MappingError as error:
        return [
            _located_finding(
                Severity.ERROR, "mackup.config_invalid", str(error), config_path
            )
        ]

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
                    _located_finding(
                        Severity.ERROR,
                        "mackup.mapping_unused",
                        "mapping is not selected in applications_to_sync;"
                        " adopt the application or delete the mapping",
                        mapping_path,
                    ),
                )
    for application in applications:
        try:
            app_path = application_config_path(applications_dir, application)
        except MappingError as error:
            findings.append(
                _located_finding(
                    Severity.ERROR, "mackup.config_invalid", str(error), config_path
                )
            )
            continue
        if not app_path.is_file():
            findings.append(
                _located_finding(
                    Severity.ERROR,
                    "mackup.application_missing",
                    f"selected application {application} has no mapping",
                    app_path,
                ),
            )
            continue
        try:
            mapping = read_application_mapping(app_path)
        except MappingError as error:
            findings.append(
                _located_finding(
                    Severity.ERROR, "mackup.mapping_invalid", str(error), app_path
                )
            )
            continue
        reference = repo_root / "reference"
        candidates = [reference / item for item in mapping.home_paths]
        candidates.extend(reference / ".config" / item for item in mapping.xdg_paths)
        optional_candidates = {reference / item for item in mapping.optional_paths}
        candidate_set = set(candidates)
        for candidate in sorted(optional_candidates - candidate_set):
            findings.append(
                _located_finding(
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
                _located_finding(
                    Severity.ERROR,
                    "mackup.reference_missing",
                    f"selected application {application} maps missing reference data",
                    candidate,
                ),
            )
        if candidates and len(missing_candidates) == len(candidates):
            findings.append(
                _located_finding(
                    Severity.ERROR,
                    "mackup.application_empty",
                    f"selected application {application} has no reference data",
                    app_path,
                ),
            )
    if not findings:
        findings.append(
            _located_finding(
                Severity.OK,
                "mackup.mapping_ready",
                f"{len(applications)} selected applications have reference data",
                config_path,
            ),
        )
    return findings


def _tracked_paths(
    repo_root: Path, *, include_untracked: bool = False
) -> tuple[list[Path], Finding | None]:
    command = ["git", "-C", str(repo_root), "ls-files", "-z"]
    if include_untracked:
        command.extend(("--cached", "--others", "--exclude-standard"))
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
    )
    if completed.returncode == 0:
        return (
            [
                repo_root / item.decode()
                for item in completed.stdout.split(b"\0")
                if item
            ],
            None,
        )
    detail = completed.stderr.decode(errors="replace").strip()
    if "not a git repository" in detail.lower():
        if include_untracked:
            return list(repo_root.rglob("*")), None
        return [], None
    return (
        [],
        _located_finding(
            Severity.ERROR,
            "repository.tracked_files_unavailable",
            "git ls-files failed" + (f": {detail}" if detail else ""),
            repo_root,
        ),
    )


def _tracked_file_findings(repo_root: Path, tracked_paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for file_path in tracked_paths:
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
                _located_finding(
                    Severity.ERROR,
                    "repository.private_tracked",
                    "materialized private file must not be tracked",
                    file_path,
                ),
            )
        if relative.startswith("generated/"):
            findings.append(
                _located_finding(
                    Severity.ERROR,
                    "repository.generated_tracked",
                    "generated/ output must not be tracked; mise run generate rewrites it",
                    file_path,
                ),
            )
    return findings


def _mise_alias_findings(repo_root: Path) -> list[Finding]:
    config_path = repo_root / "reference/.config/mise/config.toml"
    if not config_path.is_file():
        return []
    try:
        config = tomllib.loads(config_path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as error:
        return [
            _located_finding(
                Severity.ERROR,
                "mise.config_invalid",
                f"shared mise config is unreadable or invalid: {error}",
                config_path,
            ),
        ]

    tools = config.get("tools", {})
    if not isinstance(tools, dict):
        return [
            _located_finding(
                Severity.ERROR,
                "mise.config_invalid",
                "shared mise [tools] section must be a table",
                config_path,
            ),
        ]

    aliases: dict[str, str] = {}
    for section in ("alias", "tool_alias"):
        section_aliases = config.get(section, {})
        if not isinstance(section_aliases, dict):
            return [
                _located_finding(
                    Severity.ERROR,
                    "mise.config_invalid",
                    f"shared mise [{section}] section must be a table",
                    config_path,
                ),
            ]
        for alias, value in section_aliases.items():
            aliases.pop(alias, None)
            backend = value.get("backend") if isinstance(value, dict) else value
            if backend is None:
                continue
            if not isinstance(backend, str):
                return [
                    _located_finding(
                        Severity.ERROR,
                        "mise.config_invalid",
                        f"shared mise [{section}] backends must be strings",
                        config_path,
                    ),
                ]
            aliases[alias] = backend

    findings = [
        _located_finding(
            Severity.ERROR,
            "mise.alias_duplicate_identity",
            f"declare {alias}, not both {alias} and its backend identity {backend}",
            config_path,
        )
        for alias, backend in aliases.items()
        if alias in tools and backend in tools
    ]
    if findings:
        return findings
    return [
        _located_finding(
            Severity.OK,
            "mise.alias_identities_unique",
            "shared mise tools use one identity per alias",
            config_path,
        ),
    ]


def _symlink_findings(tracked_paths: list[Path]) -> list[Finding]:
    return [
        _located_finding(
            Severity.ERROR,
            "repository.dangling_symlink",
            "tracked symlink target does not exist",
            file_path,
        )
        for file_path in tracked_paths
        if file_path.is_symlink() and not file_path.exists()
    ]


def inspect_repository(repo_root: Path) -> LintReport:
    """Return repository path, mapping, and symlink invariants."""
    tracked_paths, tracked_finding = _tracked_paths(repo_root)
    candidates, candidate_finding = _tracked_paths(repo_root, include_untracked=True)
    text_files = _iter_text_files(repo_root, candidates)
    findings = _path_findings(repo_root, text_files)
    findings.extend(_structured_data_parser_findings(repo_root, text_files))
    if finding := tracked_finding or candidate_finding:
        findings.append(finding)
    findings.extend(_mackup_findings(repo_root, set(tracked_paths)))
    findings.extend(_symlink_findings(tracked_paths))
    findings.extend(_tracked_file_findings(repo_root, tracked_paths))
    findings.extend(_mise_alias_findings(repo_root))
    return LintReport(schema_version=1, findings=tuple(findings))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect repository invariants.")
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
        "--include-ok",
        action="store_true",
        help="also list ok findings (default: warn, error, and skipped only)",
    )
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    report = inspect_repository(repo_root)
    if args.as_json:
        print(
            json.dumps(
                finding_document(report, operation="lint", strict=args.strict),
                indent=2,
                sort_keys=True,
            ),
        )
    else:
        render_findings(report, include_ok=args.include_ok)
    return 0 if report.is_ok(strict=args.strict) else 1


if __name__ == "__main__":
    raise SystemExit(main())
