import json
import os
import subprocess
import sys
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


def test_setup_cli_previews_linux_lite_as_json_without_writing(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    completed = _run_module(
        "scripts.setup",
        home,
        "--profile",
        "linux-lite",
        "--dry-run",
        "--json",
    )
    document = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert document["profile"] == "linux-lite"
    assert document["dry_run"] is True
    assert document["changed"] is True
    assert not (home / ".bashrc").exists()
    assert not (home / ".gitconfig").exists()


def test_check_cli_reports_optional_linux_lite_gaps_as_json(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    tool_bin = tmp_path / "bin"
    tool_bin.mkdir()
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
        "operation": "diff",
        "profile": "linux-lite",
        "schema_version": 1,
        "summary": {},
    }
