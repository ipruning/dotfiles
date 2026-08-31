import json
import subprocess
from pathlib import Path

import pytest

import scripts.clean as clean_module
from scripts.clean import CleanStatus, execute_clean, plan_clean
from scripts.host_policy import HostPolicyMutationError


def _write_mise(home: Path) -> Path:
    executable = home / ".local/bin/mise"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    return executable


def test_clean_preview_runs_only_read_only_commands(tmp_path: Path) -> None:
    home = tmp_path / "home"
    mise = _write_mise(home)
    calls: list[tuple[str, ...]] = []

    def runner(
        command: tuple[str, ...],
        _environment: dict[str, str],
        _timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "nothing to remove\n", "")

    report = plan_clean(
        home,
        executable_finder=lambda tool: f"/tools/{tool}",
        runner=runner,
    )

    assert report.apply is False
    assert [result.status for result in report.results] == [
        CleanStatus.PREVIEWED,
        CleanStatus.PREVIEWED,
        CleanStatus.PREVIEWED,
    ]
    assert calls == [
        (str(mise), "prune", "--dry-run", "--tools"),
        ("/tools/brew", "autoremove", "--dry-run"),
        ("/tools/brew", "cleanup", "--dry-run"),
    ]


def test_clean_apply_uses_owner_commands_and_policy_guard(tmp_path: Path) -> None:
    home = tmp_path / "home"
    mise = _write_mise(home)
    calls: list[tuple[str, ...]] = []

    def runner(
        command: tuple[str, ...],
        _environment: dict[str, str],
        _timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    report = execute_clean(
        home,
        executable_finder=lambda tool: f"/tools/{tool}",
        runner=runner,
    )

    assert report.apply is True
    assert [result.status for result in report.results] == [
        CleanStatus.SUCCEEDED,
        CleanStatus.SUCCEEDED,
        CleanStatus.SUCCEEDED,
    ]
    assert calls == [
        (str(mise), "prune", "--yes", "--tools"),
        ("/tools/brew", "autoremove"),
        ("/tools/brew", "cleanup"),
    ]

    policy = home / ".config/dotfiles/policy.toml"
    policy.parent.mkdir(parents=True)
    policy.write_text('mode = "audit-only"\n')
    with pytest.raises(HostPolicyMutationError):
        execute_clean(home, executable_finder=lambda _tool: None, runner=runner)


def test_clean_cli_json_keeps_stdout_machine_readable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(clean_module.Path, "home", staticmethod(lambda: home))
    monkeypatch.setattr(
        clean_module,
        "plan_clean",
        lambda _home: clean_module.CleanReport(False, ()),
    )

    assert clean_module.main(["--json"]) == 0
    document = json.loads(capsys.readouterr().out)
    assert document["operation"] == "clean"
    assert document["apply"] is False
    assert document["ok"] is True
