import json
import os
from pathlib import Path

from tests.conftest import REPO_ROOT, run_scripts_module


def _write_mise(home: Path, log_path: Path, *, install_exit: int = 0) -> Path:
    executable = home / ".local/bin/mise"
    executable.parent.mkdir(parents=True)
    executable.write_text(
        "#!/bin/sh\n"
        f'printf \'%s|%s\\n\' "$*" "$PATH" >> {log_path}\n'
        'if [ "$1" = "install" ]; then\n'
        f"  exit {install_exit}\n"
        "fi\n"
        "exit 0\n",
    )
    executable.chmod(0o755)
    return executable


def _write_live_config(home: Path) -> None:
    config = home / ".config/mise"
    config.mkdir(parents=True)
    (config / "config.toml").write_text('[tools]\nnode = "20"\n')
    (config / "mise.lock").write_text("# host-specific lock\n")


def test_mise_sync_previews_configuration_tools_and_shims_without_writing(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _write_live_config(home)
    log_path = tmp_path / "mise.log"
    executable = _write_mise(home, log_path)

    completed = run_scripts_module("mise_sync", home, "--json")

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    assert document["schema_version"] == 1
    assert document["operation"] == "mise-sync"
    assert document["apply"] is False
    assert document["ok"] is True
    assert document["summary"] == {"planned": 4}
    assert [change["status"] for change in document["changes"]] == [
        "planned",
        "planned",
    ]
    assert [step["command"] for step in document["steps"]] == [
        [
            str(executable),
            "install",
            "--locked",
            "--yes",
            "-C",
            str(home),
        ],
        [str(executable), "reshim", "-C", str(home)],
    ]
    assert all(
        step["environment"]["PATH_prepend"] == [str(executable.parent)]
        for step in document["steps"]
    )
    assert document["next"] == ["mise run mise-sync -- --apply"]
    assert not log_path.exists()
    assert not (home / ".config/mise/config.toml").is_symlink()


def test_mise_sync_apply_links_shared_declaration_and_runs_locked_commands(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _write_live_config(home)
    log_path = tmp_path / "mise.log"
    executable = _write_mise(home, log_path)

    completed = run_scripts_module("mise_sync", home, "--apply", "--json")

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    assert document["apply"] is True
    assert document["ok"] is True
    assert document["summary"] == {"applied": 2, "succeeded": 2}
    config = home / ".config/mise/config.toml"
    lockfile = home / ".config/mise/mise.lock"
    assert config.is_symlink()
    assert config.resolve() == REPO_ROOT / "reference/.config/mise/config.toml"
    assert lockfile.is_symlink()
    assert lockfile.resolve() == REPO_ROOT / "reference/.config/mise/mise.lock"
    assert all(Path(change["backup_path"]).is_file() for change in document["changes"])
    invocations = log_path.read_text().splitlines()
    assert invocations[0].split("|", 1)[0] == (f"install --locked --yes -C {home}")
    assert invocations[1].split("|", 1)[0] == f"reshim -C {home}"
    assert all(
        line.split("|", 1)[1].split(os.pathsep)[0] == str(executable.parent)
        for line in invocations
    )
    assert document["next"] == ["mise run check", "mise run diff"]

    converged = run_scripts_module("mise_sync", home, "--apply", "--json")
    assert converged.returncode == 0
    converged_document = json.loads(converged.stdout)
    assert converged_document["changes"] == []
    assert converged_document["summary"] == {"succeeded": 2}


def test_mise_sync_fails_before_restore_without_canonical_mise(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _write_live_config(home)

    completed = run_scripts_module("mise_sync", home, "--apply", "--json")

    assert completed.returncode == 1
    document = json.loads(completed.stdout)
    assert document["ok"] is False
    assert document["apply"] is True
    assert document["steps"][0]["status"] == "failed"
    assert document["steps"][1]["status"] == "skipped"
    assert "missing, symlinked, or not executable" in document["steps"][0]["reason"]
    assert "[mise.tools] FAIL" in completed.stderr
    config = home / ".config/mise/config.toml"
    assert config.read_text() == '[tools]\nnode = "20"\n'
    assert not config.is_symlink()


def test_mise_sync_reports_install_failure_but_still_repairs_shims(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _write_live_config(home)
    log_path = tmp_path / "mise.log"
    _write_mise(home, log_path, install_exit=7)

    completed = run_scripts_module("mise_sync", home, "--apply", "--json")

    assert completed.returncode == 1
    document = json.loads(completed.stdout)
    assert document["ok"] is False
    assert [step["status"] for step in document["steps"]] == [
        "failed",
        "succeeded",
    ]
    assert [line.split("|", 1)[0] for line in log_path.read_text().splitlines()] == [
        f"install --locked --yes -C {home}",
        f"reshim -C {home}",
    ]
    assert "[mise.tools] FAIL command exited 7" in completed.stderr
