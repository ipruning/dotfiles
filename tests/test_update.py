import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from scripts.process import run_process_group
from scripts.update import (
    UpdateStatus,
    UpdateStep,
    _run_with_progress,
    execute_updates,
    plan_updates,
)

# These integration tests run alongside the other verify tasks. Give the helper
# process time to spawn its child before testing the updater's timeout behavior.
PROCESS_GROUP_TEST_TIMEOUT_SECONDS = 5


def _fake_tool(
    bin_dir: Path,
    name: str,
    log_path: Path,
    *,
    exit_code: int = 0,
    failure_output: bool = True,
    mise_inventory: str | None = None,
    delay_seconds: float = 0,
) -> None:
    native_dir = {
        "amp": ".amp/bin",
        "claude": ".local/share/claude/versions",
        "pi": ".pi/agent/install",
        "sprite": ".local/bin",
        "tigris": ".local/bin",
    }
    if name in native_dir:
        home = bin_dir.parent / "home"
        target_dir = home / native_dir[name]
        target_dir.mkdir(parents=True, exist_ok=True)
        if bin_dir != target_dir:
            (bin_dir / name).symlink_to(target_dir / name)
        bin_dir = target_dir
    tool_path = bin_dir / name
    inventory = ""
    if name == "mise":
        inventory_document = mise_inventory or json.dumps(
            {"python": [{"version": "3.14.6", "installed": True}]},
        )
        config = tool_path.parents[2] / ".config/mise/config.toml"
        config.parent.mkdir(parents=True, exist_ok=True)
        source = (
            Path(__file__).resolve().parents[1] / "reference/.config/mise/config.toml"
        )
        if not config.exists():
            shutil.copy2(source, config)
        shutil.copy2(source.with_name("mise.lock"), config.with_name("mise.lock"))
        inventory = (
            'if [ "$1" = "config" ]; then\n'
            f"  printf '%s\\n' {shlex.quote(json.dumps([{'path': str(config), 'tools': []}]))}\n"
            "  exit 0\n"
            "fi\n"
            'if [ "$1" = "activate" ] || [ "$1" = "completion" ]; then\n'
            "  printf '# shell runtime\\n'\n"
            "  exit 0\n"
            "fi\n"
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
    delay = f"/bin/sleep {delay_seconds}\n" if delay_seconds else ""
    tool_path.write_text(
        "#!/bin/sh\n"
        f"{inventory}"
        f"printf '%s\\n' \"{name} $*\" >> {shlex.quote(str(log_path))}\n"
        f"{delay}"
        f"{failure}",
    )
    tool_path.chmod(0o755)


def _run_update(
    tmp_path: Path,
    *arguments: str,
    tools: tuple[str, ...] = ("brew", "mise", "amp"),
    failing_tool: str | None = None,
    failure_output: bool = True,
    mise_inventory: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir()
    log_path = tmp_path / "invocations.log"
    for name in tools:
        tool_dir = home / ".local/bin" if name == "mise" else bin_dir
        tool_dir.mkdir(parents=True, exist_ok=True)
        _fake_tool(
            tool_dir,
            name,
            log_path,
            exit_code=7 if name == failing_tool else 0,
            failure_output=failure_output,
            mise_inventory=mise_inventory if name == "mise" else None,
        )
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    environment["PATH"] = os.pathsep.join((str(bin_dir), str(home / ".local/bin")))
    project = tmp_path / "project"
    source_root = Path(__file__).resolve().parents[1]
    shutil.copytree(source_root / "scripts", project / "scripts")
    shutil.copytree(
        source_root / "reference/.config/mise", project / "reference/.config/mise"
    )
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.update", *arguments],
        cwd=project,
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
            "mise.self",
            "planned",
            [
                str(tmp_path / "home/.local/bin/mise"),
                "self-update",
                "--yes",
                "--no-plugins",
            ],
        ),
        (
            "mise.tools",
            "planned",
            [
                str(tmp_path / "home/.local/bin/mise"),
                "install",
                "--locked",
                "--yes",
                "-C",
                str(tmp_path / "home"),
                "python",
            ],
        ),
        (
            "mise.shims",
            "planned",
            [
                str(tmp_path / "home/.local/bin/mise"),
                "reshim",
                "-C",
                str(tmp_path / "home"),
            ],
        ),
        ("amp", "planned", [str(tmp_path / "bin/amp"), "update"]),
    ]
    assert document["summary"] == {"planned": 6, "skipped": 8}
    assert document["notes"] == [
        (
            "planned means the updater command is available; each updater "
            "determines whether an update exists during apply."
        ),
        (
            "mise.tools consumes the shared lock without changing declarations; "
            "use upgrade-tools explicitly to advance the shared baseline."
        ),
    ]
    assert document["next"] == ["mise run update -- --apply"]
    steps = {step["name"]: step for step in document["steps"]}
    expected_mise_path = [str(tmp_path / "home/.local/bin")]
    assert steps["mise.self"]["environment"]["PATH_prepend"] == expected_mise_path
    assert steps["mise.tools"]["environment"]["PATH_prepend"] == expected_mise_path
    assert steps["mise.shims"]["environment"]["PATH_prepend"] == expected_mise_path
    assert steps["brew.metadata"]["environment"]["PATH_prepend"] == []
    assert steps["brew.metadata"]["environment"]["variables"] == {}
    assert steps["brew.packages"]["environment"]["variables"] == {
        "HOMEBREW_NO_INSTALL_CLEANUP": "1",
    }
    assert steps["sprite.version"]["stdin"] == "y\n"
    assert steps["tigris"]["attention"] is None
    assert not log_path.exists()


def test_update_preview_treats_tigris_like_other_updaters(tmp_path: Path) -> None:
    completed, _log_path = _run_update(
        tmp_path,
        "--json",
        tools=("tigris",),
    )

    document = json.loads(completed.stdout)
    tigris = next(step for step in document["steps"] if step["name"] == "tigris")
    assert tigris["status"] == "planned"
    assert tigris["attention"] is None


def test_update_previews_pi_self_and_extensions_without_running_either(
    tmp_path: Path,
) -> None:
    completed, log_path = _run_update(tmp_path, "--json", tools=("pi",))

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    assert [
        (step["name"], step["command"])
        for step in document["steps"]
        if step["status"] == "planned"
    ] == [
        ("pi", [str(tmp_path / "bin/pi"), "update"]),
        ("pi.extensions", [str(tmp_path / "bin/pi"), "update", "--extensions"]),
    ]
    assert not log_path.exists()


def test_update_runs_pi_extensions_even_after_self_update_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "pi.log"
    pi = tmp_path / "home/.pi/agent/install/pi"
    pi.parent.mkdir(parents=True)
    (bin_dir / "pi").symlink_to(pi)
    pi.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"pi $*\" >> {shlex.quote(str(log_path))}\n"
        'if [ "$#" -eq 1 ]; then exit 7; fi\n'
        "exit 0\n",
    )
    pi.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))

    report = execute_updates(
        tmp_path / "home",
        capture_output=True,
    )

    assert report.ok is False
    assert [
        (result.step.name, result.status, result.exit_code)
        for result in report.results
        if result.status is not UpdateStatus.SKIPPED
    ] == [
        ("pi", UpdateStatus.FAILED, 7),
        ("pi.extensions", UpdateStatus.SUCCEEDED, 0),
    ]
    assert log_path.read_text().splitlines() == ["pi update", "pi update --extensions"]


def test_update_gives_package_managers_transaction_scale_timeouts(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    mise_bin = home / ".local/bin"
    mise_bin.mkdir(parents=True)
    _fake_tool(mise_bin, "mise", tmp_path / "mise.log")
    report = plan_updates(
        home,
        executable_finder=lambda tool: f"/tools/{tool}",
    )
    steps = {result.step.name: result.step for result in report.results}

    assert steps["brew.packages"].timeout_seconds >= 3600
    assert steps["mise.tools"].timeout_seconds >= 1800
    assert steps["claude"].timeout_seconds >= 1800
    assert steps["pi"].timeout_seconds >= 1800


def test_update_leaves_host_selected_mise_self_update_to_its_owner(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    mise = tmp_path / "system/bin/mise"
    mise.parent.mkdir(parents=True)
    mise.write_text("#!/bin/sh\nexit 0\n")
    mise.chmod(0o755)
    policy = home / ".config/dotfiles/policy.toml"
    policy.parent.mkdir(parents=True)
    policy.write_text(f'mode = "managed"\nmise_path = "{mise}"\n')

    report = plan_updates(
        home,
        executable_finder=lambda tool: str(mise) if tool == "mise" else None,
    )
    results = {result.step.name: result for result in report.results}

    assert results["mise.self"].status is UpdateStatus.SKIPPED
    assert results["mise.self"].reason == (
        "host-selected mise is updated by its host owner"
    )


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
    assert sprite.step.stdin_text == "y\n"


@pytest.mark.parametrize("capture_output", [False, True])
def test_update_confirms_sprite_in_noninteractive_apply(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capture_output: bool,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    result_path = tmp_path / "sprite-result"
    sprite = home / ".local/bin/sprite"
    sprite.parent.mkdir(parents=True)
    sprite.write_text(
        "#!/bin/sh\n"
        'if IFS= read -r answer && [ "$answer" = y ]; then\n'
        f"  printf upgraded > {shlex.quote(str(result_path))}\n"
        "else\n"
        f"  printf cancelled > {shlex.quote(str(result_path))}\n"
        "fi\n"
    )
    sprite.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))

    report = execute_updates(
        home,
        executable_finder=lambda tool: str(sprite) if tool == "sprite" else None,
        capture_output=capture_output,
        progress_interval_seconds=1,
    )

    sprite_result = next(
        result for result in report.results if result.step.name == "sprite.version"
    )
    assert sprite_result.status is UpdateStatus.SUCCEEDED
    assert result_path.read_text() == "upgraded"


def test_update_disables_homebrew_automatic_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    log_path = tmp_path / "brew.log"
    brew = bin_dir / "brew"
    brew.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = upgrade ]; then\n'
        '  printf "%s\\n" "$HOMEBREW_NO_INSTALL_CLEANUP" '
        f"> {shlex.quote(str(log_path))}\n"
        "fi\n"
    )
    brew.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))

    report = execute_updates(
        home,
        executable_finder=lambda tool: str(brew) if tool == "brew" else None,
    )

    assert report.ok is True
    assert log_path.read_text().strip() == "1"


def test_update_reports_claude_failure_recovery_without_cleaning(
    tmp_path: Path,
) -> None:
    completed, _log_path = _run_update(
        tmp_path,
        "--apply",
        "--json",
        tools=("claude",),
        failing_tool="claude",
    )

    assert completed.returncode == 1
    document = json.loads(completed.stdout)
    claude = next(step for step in document["steps"] if step["name"] == "claude")
    assert claude["status"] == "failed"
    assert "retry `claude update`" in claude["reason"]
    assert ".cache/claude/staging" in claude["reason"]
    assert "not cleaned automatically" in claude["reason"]


def test_update_runs_available_tools_in_order_and_reports_skips(tmp_path: Path) -> None:
    completed, log_path = _run_update(tmp_path, "--apply", "--json")

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    assert document["apply"] is True
    assert document["ok"] is True
    assert document["summary"] == {"skipped": 8, "succeeded": 6}
    assert [
        (step["name"], step["status"], step["exit_code"])
        for step in document["steps"]
        if step["status"] != "skipped"
    ] == [
        ("brew.metadata", "succeeded", 0),
        ("brew.packages", "succeeded", 0),
        ("mise.self", "succeeded", 0),
        ("mise.tools", "succeeded", 0),
        ("mise.shims", "succeeded", 0),
        ("amp", "succeeded", 0),
    ]
    assert log_path.read_text().splitlines() == [
        "brew update",
        "brew upgrade",
        "mise self-update --yes --no-plugins",
        f"mise install --locked --yes -C {tmp_path / 'home'} python",
        f"mise reshim -C {tmp_path / 'home'}",
        "amp update",
    ]


def test_update_executes_reshim_with_canonical_mise_first_on_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    canonical = home / ".local/bin/mise"
    canonical.parent.mkdir(parents=True)
    _fake_tool(canonical.parent, "mise", tmp_path / "mise.log")
    observed_path = ""

    def fake_inventory(command, **_kwargs):
        assert tuple(command[:2]) == (str(canonical), "ls")
        return subprocess.CompletedProcess(command, 0, "{}", "")

    def fake_run(step, **kwargs):
        nonlocal observed_path
        if step.command == (str(canonical), "reshim", "-C", str(home)):
            observed_path = kwargs["env"]["PATH"]
        return subprocess.CompletedProcess(step.command, 0, "", "")

    monkeypatch.setattr("scripts.update.run_process_group", fake_inventory)
    monkeypatch.setattr("scripts.update._run_with_progress", fake_run)

    report = execute_updates(
        home,
        executable_finder=lambda tool: str(canonical) if tool == "mise" else None,
    )

    assert report.ok is True
    assert observed_path.split(os.pathsep, maxsplit=1)[0] == str(canonical.parent)


def test_update_preview_human_output_points_to_apply(tmp_path: Path) -> None:
    completed, log_path = _run_update(tmp_path)

    assert completed.returncode == 0
    assert "PLANNED brew.metadata: cd -- " in completed.stdout
    assert " && brew update" in completed.stdout
    assert (
        "No commands run. Re-run with --apply to update host tools." in completed.stdout
    )
    assert "RUN " not in completed.stdout
    assert "Next:" not in completed.stdout
    assert not log_path.exists()


def test_update_human_output_announces_commands_before_summary(tmp_path: Path) -> None:
    completed, _log_path = _run_update(tmp_path, "--apply")

    assert completed.returncode == 0
    assert completed.stdout.splitlines()[0].startswith("RUN brew.metadata: cd -- ")
    assert completed.stdout.splitlines()[0].endswith(" && brew update")
    assert "SUCCEEDED brew.metadata" in completed.stdout
    assert ("Next:\n  mise run check\n") in completed.stdout
    assert "Summary: 6 succeeded, 8 skipped" in completed.stdout


@pytest.mark.parametrize("capture_output", [False, True])
def test_update_streams_progress_to_stderr(
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    capture_output: bool,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    log_path = tmp_path / "invocations.log"
    _fake_tool(bin_dir, "amp", log_path, delay_seconds=0.08)
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("HOME", str(home))

    report = execute_updates(
        home,
        executable_finder=lambda tool: str(bin_dir / "amp") if tool == "amp" else None,
        capture_output=capture_output,
        progress_interval_seconds=0.02,
    )

    assert report.ok is True
    assert log_path.read_text().splitlines() == ["amp update"]
    output = capfd.readouterr()
    assert output.out == ""
    assert f"[amp] RUN cd -- {home} && {bin_dir / 'amp'} update" in output.err
    assert "[amp] STILL RUNNING" in output.err
    assert "[amp] DONE exit=0" in output.err


def test_update_progress_timeout_kills_the_process_group(tmp_path: Path) -> None:
    child_pid_path = tmp_path / "child.pid"
    tool_path = tmp_path / "timeout-tool"
    tool_path.write_text(
        "#!/bin/sh\n"
        "/bin/sleep 30 &\n"
        f"printf '%s\\n' $! > {shlex.quote(str(child_pid_path))}\n"
        "wait\n"
    )
    tool_path.chmod(0o755)

    with pytest.raises(subprocess.TimeoutExpired):
        _run_with_progress(
            UpdateStep(
                "timeout",
                "timeout",
                (str(tool_path),),
                PROCESS_GROUP_TEST_TIMEOUT_SECONDS,
            ),
            env=None,
            progress_interval_seconds=1,
        )

    child_pid = int(child_pid_path.read_text())
    deadline = time.monotonic() + 1
    while True:
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        if time.monotonic() >= deadline:
            pytest.fail(f"child process {child_pid} survived the updater timeout")
        time.sleep(0.01)


def test_update_human_runner_timeout_kills_the_process_group(tmp_path: Path) -> None:
    child_pid_path = tmp_path / "human-child.pid"
    tool_path = tmp_path / "human-timeout-tool"
    tool_path.write_text(
        "#!/bin/sh\n"
        "/bin/sleep 30 &\n"
        f"printf '%s\\n' $! > {shlex.quote(str(child_pid_path))}\n"
        "wait\n"
    )
    tool_path.chmod(0o755)

    with pytest.raises(subprocess.TimeoutExpired):
        run_process_group(
            (str(tool_path),),
            env=None,
            timeout_seconds=PROCESS_GROUP_TEST_TIMEOUT_SECONDS,
        )

    child_pid = int(child_pid_path.read_text())
    deadline = time.monotonic() + 1
    while True:
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            break
        if time.monotonic() >= deadline:
            pytest.fail(f"child process {child_pid} survived the updater timeout")
        time.sleep(0.01)


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
    assert document["next"] == [
        "mise run check",
    ]
    assert log_path.read_text().splitlines() == ["amp update", "tigris update"]
    assert "[amp] FAIL command exited 7" in completed.stderr


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

    monkeypatch.setattr("scripts.update._run_with_progress", fail_with_timeout)
    timeout_report = execute_updates(
        tmp_path,
        executable_finder=lambda tool: (
            str(tmp_path / ".amp/bin/amp") if tool == "amp" else None
        ),
        capture_output=True,
    )

    timeout_result = next(
        result for result in timeout_report.results if result.step.name == "amp"
    )
    assert timeout_result.status is UpdateStatus.FAILED
    assert "[amp] FAIL timed out after 300s" in capsys.readouterr().err

    def fail_to_launch(*_args: object, **_kwargs: object) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr("scripts.update._run_with_progress", fail_to_launch)
    launch_report = execute_updates(
        tmp_path,
        executable_finder=lambda tool: (
            str(tmp_path / ".amp/bin/amp") if tool == "amp" else None
        ),
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
    mise = tmp_path / ".local/bin/mise"
    mise.parent.mkdir(parents=True)
    _fake_tool(mise.parent, "mise", tmp_path / "mise.log")
    inventory = json.dumps(
        {
            "python": [{"version": "3.14.6", "installed": True}],
            "cargo:https://github.com/ipruning/atuin": [
                {
                    "version": "rev:f12a28548ad2189de3a06be547999493f1614a78",
                    "installed": True,
                },
            ],
            "github:larksuite/cli": [
                {"version": "1.0.72", "installed": True},
            ],
        },
    )

    def fake_run(
        command: tuple[str, ...],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        assert command[:3] == (
            str(mise),
            "ls",
            "--installed",
        )
        return subprocess.CompletedProcess(command, 0, inventory, "")

    monkeypatch.setattr("scripts.update.run_process_group", fake_run)
    report = plan_updates(
        tmp_path,
        executable_finder=lambda tool: "/tools/mise" if tool == "mise" else None,
    )

    result = next(
        result for result in report.results if result.step.name == "mise.tools"
    )
    assert result.status is UpdateStatus.PLANNED
    assert result.step.command == (
        str(mise),
        "install",
        "--locked",
        "--yes",
        "-C",
        str(tmp_path),
        "cargo:https://github.com/ipruning/atuin",
        "github:larksuite/cli",
        "python",
    )


def test_update_fails_closed_when_mise_inventory_is_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mise = tmp_path / ".local/bin/mise"
    mise.parent.mkdir(parents=True)
    mise.write_text("#!/bin/sh\nexit 0\n")
    mise.chmod(0o755)
    monkeypatch.setattr(
        "scripts.update.run_process_group",
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
    mise = tmp_path / ".local/bin/mise"
    mise.parent.mkdir(parents=True)
    mise.write_text("#!/bin/sh\nexit 0\n")
    mise.chmod(0o755)
    ran: list[tuple[str, ...]] = []

    def fake_run(command, **_kwargs):
        ran.append(tuple(command))
        if tuple(command[:2]) == (str(mise), "ls"):
            return subprocess.CompletedProcess(command, 0, "not-json", "")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("scripts.update.run_process_group", fake_run)

    report = execute_updates(
        tmp_path,
        executable_finder=lambda tool: "/tools/mise" if tool == "mise" else None,
    )

    mise_result = next(r for r in report.results if r.step.name == "mise.tools")
    assert mise_result.status is UpdateStatus.FAILED
    # A failed inventory must not fall through to `mise upgrade` with no tool
    # arguments, which would upgrade every installed tool.
    assert not any(cmd[:2] == (str(mise), "upgrade") for cmd in ran)
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


def test_update_skips_mise_owned_native_self_update(tmp_path: Path) -> None:
    home = tmp_path / "home"
    pi = home / ".local/share/mise/installs/pi/1.0/bin/pi"
    pi.parent.mkdir(parents=True)
    pi.write_text("#!/bin/sh\nexit 0\n")
    pi.chmod(0o755)
    report = plan_updates(
        home, executable_finder=lambda tool: str(pi) if tool == "pi" else None
    )
    results = {result.step.name: result for result in report.results}
    assert results["pi"].status is UpdateStatus.SKIPPED
    assert "package-manager owned" in (results["pi"].reason or "")
    assert results["pi.extensions"].status is UpdateStatus.PLANNED


def test_update_keeps_unknown_native_owner_read_only(tmp_path: Path) -> None:
    report = plan_updates(
        tmp_path,
        executable_finder=lambda tool: (
            "/usr/local/bin/tigris" if tool == "tigris" else None
        ),
    )
    result = next(result for result in report.results if result.step.name == "tigris")
    assert result.status is UpdateStatus.SKIPPED
    assert "no verified native owner" in (result.reason or "")


def test_update_cli_refreshes_runtime_after_independent_failure(tmp_path: Path) -> None:
    completed, log = _run_update(
        tmp_path, "--apply", "--json", tools=("amp", "mise"), failing_tool="amp"
    )
    document = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert document["runtime"]["apply"] is True
    assert document["runtime"]["ok"] is True
    assert any(
        step["name"] == "amp" and step["status"] == "failed"
        for step in document["steps"]
    )
    assert "amp update" in log.read_text()
    assert (tmp_path / "project/generated/functions/_mise.zsh").is_file()


def _run_upgrade(tmp_path: Path, *arguments: str, linked: bool = True):
    source_root = Path(__file__).resolve().parents[1]
    project = tmp_path / "project"
    shutil.copytree(source_root / "scripts", project / "scripts")
    source = project / "reference/.config/mise/config.toml"
    source.parent.mkdir(parents=True)
    shutil.copy2(
        source_root / "reference/.config/mise/mise.lock", source.with_name("mise.lock")
    )
    source.write_text(
        '[tools]\npython = "latest"\n"cargo:https://github.com/ipruning/atuin" = { version = "rev:abc" }\n'
    )
    home = tmp_path / "home"
    binary = home / ".local/bin"
    binary.mkdir(parents=True)
    log = tmp_path / "upgrade.log"
    _fake_tool(binary, "mise", log)
    live = home / ".config/mise/config.toml"
    live.unlink()
    if linked:
        live.symlink_to(source)
    else:
        shutil.copy2(source, live)
    env = os.environ.copy()
    env.update(HOME=str(home), PATH=str(binary))
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.upgrade_tools", *arguments],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed, log


def test_upgrade_tools_cli_previews_shared_scope_without_updating(
    tmp_path: Path,
) -> None:
    completed, log = _run_upgrade(tmp_path, "--json")
    assert completed.returncode == 0, completed.stderr
    document = json.loads(completed.stdout)
    assert document["operation"] == "upgrade-tools"
    assert document["apply"] is False
    assert document["steps"][0]["command"][1:] == [
        "upgrade",
        "--bump",
        "--no-prune",
        "-C",
        str(tmp_path / "home"),
        "python@latest",
    ]
    assert not log.exists()


def test_upgrade_tools_cli_requires_shared_config_link(tmp_path: Path) -> None:
    completed, log = _run_upgrade(tmp_path, "--apply", "--json", linked=False)
    assert completed.returncode == 1
    document = json.loads(completed.stdout)
    assert document["steps"][0]["status"] == "failed"
    assert "must link" in document["steps"][0]["reason"]
    assert not log.exists()


def test_upgrade_tools_cli_updates_only_installed_shared_tools(tmp_path: Path) -> None:
    completed, log = _run_upgrade(tmp_path, "--apply", "--json")
    assert completed.returncode == 0, completed.stderr
    document = json.loads(completed.stdout)
    assert document["apply"] is True
    assert document["ok"] is True
    assert log.read_text().splitlines() == [
        f"mise upgrade --bump --no-prune -C {tmp_path / 'home'} python@latest"
    ]


def test_upgrade_tools_audit_only_keeps_preview_read_only(tmp_path: Path) -> None:
    completed, _ = _run_upgrade(tmp_path, "--json")
    home = tmp_path / "home"
    policy = home / ".config/dotfiles/policy.toml"
    policy.parent.mkdir(parents=True)
    policy.write_text('mode = "audit-only"\n')
    env = os.environ.copy()
    env.update(HOME=str(home), PATH=str(home / ".local/bin"))
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.upgrade_tools", "--apply", "--json"],
        cwd=tmp_path / "project",
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    document = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert document["error"]["code"] == "host_policy.audit_only"
    assert not (tmp_path / "upgrade.log").exists()


def test_failed_report_retry_preserves_quoted_arguments_cwd_and_input(
    tmp_path: Path,
) -> None:
    from scripts.update import UpdateReport, UpdateResult, _document

    working = tmp_path / "working space's"
    working.mkdir()
    literal = "literal $HOME $(touch unexpected)"
    step = UpdateStep(
        "fixture",
        "python",
        (
            sys.executable,
            "-c",
            "import json,os,sys; print(json.dumps([os.getcwd(),os.getenv('FIXTURE'),sys.argv[1],sys.stdin.read()]))",
            literal,
        ),
        10,
        cwd=working,
        environment=(("FIXTURE", "value with spaces"),),
        stdin_text="line one\nline two\n",
    )
    report = UpdateReport(True, (UpdateResult(step, UpdateStatus.FAILED, exit_code=7),))
    retry = json.loads(json.dumps(_document(report)))["steps"][0]["retry"]
    completed = subprocess.run(
        retry,
        shell=True,
        executable="/bin/sh",
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert json.loads(completed.stdout) == [
        str(working),
        "value with spaces",
        literal,
        "line one\nline two\n",
    ]
    assert not (working / "unexpected").exists()


def test_update_cli_installs_locked_target_when_only_older_version_is_installed(
    tmp_path: Path,
) -> None:
    inventory = json.dumps({
        "herdr": [{"version": "0.9.1", "installed": True, "active": False}],
        "unowned-tool": [{"version": "1.0", "installed": True, "active": False}],
    })
    completed, log = _run_update(
        tmp_path, "--json", tools=("mise",), mise_inventory=inventory
    )
    assert completed.returncode == 0, completed.stderr
    binary = tmp_path / "home/.local/bin/mise"
    binary.write_text(
        binary.read_text().replace(
            'if [ "$1" = "ls" ]; then\n',
            'if [ "$1" = "ls" ]; then\n'
            '  case " $* " in *" --current "*) printf "{}\\n"; exit 0 ;; esac\n',
        )
    )
    lock = tmp_path / "home/.config/mise/mise.lock"
    before = lock.read_bytes()
    env = os.environ.copy()
    env.update(HOME=str(tmp_path / "home"), PATH=str(binary.parent))
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.update", "--apply", "--json"],
        cwd=tmp_path / "project",
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    document = json.loads(completed.stdout)
    step = next(step for step in document["steps"] if step["name"] == "mise.tools")
    assert step["status"] == "succeeded"
    assert step["command"][1:] == [
        "install",
        "--locked",
        "--yes",
        "-C",
        str(tmp_path / "home"),
        "herdr",
    ]
    assert (
        f"mise install --locked --yes -C {tmp_path / 'home'} herdr"
        in log.read_text().splitlines()
    )
    assert lock.read_bytes() == before
