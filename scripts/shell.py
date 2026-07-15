"""Check repository shell files without changing them."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ExecutableFinder = Callable[[str], str | None]

BASH_SUFFIXES = {".bash", ".sh"}
ZSH_SUFFIXES = {".zsh"}
SKIP_PREFIXES = ("reference/",)
SHELLCHECK_SEVERITY = "warning"


class ShellCheckError(RuntimeError):
    """The shell inspection could not run to completion."""


@dataclass(frozen=True)
class ShellFile:
    path: Path
    dialect: str


def classify(relative: str, first_line: str, second_line: str = "") -> str | None:
    """Return the shell dialect of a tracked file, or None for non-shell files."""
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
        dialect = classify(relative, first_line, second_line)
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
) -> list[str]:
    """Return failure descriptions for tracked bash and zsh files."""
    files = collect_shell_files(repo_root)
    bash_files = [item.path for item in files if item.dialect == "bash"]
    zsh_files = [item.path for item in files if item.dialect == "zsh"]
    failures: list[str] = []

    bash_bin = _require_tool("bash", executable_finder) if bash_files else ""
    for file_path in bash_files:
        completed = subprocess.run(
            [bash_bin, "-n", str(file_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            failures.append(f"bash syntax: {completed.stderr.strip()}")
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
            failures.append(f"shellcheck: {detail}")

    if zsh_files:
        zsh_bin = _require_tool("zsh", executable_finder)
        for file_path in zsh_files:
            completed = subprocess.run(
                [zsh_bin, "-n", str(file_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                failures.append(f"zsh syntax: {completed.stderr.strip()}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check repository shell files.")
    parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    try:
        failures = check_shell_files(repo_root)
    except ShellCheckError as error:
        print(f"ERROR shell_check_failed {error}", file=sys.stderr)
        return 1
    for failure in failures:
        print(failure, file=sys.stderr)
    if failures:
        return 1
    print("Shell files pass syntax and ShellCheck gates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
