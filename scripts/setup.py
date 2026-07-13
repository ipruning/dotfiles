"""Apply small, explicit host setup operations."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .profiles import HostProfile

BASH_BLOCK_START = "# >>> dotfiles linux-lite >>>"
BASH_BLOCK_END = "# <<< dotfiles linux-lite <<<"
PRIVATE_GITCONFIG = "~/.private.gitconfig"


class SetupError(RuntimeError):
    """The requested setup could not be applied safely."""


@dataclass(frozen=True)
class SetupReport:
    profile: HostProfile
    changed: bool
    dry_run: bool
    actions: tuple[str, ...]


def _bash_block(module_path: Path) -> str:
    quoted_module = shlex.quote(str(module_path))
    return (
        f"{BASH_BLOCK_START}\n"
        f"if [ -r {quoted_module} ]; then\n"
        f"  . {quoted_module}\n"
        "fi\n"
        f"{BASH_BLOCK_END}\n"
    )


def _replace_managed_block(current: str, replacement: str) -> str:
    start = current.find(BASH_BLOCK_START)
    end = current.find(BASH_BLOCK_END)
    if (start == -1) != (end == -1) or (start != -1 and end < start):
        raise SetupError("~/.bashrc contains an incomplete dotfiles managed block")
    if start != -1:
        end += len(BASH_BLOCK_END)
        if end < len(current) and current[end] == "\n":
            end += 1
        return replacement + current[:start] + current[end:]
    separator = "\n" if current else ""
    return replacement + separator + current


def _git_include_present(gitconfig: Path) -> bool:
    if not gitconfig.is_file():
        return False
    completed = subprocess.run(
        ["git", "config", "--file", str(gitconfig), "--get-all", "include.path"],
        check=False,
        capture_output=True,
        text=True,
    )
    return PRIVATE_GITCONFIG in completed.stdout.splitlines()


def configure_linux_lite(
    repo_root: Path,
    home: Path,
    *,
    dry_run: bool = False,
) -> SetupReport:
    """Connect Bash and the private Git include without inventing host identity."""
    module_path = repo_root.resolve() / "modules/bash/init.bash"
    if not module_path.is_file():
        raise SetupError(f"Linux Lite Bash module is missing: {module_path}")
    bashrc = home / ".bashrc"
    if bashrc.exists() and not bashrc.is_file():
        raise SetupError(f"Refusing to replace non-file Bash config: {bashrc}")
    current_bashrc = bashrc.read_text() if bashrc.is_file() else ""
    desired_bashrc = _replace_managed_block(current_bashrc, _bash_block(module_path))
    bash_changed = desired_bashrc != current_bashrc

    gitconfig = home / ".gitconfig"
    if gitconfig.exists() and not gitconfig.is_file():
        raise SetupError(f"Refusing to replace non-file Git config: {gitconfig}")
    git_include_changed = not _git_include_present(gitconfig)
    actions: list[str] = []
    if bash_changed:
        actions.append(f"configure Bash through {module_path}")
    if git_include_changed:
        actions.append(f"add {PRIVATE_GITCONFIG} to Git includes")

    if not dry_run:
        home.mkdir(parents=True, exist_ok=True)
        if bash_changed:
            bashrc.write_text(desired_bashrc)
        if git_include_changed:
            completed = subprocess.run(
                [
                    "git",
                    "config",
                    "--file",
                    str(gitconfig),
                    "--add",
                    "include.path",
                    PRIVATE_GITCONFIG,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                raise SetupError(
                    completed.stderr.strip() or "Git include update failed",
                )
    return SetupReport(
        profile=HostProfile.LINUX_LITE,
        changed=bool(actions),
        dry_run=dry_run,
        actions=tuple(actions),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply explicit host setup.")
    parser.add_argument(
        "--profile",
        choices=[HostProfile.LINUX_LITE.value],
        required=True,
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    try:
        report = configure_linux_lite(repo_root, Path.home(), dry_run=args.dry_run)
    except SetupError as error:
        print(f"ERROR setup_failed {error}", file=sys.stderr)
        return 1
    document = {
        "profile": report.profile.value,
        "changed": report.changed,
        "dry_run": report.dry_run,
        "actions": list(report.actions),
    }
    if args.as_json:
        print(json.dumps(document, indent=2, sort_keys=True))
    elif report.actions:
        for action in report.actions:
            prefix = "WOULD" if report.dry_run else "CHANGED"
            print(f"{prefix} {action}")
    else:
        print("No changes required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
