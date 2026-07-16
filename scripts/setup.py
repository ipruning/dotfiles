"""Apply small, explicit host setup operations."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .profiles import HostProfile
from .render import emit_error

BASH_BLOCK_START = "# >>> dotfiles linux-lite >>>"
BASH_BLOCK_END = "# <<< dotfiles linux-lite <<<"
PRIVATE_GITCONFIG = "~/.private.gitconfig"


class SetupError(RuntimeError):
    """The requested setup could not be applied safely."""


class SetupStatus(StrEnum):
    PLANNED = "planned"
    APPLIED = "applied"


@dataclass(frozen=True)
class SetupChange:
    action: str
    status: SetupStatus


@dataclass(frozen=True)
class SetupReport:
    profile: HostProfile
    apply: bool
    changes: tuple[SetupChange, ...]

    @property
    def changed(self) -> bool:
        return bool(self.changes)


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
    try:
        completed = subprocess.run(
            ["git", "config", "--file", str(gitconfig), "--get-all", "include.path"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise SetupError(f"could not run git: {error}") from error
    return PRIVATE_GITCONFIG in completed.stdout.splitlines()


def _write_bashrc(bashrc: Path, content: str) -> None:
    mode = bashrc.stat().st_mode & 0o777 if bashrc.is_file() else 0o644
    descriptor, tmp_name = tempfile.mkstemp(dir=str(bashrc.parent), prefix=".bashrc.")
    try:
        with os.fdopen(descriptor, "w") as handle:
            handle.write(content)
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, bashrc)
    except OSError:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def plan_setup(repo_root: Path, home: Path) -> SetupReport:
    """Return the Linux Lite setup plan without writing host configuration."""
    return _configure_linux_lite(repo_root, home, apply=False)


def apply_setup(repo_root: Path, home: Path) -> SetupReport:
    """Connect Bash and the private Git include without inventing host identity."""
    return _configure_linux_lite(repo_root, home, apply=True)


def _configure_linux_lite(
    repo_root: Path,
    home: Path,
    *,
    apply: bool,
) -> SetupReport:
    module_path = repo_root.resolve() / "modules/bash/init.bash"
    if not module_path.is_file():
        raise SetupError(f"Linux Lite Bash module is missing: {module_path}")
    bashrc = home / ".bashrc"
    if bashrc.is_symlink():
        raise SetupError(f"Refusing to write through Bash config symlink: {bashrc}")
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

    if apply:
        home.mkdir(parents=True, exist_ok=True)
        if git_include_changed:
            try:
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
            except OSError as error:
                raise SetupError(f"could not run git: {error}") from error
            if completed.returncode != 0:
                raise SetupError(
                    completed.stderr.strip() or "Git include update failed",
                )
        if bash_changed:
            try:
                _write_bashrc(bashrc, desired_bashrc)
            except OSError as error:
                raise SetupError(
                    f"could not update Bash config {bashrc}: {error}",
                ) from error
    status = SetupStatus.APPLIED if apply else SetupStatus.PLANNED
    return SetupReport(
        profile=HostProfile.LINUX_LITE,
        apply=apply,
        changes=tuple(SetupChange(action=action, status=status) for action in actions),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply explicit host setup.")
    parser.add_argument(
        "--profile",
        choices=[HostProfile.LINUX_LITE.value],
        required=True,
        help="host profile whose setup should run",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the planned setup changes (default: preview only)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit the report as JSON on stdout",
    )
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    setup = apply_setup if args.apply else plan_setup
    try:
        report = setup(repo_root, Path.home())
    except SetupError as error:
        emit_error("setup", str(error), as_json=args.as_json)
        return 1
    summary = {
        status.value: sum(change.status is status for change in report.changes)
        for status in SetupStatus
        if any(change.status is status for change in report.changes)
    }
    document = {
        "schema_version": 1,
        "operation": "setup",
        "apply": report.apply,
        "ok": True,
        "profile": report.profile.value,
        "changes": [
            {"action": change.action, "status": change.status.value}
            for change in report.changes
        ],
        "summary": summary,
    }
    if args.as_json:
        print(json.dumps(document, indent=2, sort_keys=True))
        return 0
    for change in report.changes:
        print(f"{change.status.value.upper():7} {change.action}")
    if not report.changes:
        print("No changes required.")
    elif not report.apply:
        print("No files changed. Re-run with --apply to configure this host.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
