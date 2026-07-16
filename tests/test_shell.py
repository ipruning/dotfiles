import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.models import Severity
from scripts.shell import ShellCheckError, check_shell_files, shell_dialect

requires_shellcheck = pytest.mark.skipif(
    shutil.which("shellcheck") is None,
    reason="shellcheck is not installed",
)
requires_zsh = pytest.mark.skipif(
    shutil.which("zsh") is None,
    reason="zsh is not installed",
)


def _tracked_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo_root = tmp_path / "repo"
    for relative, content in files.items():
        file_path = repo_root / relative
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
    subprocess.run(["git", "init", "-q", str(repo_root)], check=True)
    subprocess.run(["git", "-C", str(repo_root), "add", "."], check=True)
    return repo_root


def test_shell_dialect_covers_extensions_shebangs_and_reference_data() -> None:
    assert shell_dialect("modules/bash/init.bash", "# sourced fragment") == "bash"
    assert shell_dialect("modules/bin/_lib/session-id.sh", "") == "bash"
    assert shell_dialect("modules/zsh/env.zsh", "") == "zsh"
    assert shell_dialect("modules/bin/g", "#!/usr/bin/env bash") == "bash"
    assert shell_dialect("modules/bin/ttok", "#!/usr/bin/env -S zsh -f") == "zsh"
    assert shell_dialect("modules/bin/watchdog", "#!/bin/sh") == "bash"
    assert shell_dialect("modules/bin/portable", "#!/usr/bin/env sh") == "bash"
    assert shell_dialect("modules/bin/dashy", "#!/bin/dash") == "bash"
    assert shell_dialect("modules/bin/pyenvish", "#!/usr/bin/env -S python3 -u") is None
    assert shell_dialect("scripts/diff.py", "#!/usr/bin/env python3") is None
    assert shell_dialect("reference/.zshenv.private.tpl.zsh", "") is None
    assert shell_dialect("notes.txt", "plain text") is None
    assert shell_dialect("modules/tool/tool", "#!/bin/sh", '""":"') is None


def test_check_shell_files_reports_bash_syntax_failures_then_passes(
    tmp_path: Path,
) -> None:
    repo_root = _tracked_repo(
        tmp_path,
        {
            "modules/bin/good": "#!/usr/bin/env bash\nprintf 'ok\\n'\n",
            "modules/bin/broken": "#!/usr/bin/env bash\nif true; then\n",
        },
    )
    quiet_shellcheck = tmp_path / "quiet-shellcheck"
    quiet_shellcheck.write_text("#!/bin/sh\nexit 0\n")
    quiet_shellcheck.chmod(0o755)

    def finder(name: str) -> str | None:
        return str(quiet_shellcheck) if name == "shellcheck" else shutil.which(name)

    failing = check_shell_files(repo_root, executable_finder=finder)
    syntax_findings = [
        finding for finding in failing.findings if finding.code == "shell.bash_syntax"
    ]
    assert syntax_findings
    assert all(
        finding.severity is Severity.ERROR and finding.path is not None
        for finding in syntax_findings
    )
    assert failing.is_ok() is False

    (repo_root / "modules/bin/broken").write_text(
        "#!/usr/bin/env bash\nif true; then\n  printf 'ok\\n'\nfi\n",
    )
    assert check_shell_files(repo_root, executable_finder=finder).is_ok() is True


@requires_shellcheck
def test_check_shell_files_reports_shellcheck_warnings(tmp_path: Path) -> None:
    repo_root = _tracked_repo(
        tmp_path,
        {
            "modules/bin/warned": (
                "#!/usr/bin/env bash\n"
                "helper() {\n"
                "  local stamp=$(date)\n"
                "  printf '%s\\n' \"$stamp\"\n"
                "}\n"
                "helper\n"
            ),
        },
    )

    report = check_shell_files(repo_root)

    shellcheck_findings = [
        finding for finding in report.findings if finding.code == "shell.shellcheck"
    ]
    assert shellcheck_findings
    assert all(finding.severity is Severity.ERROR for finding in shellcheck_findings)
    assert any("SC2155" in finding.message for finding in shellcheck_findings)


@requires_zsh
def test_check_shell_files_checks_zsh_syntax(tmp_path: Path) -> None:
    repo_root = _tracked_repo(
        tmp_path,
        {
            "modules/zsh/broken.zsh": "if true; then\n",
        },
    )

    report = check_shell_files(repo_root)

    assert any(
        finding.code == "shell.zsh_syntax" and finding.severity is Severity.ERROR
        for finding in report.findings
    )


def test_check_shell_files_requires_missing_tools_explicitly(tmp_path: Path) -> None:
    repo_root = _tracked_repo(
        tmp_path,
        {"modules/bin/good": "#!/usr/bin/env bash\nprintf 'ok\\n'\n"},
    )

    with pytest.raises(ShellCheckError, match="shellcheck"):
        check_shell_files(
            repo_root,
            executable_finder=lambda name: (
                None if name == "shellcheck" else shutil.which(name)
            ),
        )


def test_check_shell_files_skips_zsh_loudly_when_zsh_is_absent(
    tmp_path: Path,
) -> None:
    repo_root = _tracked_repo(
        tmp_path,
        {
            "modules/zsh/env.zsh": "alias ok=true\n",
            "modules/bin/good": "#!/usr/bin/env bash\nprintf 'ok\\n'\n",
        },
    )
    quiet_shellcheck = tmp_path / "quiet-shellcheck"
    quiet_shellcheck.write_text("#!/bin/sh\nexit 0\n")
    quiet_shellcheck.chmod(0o755)

    def finder(name: str) -> str | None:
        if name == "zsh":
            return None
        if name == "shellcheck":
            return str(quiet_shellcheck)
        return shutil.which(name)

    report = check_shell_files(repo_root, executable_finder=finder)

    assert report.is_ok() is True
    skipped = [
        finding for finding in report.findings if finding.code == "shell.zsh_skipped"
    ]
    assert skipped
    assert skipped[0].severity is Severity.SKIPPED
    assert "zsh is not installed" in skipped[0].message
