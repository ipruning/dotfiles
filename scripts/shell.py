"""Check repository shell files without changing them."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .models import ExecutableFinder, Finding, FindingReport, Severity
from .render import emit_error, finding_document, render_findings


BASH_SUFFIXES = {".bash", ".sh"}
ZSH_SUFFIXES = {".zsh"}
# Startup dotfiles carry no shell suffix or shebang but are real shell that
# restore links into $HOME, so recognize them by name even under reference/.
ZSH_DOTFILES = {".zshrc", ".zshenv", ".zprofile", ".zlogin", ".zlogout"}
BASH_DOTFILES = {".bashrc", ".bash_profile", ".bash_login", ".profile"}
SKIP_PREFIXES = ("reference/",)
SHELLCHECK_SEVERITY = "warning"


class ShellCheckError(RuntimeError):
    """The shell inspection could not run to completion."""


@dataclass(frozen=True)
class ShellFile:
    path: Path
    dialect: str


@dataclass(frozen=True)
class ShellReport(FindingReport):
    pass


def shell_dialect(relative: str, first_line: str, second_line: str = "") -> str | None:
    """Return the shell dialect of a tracked file, or None for non-shell files."""
    name = Path(relative).name
    if name in ZSH_DOTFILES:
        return "zsh"
    if name in BASH_DOTFILES:
        return "bash"
    if relative.startswith(SKIP_PREFIXES):
        return None
    suffix = Path(relative).suffix
    if suffix in BASH_SUFFIXES:
        return "bash"
    if suffix in ZSH_SUFFIXES:
        return "zsh"
    if not first_line.startswith("#!"):
        return None
    if second_line.startswith('""":"'):
        # sh-launcher/Python polyglot: the body is Python, not shell.
        return None
    interpreter_tokens = [
        token
        for token in first_line[2:].split()
        if Path(token).name != "env" and not token.startswith("-") and "=" not in token
    ]
    interpreter = Path(interpreter_tokens[0]).name if interpreter_tokens else ""
    if interpreter == "zsh":
        return "zsh"
    if interpreter in {"bash", "sh", "dash", "ash"}:
        return "bash"
    return None


def collect_shell_files(repo_root: Path) -> list[ShellFile]:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ShellCheckError("unable to list tracked files")
    files: list[ShellFile] = []
    for item in completed.stdout.split(b"\0"):
        if not item:
            continue
        relative = item.decode()
        file_path = repo_root / relative
        if file_path.is_symlink() or not file_path.is_file():
            continue
        try:
            head = file_path.read_bytes().split(b"\n", 2)
        except OSError:
            continue
        first_line = head[0].decode(errors="replace")
        second_line = head[1].decode(errors="replace") if len(head) > 1 else ""
        dialect = shell_dialect(relative, first_line, second_line)
        if dialect:
            files.append(ShellFile(path=file_path, dialect=dialect))
    return files


def _require_tool(name: str, executable_finder: ExecutableFinder) -> str:
    tool = executable_finder(name)
    if tool is None:
        raise ShellCheckError(
            f"{name} is required to verify shell files; install it first",
        )
    return tool


def check_shell_files(
    repo_root: Path,
    *,
    executable_finder: ExecutableFinder = shutil.which,
) -> ShellReport:
    """Return error findings and loud skips for tracked bash and zsh files."""
    files = collect_shell_files(repo_root)
    bash_files = [item.path for item in files if item.dialect == "bash"]
    zsh_files = [item.path for item in files if item.dialect == "zsh"]
    findings: list[Finding] = []

    bash_bin = _require_tool("bash", executable_finder) if bash_files else ""
    for file_path in bash_files:
        completed = subprocess.run(
            [bash_bin, "-n", str(file_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            findings.append(
                Finding(
                    check="shell",
                    severity=Severity.ERROR,
                    code="shell.bash_syntax",
                    message=completed.stderr.strip(),
                    path=file_path,
                ),
            )
    if bash_files:
        shellcheck_bin = _require_tool("shellcheck", executable_finder)
        completed = subprocess.run(
            [
                shellcheck_bin,
                "--severity",
                SHELLCHECK_SEVERITY,
                *[str(file_path) for file_path in bash_files],
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            detail = completed.stdout.strip() or completed.stderr.strip()
            findings.append(
                Finding(
                    check="shell",
                    severity=Severity.ERROR,
                    code="shell.shellcheck",
                    message=detail,
                ),
            )

    zsh_bin = executable_finder("zsh") if zsh_files else None
    if zsh_files and zsh_bin is None:
        # zsh is not pinnable through mise, and hosts without zsh never run
        # the zsh configuration; skip loudly instead of failing the gate.
        findings.append(
            Finding(
                check="shell",
                severity=None,
                code="shell.zsh_skipped",
                message=f"skipped {len(zsh_files)} zsh files: zsh is not installed",
            ),
        )
    elif zsh_bin is not None:
        for file_path in zsh_files:
            completed = subprocess.run(
                [zsh_bin, "-n", str(file_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                findings.append(
                    Finding(
                        check="shell",
                        severity=Severity.ERROR,
                        code="shell.zsh_syntax",
                        message=completed.stderr.strip(),
                        path=file_path,
                    ),
                )
    return ShellReport(schema_version=1, findings=tuple(findings))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check repository shell files.")
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit the report as JSON on stdout",
    )
    parser.add_argument(
        "--include-ok",
        action="store_true",
        help="also list ok findings (default: warn, error, and skipped only)",
    )
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    try:
        report = check_shell_files(repo_root)
    except ShellCheckError as error:
        emit_error("shell", str(error), as_json=args.as_json)
        return 1
    if args.as_json:
        print(
            json.dumps(
                finding_document(report, operation="shell"),
                indent=2,
                sort_keys=True,
            ),
        )
    else:
        render_findings(report, include_ok=args.include_ok)
    return 0 if report.is_ok() else 1


if __name__ == "__main__":
    raise SystemExit(main())
