import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.shell import ShellCheckError, check_shell_files, classify

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


def test_classify_covers_extensions_shebangs_and_reference_data() -> None:
    assert classify("modules/bash/init.bash", "# sourced fragment") == "bash"
    assert classify("modules/bin/_lib/session-id.sh", "") == "bash"
    assert classify("modules/zsh/env.zsh", "") == "zsh"
    assert classify("modules/bin/g", "#!/usr/bin/env bash") == "bash"
    assert classify("modules/bin/ttok", "#!/usr/bin/env -S zsh -f") == "zsh"
    assert classify("modules/bin/watchdog", "#!/bin/sh") == "bash"
    assert classify("scripts/diff.py", "#!/usr/bin/env python3") is None
    assert classify("reference/.zshenv.private.tpl.zsh", "") is None
    assert classify("notes.txt", "plain text") is None
    assert classify("modules/tool/tool", "#!/bin/sh", '""":"') is None


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
    assert any(failure.startswith("bash syntax") for failure in failing)

    (repo_root / "modules/bin/broken").write_text(
        "#!/usr/bin/env bash\nif true; then\n  printf 'ok\\n'\nfi\n",
    )
    assert check_shell_files(repo_root, executable_finder=finder) == []


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

    failures = check_shell_files(repo_root)

    assert any(failure.startswith("shellcheck") for failure in failures)
    assert any("SC2155" in failure for failure in failures)


@requires_zsh
def test_check_shell_files_checks_zsh_syntax(tmp_path: Path) -> None:
    repo_root = _tracked_repo(
        tmp_path,
        {
            "modules/zsh/broken.zsh": "if true; then\n",
        },
    )

    failures = check_shell_files(repo_root)

    assert any(failure.startswith("zsh syntax") for failure in failures)


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
