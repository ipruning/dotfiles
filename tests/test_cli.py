import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import scripts.diff as diff_module


def _run_module(
    module: str,
    home: Path,
    *arguments: str,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[1]
    active_environment = os.environ.copy()
    active_environment["HOME"] = str(home)
    if environment:
        active_environment.update(environment)
    return subprocess.run(
        [sys.executable, "-m", module, *arguments],
        cwd=repo_root,
        env=active_environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_mise_python_tasks_never_sync_dependencies_implicitly(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config = tomllib.loads((repo_root / "mise.toml").read_text())
    task_commands: list[str] = []
    for task in config["tasks"].values():
        run = task.get("run")
        commands = run if isinstance(run, list) else [run]
        task_commands.extend(
            command for command in commands if isinstance(command, str)
        )

    assert config["settings"]["auto_install"] is False
    assert config["settings"]["lockfile"] is True
    assert config["settings"]["lockfile_platforms"] == [
        "macos-arm64",
        "linux-x64",
    ]
    assert config["min_version"]["hard"] == "2026.7.12"
    assert config["tool_alias"] == {
        "fd": "aqua:sharkdp/fd",
        "jq": "aqua:jqlang/jq",
        "ripgrep": "aqua:BurntSushi/ripgrep",
        "shellcheck": "aqua:koalaman/shellcheck",
        "uv": "aqua:astral-sh/uv",
    }
    assert task_commands
    assert all("uv run " not in command for command in task_commands)
    assert "uv run" not in (repo_root / "scripts/zsh-profile").read_text()

    # Exercise a real preview task from a checkout without .venv. The task must
    # use the provisioned interpreter without creating project runtime state.
    project = tmp_path / "project"
    shutil.copytree(repo_root / "scripts", project / "scripts")
    bash_module = project / "modules/bash/init.bash"
    bash_module.parent.mkdir(parents=True)
    shutil.copy2(repo_root / "modules/bash/init.bash", bash_module)
    home = tmp_path / "home"
    home.mkdir()
    environment = os.environ.copy()
    environment.pop("VIRTUAL_ENV", None)
    environment["HOME"] = str(home)
    completed = subprocess.run(
        [
            "bash",
            "-c",
            config["tasks"]["setup"]["run"],
            "mise-task",
            "--profile",
            "linux-lite",
            "--json",
        ],
        cwd=project,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["apply"] is False
    assert not (project / ".venv").exists()
    assert not (project / "uv.lock").exists()


def test_global_mise_lock_covers_declared_artifact_platforms() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config = tomllib.loads(
        (repo_root / "reference/.config/mise/config.toml").read_text(),
    )
    lockfile = tomllib.loads(
        (repo_root / "reference/.config/mise/mise.lock").read_text(),
    )
    version_only_backends = {"core:rust"}
    version_only_prefixes = ("cargo:", "gem:", "go:", "npm:", "pipx:")
    missing: list[str] = []

    for tool in config["tools"]:
        entries = lockfile["tools"].get(tool)
        if not entries:
            missing.append(f"{tool}:lock-entry")
            continue
        for entry in entries:
            backend = entry["backend"]
            if backend in version_only_backends or backend.startswith(
                version_only_prefixes,
            ):
                continue
            for platform_name in config["settings"]["lockfile_platforms"]:
                platform = entry.get(f"platforms.{platform_name}", {})
                if not platform.get("url"):
                    missing.append(f"{tool}@{entry['version']}:{platform_name}")

    assert missing == []


def test_setup_cli_previews_linux_lite_as_json_without_writing(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    completed = _run_module(
        "scripts.setup",
        home,
        "--profile",
        "linux-lite",
        "--json",
    )
    document = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert document["schema_version"] == 1
    assert document["operation"] == "setup"
    assert document["ok"] is True
    assert document["profile"] == "linux-lite"
    assert document["apply"] is False
    assert document["summary"] == {"planned": 2}
    assert [change["status"] for change in document["changes"]] == [
        "planned",
        "planned",
    ]
    assert not (home / ".bashrc").exists()
    assert not (home / ".gitconfig").exists()


def test_check_cli_reports_optional_linux_lite_gaps_as_json(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tool_bin = home / ".local/bin"
    tool_bin.mkdir(parents=True)
    mise = tool_bin / "mise"
    mise.write_text("#!/bin/sh\nexit 0\n")
    mise.chmod(0o755)

    completed = _run_module(
        "scripts.check",
        home,
        "--profile",
        "linux-lite",
        "--json",
        environment={"PATH": f"{tool_bin}:/usr/bin:/bin"},
    )
    document = json.loads(completed.stdout)
    codes = {finding["code"] for finding in document["findings"]}

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert document["ok"] is True
    assert document["profile"] == "linux-lite"
    assert sum(document["summary"].values()) == len(document["findings"])
    assert "git.private_include_missing" in codes
    assert "skillshare.config_missing" in codes
    assert "shell.bash_missing" in codes
    assert "shell.repo_commands_isolated" in codes


def test_diff_cli_renders_profile_and_exit_status_at_the_mackup_boundary(
    monkeypatch,
    capsys,
) -> None:
    def inspect(
        _runner,
        _repo_root: Path,
        _home: Path,
        _application: str | None,
    ) -> dict[str, object]:
        return {
            "schema_version": 1,
            "operation": "diff",
            "changes": [],
            "summary": {},
        }

    monkeypatch.setattr(diff_module.SubprocessMackupRunner, "inspect", inspect)

    exit_code = diff_module.main(["--profile", "linux-lite", "--json"])
    captured = capsys.readouterr()
    document = json.loads(captured.out)

    assert exit_code == 0
    assert captured.err == ""
    assert document == {
        "changes": [],
        "ok": True,
        "operation": "diff",
        "profile": "linux-lite",
        "schema_version": 1,
        "summary": {},
    }
