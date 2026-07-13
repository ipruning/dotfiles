import os
import subprocess
from pathlib import Path

import pytest

from scripts.setup import SetupError, configure_linux_lite
from scripts.profiles import HostProfile


def test_linux_lite_setup_preserves_shell_config_and_is_idempotent(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    (repo_root / "modules/bash").mkdir(parents=True)
    (repo_root / "modules/bash/init.bash").write_text("export READY=1\n")
    home.mkdir()
    bashrc = home / ".bashrc"
    bashrc.write_text("# existing host setup\n")
    gitconfig = home / ".gitconfig"
    gitconfig.write_text("[init]\n\tdefaultBranch = main\n")

    preview = configure_linux_lite(repo_root, home, dry_run=True)

    assert preview.changed is True
    assert preview.profile is HostProfile.LINUX_LITE
    assert bashrc.read_text() == "# existing host setup\n"
    assert "include" not in gitconfig.read_text()

    first = configure_linux_lite(repo_root, home)
    second = configure_linux_lite(repo_root, home)

    assert first.changed is True
    assert second.changed is False
    assert bashrc.read_text().startswith("# >>> dotfiles linux-lite >>>\n")
    assert "# existing host setup\n" in bashrc.read_text()
    assert bashrc.read_text().count("# >>> dotfiles linux-lite >>>") == 1
    assert str(repo_root / "modules/bash/init.bash") in bashrc.read_text()
    assert "~/.private.gitconfig" in gitconfig.read_text()


def test_linux_lite_setup_rejects_incomplete_managed_block(tmp_path: Path) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    (repo_root / "modules/bash").mkdir(parents=True)
    (repo_root / "modules/bash/init.bash").write_text("export READY=1\n")
    home.mkdir()
    bashrc = home / ".bashrc"
    bashrc.write_text("# >>> dotfiles linux-lite >>>\n")

    with pytest.raises(SetupError, match="incomplete"):
        configure_linux_lite(repo_root, home)

    assert bashrc.read_text() == "# >>> dotfiles linux-lite >>>\n"


def test_linux_lite_setup_rejects_non_file_git_config_before_writing_bash(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    (repo_root / "modules/bash").mkdir(parents=True)
    (repo_root / "modules/bash/init.bash").write_text("export READY=1\n")
    home.mkdir()
    bashrc = home / ".bashrc"
    bashrc.write_text("# unchanged\n")
    (home / ".gitconfig").mkdir()

    with pytest.raises(SetupError, match="Git config"):
        configure_linux_lite(repo_root, home)

    assert bashrc.read_text() == "# unchanged\n"


def test_linux_lite_loader_runs_before_noninteractive_bash_return(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    (repo_root / "modules/bash").mkdir(parents=True)
    (repo_root / "modules/bash/init.bash").write_text("export DOTFILES_READY=1\n")
    home.mkdir()
    bashrc = home / ".bashrc"
    bashrc.write_text("case $- in *i*) ;; *) return;; esac\n")

    configure_linux_lite(repo_root, home)
    environment = {
        "BASH_ENV": str(bashrc),
        "HOME": str(home),
        "PATH": "/usr/bin:/bin",
    }
    completed = subprocess.run(
        ["bash", "-c", 'printf "%s" "$DOTFILES_READY"'],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout == "1"


def test_bash_module_exposes_repository_commands_without_duplicate_paths() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "modules/bash/init.bash"
    environment = os.environ.copy()
    environment["PATH"] = "/usr/bin:/bin"

    completed = subprocess.run(
        [
            "bash",
            "--noprofile",
            "--norc",
            "-c",
            f'. "{module_path}"; . "{module_path}"; command -v g; printf "%s" "$PATH"',
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    lines = completed.stdout.splitlines()
    assert lines[0] == str(repo_root / "modules/bin/g")
    assert lines[1].split(":").count(str(repo_root / "modules/bin")) == 1
