import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.update import UpdateStatus, execute_updates, plan_updates


def _fake_tool(
    bin_dir: Path,
    name: str,
    log_path: Path,
    *,
    exit_code: int = 0,
    failure_output: bool = True,
    mise_inventory: str | None = None,
) -> None:
    tool_path = bin_dir / name
    inventory = ""
    if name == "mise":
        inventory_document = mise_inventory or json.dumps(
            {"python": [{"version": "3.14.6", "installed": True}]},
        )
        inventory = (
            'if [ "$1" = "ls" ]; then\n'
            f"  printf '%s\\n' {shlex.quote(inventory_document)}\n"
            "  exit 0\n"
            "fi\n"
        )
    failure = (
        (f"printf '%s\\n' 'simulated {name} failure' >&2\n" if failure_output else "")
        + f"exit {exit_code}\n"
        if exit_code
        else ""
    )
    tool_path.write_text(
        "#!/bin/sh\n"
        f"{inventory}"
        f"printf '%s\\n' \"{name} $*\" >> {shlex.quote(str(log_path))}\n"
        f"{failure}",
    )
    tool_path.chmod(0o755)


def _run_update(
    tmp_path: Path,
    *arguments: str,
    tools: tuple[str, ...] = ("brew", "mise", "amp"),
    failing_tool: str | None = None,
    failure_output: bool = True,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    log_path = tmp_path / "invocations.log"
    for name in tools:
        _fake_tool(
            bin_dir,
            name,
            log_path,
            exit_code=7 if name == failing_tool else 0,
            failure_output=failure_output,
        )
    environment = os.environ.copy()
    environment["HOME"] = str(tmp_path / "home")
    environment["PATH"] = str(bin_dir)
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.update", *arguments],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed, log_path


def test_update_previews_exact_plan_by_default_without_running_tools(
    tmp_path: Path,
) -> None:
    completed, log_path = _run_update(tmp_path, "--json")

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    assert document["schema_version"] == 1
    assert document["operation"] == "update"
    assert document["apply"] is False
    assert document["ok"] is True
    assert [
        (step["name"], step["status"], step["command"])
        for step in document["steps"]
        if step["status"] == "planned"
    ] == [
        ("brew.metadata", "planned", ["brew", "update"]),
        ("brew.packages", "planned", ["brew", "upgrade"]),
        (
            "mise.tools",
            "planned",
            [
                "mise",
                "upgrade",
                "--bump",
                "-C",
                str(tmp_path / "home"),
                "python@3.14.6",
            ],
        ),
        ("mise.shims", "planned", ["mise", "reshim"]),
        ("amp", "planned", ["amp", "update"]),
    ]
    assert document["summary"] == {"planned": 5, "skipped": 8}
    assert document["next"] == ["mise run update -- --apply"]
    assert not log_path.exists()


def test_update_gives_package_managers_transaction_scale_timeouts(
    tmp_path: Path,
) -> None:
    report = plan_updates(
        tmp_path / "home",
        executable_finder=lambda tool: f"/tools/{tool}",
    )
    steps = {result.step.name: result.step for result in report.results}

    assert steps["brew.packages"].timeout_seconds >= 3600
    assert steps["mise.tools"].timeout_seconds >= 1800


def test_update_installs_sprite_updates_instead_of_only_checking(
    tmp_path: Path,
) -> None:
    report = plan_updates(
        tmp_path / "home",
        executable_finder=lambda tool: "/tools/sprite" if tool == "sprite" else None,
    )

    sprite = next(
        result for result in report.results if result.step.name == "sprite.version"
    )

    assert sprite.step.command == ("sprite", "upgrade")


def test_update_runs_available_tools_in_order_and_reports_skips(tmp_path: Path) -> None:
    completed, log_path = _run_update(tmp_path, "--apply", "--json")

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    assert document["apply"] is True
    assert document["ok"] is True
    assert document["summary"] == {"skipped": 8, "succeeded": 5}
    assert [
        (step["name"], step["status"], step["exit_code"])
        for step in document["steps"]
        if step["status"] != "skipped"
    ] == [
        ("brew.metadata", "succeeded", 0),
        ("brew.packages", "succeeded", 0),
        ("mise.tools", "succeeded", 0),
        ("mise.shims", "succeeded", 0),
        ("amp", "succeeded", 0),
    ]
    assert log_path.read_text().splitlines() == [
        "brew update",
        "brew upgrade",
        f"mise upgrade --bump -C {tmp_path / 'home'} python@3.14.6",
        "mise reshim",
        "amp update",
    ]


def test_update_preview_human_output_points_to_apply(tmp_path: Path) -> None:
    completed, log_path = _run_update(tmp_path)

    assert completed.returncode == 0
    assert "PLANNED brew.metadata: brew update" in completed.stdout
    assert (
        "No commands run. Re-run with --apply to update host tools." in completed.stdout
    )
    assert "RUN " not in completed.stdout
    assert "Next:" not in completed.stdout
    assert not log_path.exists()


def test_update_human_output_announces_commands_before_summary(tmp_path: Path) -> None:
    completed, _log_path = _run_update(tmp_path, "--apply")

    assert completed.returncode == 0
    assert completed.stdout.splitlines()[0] == "RUN brew.metadata: brew update"
    assert "SUCCEEDED brew.metadata" in completed.stdout
    assert ("Next:\n  mise run runtime\n") in completed.stdout
    assert "Summary: 5 succeeded, 8 skipped" in completed.stdout


def test_update_failure_is_contextual_and_does_not_hide_later_results(
    tmp_path: Path,
) -> None:
    completed, log_path = _run_update(
        tmp_path,
        "--apply",
        "--json",
        tools=("amp", "tigris"),
        failing_tool="amp",
    )

    assert completed.returncode == 1
    document = json.loads(completed.stdout)
    assert document["ok"] is False
    results = {step["name"]: step for step in document["steps"]}
    assert results["amp"]["status"] == "failed"
    assert results["amp"]["exit_code"] == 7
    assert results["tigris"]["status"] == "succeeded"
    assert document["next"] == []
    assert log_path.read_text().splitlines() == ["amp update", "tigris update"]
    assert "[amp] simulated amp failure" in completed.stderr


def test_update_json_reports_a_quiet_command_failure_on_stderr(tmp_path: Path) -> None:
    completed, _log_path = _run_update(
        tmp_path,
        "--apply",
        "--json",
        tools=("amp",),
        failing_tool="amp",
        failure_output=False,
    )

    assert completed.returncode == 1
    assert json.loads(completed.stdout)["ok"] is False
    assert "[amp] FAIL command exited 7" in completed.stderr


def test_update_reports_timeout_and_launch_failures_on_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_with_timeout(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired(("amp", "update"), 300)

    monkeypatch.setattr("scripts.update.subprocess.run", fail_with_timeout)
    timeout_report = execute_updates(
        tmp_path,
        executable_finder=lambda tool: "/fake/amp" if tool == "amp" else None,
        capture_output=True,
    )

    timeout_result = next(
        result for result in timeout_report.results if result.step.name == "amp"
    )
    assert timeout_result.status is UpdateStatus.FAILED
    assert "[amp] FAIL timed out after 300s" in capsys.readouterr().err

    def fail_to_launch(*_args: object, **_kwargs: object) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr("scripts.update.subprocess.run", fail_to_launch)
    launch_report = execute_updates(
        tmp_path,
        executable_finder=lambda tool: "/fake/amp" if tool == "amp" else None,
        capture_output=True,
    )

    launch_result = next(
        result for result in launch_report.results if result.step.name == "amp"
    )
    assert launch_result.status is UpdateStatus.FAILED
    assert "[amp] FAIL permission denied" in capsys.readouterr().err


def test_update_mise_step_passes_only_installed_versions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inventory = json.dumps(
        {
            "python": [{"version": "3.14.6", "installed": True}],
            "github:larksuite/cli": [
                {"version": "1.0.72", "installed": True},
            ],
        },
    )

    def fake_run(
        command: tuple[str, ...],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        assert command[:4] == ("mise", "ls", "--current", "--installed")
        return subprocess.CompletedProcess(command, 0, inventory, "")

    monkeypatch.setattr("scripts.update.subprocess.run", fake_run)
    report = plan_updates(
        tmp_path,
        executable_finder=lambda tool: "/tools/mise" if tool == "mise" else None,
    )

    result = next(
        result for result in report.results if result.step.name == "mise.tools"
    )
    assert result.status is UpdateStatus.PLANNED
    assert result.step.command == (
        "mise",
        "upgrade",
        "--bump",
        "-C",
        str(tmp_path),
        "github:larksuite/cli@1.0.72",
        "python@3.14.6",
    )


def test_update_fails_closed_when_mise_inventory_is_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "scripts.update.subprocess.run",
        lambda command, **_kwargs: subprocess.CompletedProcess(
            command, 0, "not-json", ""
        ),
    )

    report = plan_updates(
        tmp_path,
        executable_finder=lambda tool: "/tools/mise" if tool == "mise" else None,
    )

    result = next(
        result for result in report.results if result.step.name == "mise.tools"
    )
    assert result.status is UpdateStatus.FAILED
    assert "invalid JSON" in (result.reason or "")
    assert report.ok is False


def test_update_apply_does_not_execute_a_failed_mise_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ran: list[tuple[str, ...]] = []

    def fake_run(command, **_kwargs):
        ran.append(tuple(command))
        if tuple(command[:2]) == ("mise", "ls"):
            return subprocess.CompletedProcess(command, 0, "not-json", "")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("scripts.update.subprocess.run", fake_run)

    report = execute_updates(
        tmp_path,
        executable_finder=lambda tool: "/tools/mise" if tool == "mise" else None,
    )

    mise_result = next(r for r in report.results if r.step.name == "mise.tools")
    assert mise_result.status is UpdateStatus.FAILED
    # A failed inventory must not fall through to `mise upgrade` with no tool
    # arguments, which would upgrade every installed tool.
    assert not any(cmd[:2] == ("mise", "upgrade") for cmd in ran)
    assert report.ok is False


def test_update_help_and_invalid_options_never_run_tools(tmp_path: Path) -> None:
    help_result, help_log = _run_update(tmp_path / "help", "--help")
    invalid_result, invalid_log = _run_update(tmp_path / "invalid", "--unknown")

    assert help_result.returncode == 0
    assert "--apply" in help_result.stdout
    assert "--json" in help_result.stdout
    assert not help_log.exists()
    assert invalid_result.returncode == 2
    assert "unrecognized arguments: --unknown" in invalid_result.stderr
    assert not invalid_log.exists()
