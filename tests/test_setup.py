import subprocess
import json
from pathlib import Path

import pytest

import scripts.setup as setup_script
from scripts.setup import SetupError, apply_setup, plan_setup
from scripts.profiles import HostProfile
from tests.conftest import run_scripts_module


def test_setup_json_exposes_apply_handoff_and_shell_restart(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    preview = run_scripts_module(
        "setup",
        home,
        "--profile",
        "linux-lite",
        "--json",
    )
    assert preview.returncode == 0
    preview_document = json.loads(preview.stdout)
    assert preview_document["apply"] is False
    assert preview_document["next"] == [
        "mise run setup -- --profile linux-lite --apply"
    ]
    assert preview_document["shell_restart_required"] is False

    applied = run_scripts_module(
        "setup",
        home,
        "--profile",
        "linux-lite",
        "--apply",
        "--json",
    )
    assert applied.returncode == 0
    applied_document = json.loads(applied.stdout)
    assert applied_document["apply"] is True
    assert applied_document["next"] == []
    assert applied_document["shell_restart_required"] is True


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

    preview = plan_setup(repo_root, home)

    assert preview.changed is True
    assert preview.profile is HostProfile.LINUX_LITE
    assert bashrc.read_text() == "# existing host setup\n"
    assert "include" not in gitconfig.read_text()

    first = apply_setup(repo_root, home)
    second = apply_setup(repo_root, home)

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
        apply_setup(repo_root, home)

    assert bashrc.read_text() == "# >>> dotfiles linux-lite >>>\n"


def test_linux_lite_setup_refuses_symlinked_bash_config(tmp_path: Path) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    (repo_root / "modules/bash").mkdir(parents=True)
    (repo_root / "modules/bash/init.bash").write_text("export READY=1\n")
    home.mkdir()
    external_target = tmp_path / "elsewhere/bashrc"
    external_target.parent.mkdir()
    external_target.write_text("# external content\n")
    bashrc = home / ".bashrc"
    bashrc.symlink_to(external_target)

    with pytest.raises(SetupError, match="symlink"):
        apply_setup(repo_root, home)

    assert external_target.read_text() == "# external content\n"

    external_target.unlink()
    with pytest.raises(SetupError, match="symlink"):
        apply_setup(repo_root, home)

    assert bashrc.is_symlink()
    assert not external_target.exists()


def test_linux_lite_setup_preserves_bash_config_permissions(tmp_path: Path) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    (repo_root / "modules/bash").mkdir(parents=True)
    (repo_root / "modules/bash/init.bash").write_text("export READY=1\n")
    home.mkdir()
    bashrc = home / ".bashrc"
    bashrc.write_text("# existing host setup\n")
    bashrc.chmod(0o600)
    (home / ".gitconfig").write_text("[init]\n\tdefaultBranch = main\n")

    apply_setup(repo_root, home)

    assert bashrc.stat().st_mode & 0o777 == 0o600
    assert "# existing host setup\n" in bashrc.read_text()
    assert not list(home.glob(".bashrc.*"))


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
        apply_setup(repo_root, home)

    assert bashrc.read_text() == "# unchanged\n"


def test_linux_lite_setup_preserves_bash_when_git_update_fails(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    (repo_root / "modules/bash").mkdir(parents=True)
    (repo_root / "modules/bash/init.bash").write_text("export READY=1\n")
    home.mkdir()
    bashrc = home / ".bashrc"
    bashrc.write_text("# unchanged\n")
    (home / ".gitconfig").write_text("[broken\n")

    with pytest.raises(SetupError):
        apply_setup(repo_root, home)

    assert bashrc.read_text() == "# unchanged\n"


def test_linux_lite_setup_rolls_back_git_when_bash_update_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    (repo_root / "modules/bash").mkdir(parents=True)
    (repo_root / "modules/bash/init.bash").write_text("export READY=1\n")
    home.mkdir()
    bashrc = home / ".bashrc"
    bashrc.write_text("# unchanged\n")
    gitconfig = home / ".gitconfig"
    original_gitconfig = "[init]\n\tdefaultBranch = main\n"
    gitconfig.write_text(original_gitconfig)

    def refuse_bash_update(_bashrc: Path, _content: str) -> None:
        raise OSError("disk refused write")

    monkeypatch.setattr(setup_script, "_write_bashrc", refuse_bash_update)

    with pytest.raises(SetupError, match="rolled back the Git include update"):
        apply_setup(repo_root, home)

    assert bashrc.read_text() == "# unchanged\n"
    assert gitconfig.read_text() == original_gitconfig


def test_linux_lite_setup_refuses_symlinked_git_config(tmp_path: Path) -> None:
    repo_root = tmp_path / "dotfiles"
    home = tmp_path / "home"
    (repo_root / "modules/bash").mkdir(parents=True)
    (repo_root / "modules/bash/init.bash").write_text("export READY=1\n")
    home.mkdir()
    external_target = tmp_path / "elsewhere/gitconfig"
    external_target.parent.mkdir()
    external_target.write_text("[init]\n\tdefaultBranch = main\n")
    (home / ".gitconfig").symlink_to(external_target)

    with pytest.raises(SetupError, match="Git config symlink"):
        apply_setup(repo_root, home)

    assert external_target.read_text() == "[init]\n\tdefaultBranch = main\n"


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

    apply_setup(repo_root, home)
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


def test_bash_module_exposes_only_user_and_mise_commands_without_duplicates(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "modules/bash/init.bash"
    home = tmp_path / "home"
    local_bin = home / ".local/bin"
    shims = home / ".local/share/mise/shims"
    system_bin = tmp_path / "system-bin"
    for directory in (local_bin, shims, system_bin):
        directory.mkdir(parents=True)
    for executable in (local_bin / "mise", shims / "uv", system_bin / "ss"):
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)

    environment = {
        "HOME": str(home),
        "PATH": f"{system_bin}:/usr/bin:/bin",
    }

    completed = subprocess.run(
        [
            "bash",
            "--noprofile",
            "--norc",
            "-c",
            f'. "{module_path}"; . "{module_path}"; '
            "command -v mise; command -v uv; command -v ss; "
            'command -v g || printf "g missing\\n"; printf "%s" "$PATH"',
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    lines = completed.stdout.splitlines()
    assert lines[:4] == [
        str(local_bin / "mise"),
        str(shims / "uv"),
        str(system_bin / "ss"),
        "g missing",
    ]
    loaded_path = lines[4].split(":")
    assert loaded_path.count(str(local_bin)) == 1
    assert loaded_path.count(str(shims)) == 1
    assert str(repo_root / "modules/bin") not in loaded_path
    assert str(repo_root / "generated/bin") not in loaded_path
