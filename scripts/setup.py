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


def _next_commands(report: SetupReport) -> tuple[str, ...]:
    if not report.apply and report.profile is HostProfile.LINUX_LITE and report.changed:
        return ("mise run setup -- --profile linux-lite --apply",)
    return ()


def _shell_restart_required(report: SetupReport) -> bool:
    return report.apply and any(
        change.status is SetupStatus.APPLIED
        and change.action.startswith("configure Bash through ")
        for change in report.changes
    )


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
    if completed.returncode not in {0, 1}:
        raise SetupError(
            completed.stderr.strip() or "could not inspect Git include configuration"
        )
    return PRIVATE_GITCONFIG in completed.stdout.splitlines()


def _write_file(path: Path, content: bytes, mode: int) -> None:
    descriptor, tmp_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, path)
    except OSError:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def _write_bashrc(bashrc: Path, content: str) -> None:
    mode = bashrc.stat().st_mode & 0o777 if bashrc.is_file() else 0o644
    _write_file(bashrc, content.encode(), mode)


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
    if gitconfig.is_symlink():
        raise SetupError(f"Refusing to write through Git config symlink: {gitconfig}")
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
        gitconfig_existed = False
        gitconfig_before = b""
        gitconfig_mode = 0o644
        if git_include_changed:
            gitconfig_existed = gitconfig.is_file()
            try:
                if gitconfig_existed:
                    gitconfig_before = gitconfig.read_bytes()
                    gitconfig_mode = gitconfig.stat().st_mode & 0o777
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
                raise SetupError(
                    f"could not update Git config {gitconfig}: {error}"
                ) from error
            if completed.returncode != 0:
                raise SetupError(
                    completed.stderr.strip() or "Git include update failed",
                )
        if bash_changed:
            try:
                _write_bashrc(bashrc, desired_bashrc)
            except OSError as error:
                if git_include_changed:
                    try:
                        if gitconfig_existed:
                            _write_file(
                                gitconfig,
                                gitconfig_before,
                                gitconfig_mode,
                            )
                        else:
                            gitconfig.unlink(missing_ok=True)
                    except OSError as rollback_error:
                        raise SetupError(
                            f"could not update Bash config {bashrc}: {error}; "
                            "Git include was added and rollback failed: "
                            f"{rollback_error}"
                        ) from error
                    raise SetupError(
                        f"could not update Bash config {bashrc}: {error}; "
                        "rolled back the Git include update",
                    ) from error
                raise SetupError(
                    f"could not update Bash config {bashrc}: {error}"
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
        emit_error("setup", str(error), as_json=args.as_json, apply=args.apply)
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
        "next": list(_next_commands(report)),
        "shell_restart_required": _shell_restart_required(report),
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
    print(f"Profile: {report.profile.value}")
    for change in report.changes:
        print(f"{change.status.value.upper():7} {change.action}")
    rendered = ", ".join(f"{count} {status}" for status, count in summary.items())
    print(f"Summary: {rendered or 'no changes'}")
    if not report.changes:
        print("No changes required.")
    elif not report.apply:
        print("No files changed. Re-run with --apply to configure this host.")
        print("Next:")
        for command in _next_commands(report):
            print(f"  {command}")
    elif _shell_restart_required(report):
        print("Updated Bash startup configuration is not active in this shell.")
        print("Open a new Bash or run `exec bash` to load it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
