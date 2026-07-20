import json
import os
import shlex
import stat
import subprocess
import sys
from pathlib import Path
from typing import NotRequired, TypedDict

import pytest

from scripts.inventory import (
    InventoryStatus,
    execute_inventory,
    plan_inventory,
    sanitize_host,
)

BREWFILE = 'tap "acme/tap"\nbrew "fd"\ncask "ghostty"\n'
GH_EXTENSIONS = "gh poi\tseachicken/gh-poi\tv0.18.1\ngh dash\tdlvhdr/gh-dash\tv4.25.2\n"


class FakeToolOptions(TypedDict):
    stdout: NotRequired[str]
    stderr: NotRequired[str]
    exit_code: NotRequired[int]


def _fake_tool(
    bin_dir: Path,
    name: str,
    log_path: Path,
    *,
    stdout: str = "",
    stderr: str = "",
    exit_code: int = 0,
) -> None:
    tool_path = bin_dir / name
    lines = [
        "#!/bin/sh",
        f"printf '%s\\n' \"{name} $*\" >> {shlex.quote(str(log_path))}",
    ]
    if stdout:
        lines.append(f"printf '%s' {shlex.quote(stdout)}")
    if stderr:
        lines.append(f"printf '%s' {shlex.quote(stderr)} >&2")
    lines.append(f"exit {exit_code}")
    tool_path.write_text("\n".join(lines) + "\n")
    tool_path.chmod(0o755)


def _make_applications(
    root: Path, *, apps: tuple[str, ...], setapp: tuple[str, ...] | None
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name in apps:
        (root / f"{name}.app").mkdir()
    if setapp is not None:
        setapp_dir = root / "Setapp"
        setapp_dir.mkdir()
        for name in setapp:
            (setapp_dir / f"{name}.app").mkdir()


def _run_inventory(
    tmp_path: Path,
    *arguments: str,
    tools: dict[str, FakeToolOptions] | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    repo_root = tmp_path / "dotfiles"
    repo_root.mkdir(exist_ok=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    log_path = tmp_path / "invocations.log"
    defaults: dict[str, FakeToolOptions] = {
        "brew": {"stdout": BREWFILE},
        "gh": {"stdout": GH_EXTENSIONS},
    }
    for name, options in (tools if tools is not None else defaults).items():
        _fake_tool(bin_dir, name, log_path, **options)
    environment = os.environ.copy()
    environment["PATH"] = str(bin_dir)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.inventory",
            "--repo-root",
            str(repo_root),
            "--host",
            "TestHost",
            "--applications-root",
            str(tmp_path / "Applications"),
            *arguments,
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed, repo_root / "inventory/TestHost", log_path


def test_inventory_previews_exact_plan_by_default_without_collecting(
    tmp_path: Path,
) -> None:
    _make_applications(
        tmp_path / "Applications", apps=("Ghostty",), setapp=("TablePlus",)
    )

    completed, host_dir, log_path = _run_inventory(tmp_path, "--json")

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    assert document["schema_version"] == 1
    assert document["operation"] == "inventory"
    assert document["host"] == "TestHost"
    assert document["apply"] is False
    assert document["ok"] is True
    assert [
        (step["name"], step["status"], step["target"]) for step in document["steps"]
    ] == [
        ("brew.bundle", "planned", "inventory/TestHost/Brewfile"),
        ("gh.extensions", "planned", "inventory/TestHost/gh_extensions.txt"),
        ("applications", "planned", "inventory/TestHost/applications.txt"),
        ("setapp", "planned", "inventory/TestHost/setapp.txt"),
    ]
    assert document["summary"] == {"planned": 4}
    assert document["next"] == ["mise run inventory -- --apply"]
    assert not host_dir.exists()
    assert not log_path.exists()


def test_inventory_writes_sorted_snapshots_then_reports_unchanged(
    tmp_path: Path,
) -> None:
    _make_applications(
        tmp_path / "Applications",
        apps=("beta", "Alpha"),
        setapp=("TablePlus", "CleanShot X"),
    )

    first, host_dir, _log_path = _run_inventory(tmp_path, "--apply", "--json")

    assert first.returncode == 0
    assert (host_dir / "Brewfile").read_text() == BREWFILE
    assert (host_dir / "gh_extensions.txt").read_text() == (
        "dlvhdr/gh-dash\nseachicken/gh-poi\n"
    )
    assert (host_dir / "applications.txt").read_text() == "Alpha\nbeta\n"
    assert (host_dir / "setapp.txt").read_text() == "CleanShot X\nTablePlus\n"
    assert stat.S_IMODE((host_dir / "Brewfile").stat().st_mode) == 0o644
    assert all(
        step["status"] == "written" for step in json.loads(first.stdout)["steps"]
    )

    second, _host_dir, _log_path = _run_inventory(tmp_path, "--apply", "--json")

    assert second.returncode == 0
    second_document = json.loads(second.stdout)
    assert all(step["status"] == "unchanged" for step in second_document["steps"])
    assert second_document["next"] == []


def test_inventory_skips_missing_collectors_without_touching_snapshots(
    tmp_path: Path,
) -> None:
    _make_applications(tmp_path / "Applications", apps=("Ghostty",), setapp=None)
    repo_root = tmp_path / "dotfiles"
    host_dir = repo_root / "inventory/TestHost"
    host_dir.mkdir(parents=True)
    (host_dir / "gh_extensions.txt").write_text("old/extension\n")
    (host_dir / "setapp.txt").write_text("Old App\n")

    completed, host_dir, _log_path = _run_inventory(
        tmp_path, "--apply", "--json", tools={"brew": {"stdout": BREWFILE}}
    )

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    steps = {step["name"]: step for step in document["steps"]}
    assert steps["gh.extensions"]["status"] == "skipped"
    assert "gh is not available on PATH" in steps["gh.extensions"]["reason"]
    assert steps["setapp"]["status"] == "skipped"
    assert steps["brew.bundle"]["status"] == "written"
    assert (host_dir / "gh_extensions.txt").read_text() == "old/extension\n"
    assert (host_dir / "setapp.txt").read_text() == "Old App\n"


def test_inventory_failure_keeps_existing_snapshot_and_later_steps_run(
    tmp_path: Path,
) -> None:
    _make_applications(tmp_path / "Applications", apps=("Ghostty",), setapp=())
    repo_root = tmp_path / "dotfiles"
    host_dir = repo_root / "inventory/TestHost"
    host_dir.mkdir(parents=True)
    (host_dir / "Brewfile").write_text('brew "previous"\n')

    completed, host_dir, _log_path = _run_inventory(
        tmp_path,
        "--apply",
        "--json",
        tools={
            "brew": {"stderr": "simulated brew failure\n", "exit_code": 7},
            "gh": {"stdout": GH_EXTENSIONS},
        },
    )

    assert completed.returncode == 1
    document = json.loads(completed.stdout)
    assert document["ok"] is False
    steps = {step["name"]: step for step in document["steps"]}
    assert steps["brew.bundle"]["status"] == "failed"
    assert steps["brew.bundle"]["reason"] == "command exited 7"
    assert steps["brew.bundle"]["exit_code"] == 7
    assert steps["gh.extensions"]["status"] == "written"
    assert steps["applications"]["status"] == "written"
    assert (host_dir / "Brewfile").read_text() == 'brew "previous"\n'
    assert "[brew.bundle] simulated brew failure" in completed.stderr
    assert "[brew.bundle] FAIL command exited 7" in completed.stderr


def test_inventory_empty_collector_output_fails_and_keeps_snapshot(
    tmp_path: Path,
) -> None:
    _make_applications(tmp_path / "Applications", apps=("Ghostty",), setapp=None)
    repo_root = tmp_path / "dotfiles"
    host_dir = repo_root / "inventory/TestHost"
    host_dir.mkdir(parents=True)
    (host_dir / "Brewfile").write_text('brew "old"\n')

    completed, host_dir, _log_path = _run_inventory(
        tmp_path,
        "--apply",
        "--json",
        tools={"brew": {"stdout": ""}, "gh": {"stdout": GH_EXTENSIONS}},
    )

    assert completed.returncode == 1
    steps = {step["name"]: step for step in json.loads(completed.stdout)["steps"]}
    assert steps["brew.bundle"]["status"] == "failed"
    assert "empty output" in steps["brew.bundle"]["reason"]
    assert (host_dir / "Brewfile").read_text() == 'brew "old"\n'


def test_inventory_zero_gh_extensions_is_a_legitimate_snapshot(
    tmp_path: Path,
) -> None:
    _make_applications(tmp_path / "Applications", apps=("Ghostty",), setapp=None)
    repo_root = tmp_path / "dotfiles"
    host_dir = repo_root / "inventory/TestHost"
    host_dir.mkdir(parents=True)
    (host_dir / "gh_extensions.txt").write_text("old/extension\n")

    completed, host_dir, _log_path = _run_inventory(
        tmp_path,
        "--apply",
        "--json",
        tools={"brew": {"stdout": BREWFILE}, "gh": {"stdout": ""}},
    )

    assert completed.returncode == 0
    steps = {step["name"]: step for step in json.loads(completed.stdout)["steps"]}
    assert steps["gh.extensions"]["status"] == "written"
    assert (host_dir / "gh_extensions.txt").read_text() == ""


def test_inventory_failing_gh_with_empty_output_still_fails(
    tmp_path: Path,
) -> None:
    _make_applications(tmp_path / "Applications", apps=("Ghostty",), setapp=None)
    repo_root = tmp_path / "dotfiles"
    host_dir = repo_root / "inventory/TestHost"
    host_dir.mkdir(parents=True)
    (host_dir / "gh_extensions.txt").write_text("old/extension\n")

    completed, host_dir, _log_path = _run_inventory(
        tmp_path,
        "--apply",
        "--json",
        tools={"brew": {"stdout": BREWFILE}, "gh": {"stdout": "", "exit_code": 4}},
    )

    assert completed.returncode == 1
    steps = {step["name"]: step for step in json.loads(completed.stdout)["steps"]}
    assert steps["gh.extensions"]["status"] == "failed"
    assert "exited 4" in steps["gh.extensions"]["reason"]
    assert (host_dir / "gh_extensions.txt").read_text() == "old/extension\n"


def test_inventory_failed_atomic_publish_keeps_previous_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    applications_root = tmp_path / "Applications"
    _make_applications(applications_root, apps=("Ghostty",), setapp=None)
    repo_root = tmp_path / "dotfiles"
    target = repo_root / "inventory/TestHost/applications.txt"
    target.parent.mkdir(parents=True)
    target.write_text("Previous App\n")
    plan = plan_inventory(
        repo_root,
        "TestHost",
        applications_root=applications_root,
        executable_finder=lambda _tool: None,
    )
    original_replace = Path.replace

    def fail_publish(source: Path, destination: Path) -> Path:
        if destination == target and source.name.startswith(f".{target.name}.tmp-"):
            raise OSError("injected snapshot publish failure")
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "replace", fail_publish)
    report = execute_inventory(plan)

    application = next(
        result for result in report.results if result.spec.name == "applications"
    )
    assert application.status is InventoryStatus.FAILED
    assert target.read_text() == "Previous App\n"
    assert not list(target.parent.glob(f".{target.name}.tmp-*"))


def test_inventory_rejects_unparseable_gh_output_without_writing(
    tmp_path: Path,
) -> None:
    _make_applications(tmp_path / "Applications", apps=("Ghostty",), setapp=None)

    completed, host_dir, _log_path = _run_inventory(
        tmp_path,
        "--apply",
        "--json",
        tools={
            "brew": {"stdout": BREWFILE},
            "gh": {"stdout": "not a tab separated line\n"},
        },
    )

    assert completed.returncode == 1
    steps = {step["name"]: step for step in json.loads(completed.stdout)["steps"]}
    assert steps["gh.extensions"]["status"] == "failed"
    assert steps["gh.extensions"]["exit_code"] == 0
    assert "unrecognized gh extension list line" in steps["gh.extensions"]["reason"]
    assert not (host_dir / "gh_extensions.txt").exists()


def test_inventory_rejects_traversal_and_separator_hosts(tmp_path: Path) -> None:
    for bad_host in ("..", "a/b"):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.inventory",
                "--repo-root",
                str(tmp_path / "dotfiles"),
                "--host",
                bad_host,
            ],
            cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "PATH": str(tmp_path)},
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 2
        assert "--host must use only" in completed.stderr
    assert not (tmp_path / "dotfiles").exists()


def test_inventory_sanitizes_detected_hostnames() -> None:
    assert sanitize_host("MacBook-Pro-M5-Pro") == "MacBook-Pro-M5-Pro"
    assert sanitize_host("Alex's Mac") == "Alex-s-Mac"
    assert sanitize_host("..") == "unknown-host"
    assert sanitize_host("") == "unknown-host"


def test_inventory_human_output_announces_collectors_and_summary(
    tmp_path: Path,
) -> None:
    _make_applications(tmp_path / "Applications", apps=("Ghostty",), setapp=None)

    completed, _host_dir, _log_path = _run_inventory(tmp_path, "--apply")

    assert completed.returncode == 0
    assert completed.stdout.splitlines()[0] == (
        "RUN brew.bundle: brew bundle dump --file=- --quiet"
    )
    assert "WRITTEN brew.bundle: inventory/TestHost/Brewfile" in completed.stdout
    assert "SKIPPED setapp:" in completed.stdout
    assert "Summary: 3 written, 1 skipped" in completed.stdout
    assert "Next:\n  git diff inventory/\n" in completed.stdout


def test_inventory_reports_timeout_on_stderr_and_keeps_going(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_with_timeout(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired(("brew",), 300)

    monkeypatch.setattr("scripts.inventory.subprocess.run", fail_with_timeout)
    applications_root = tmp_path / "Applications"
    _make_applications(applications_root, apps=("Ghostty",), setapp=None)
    plan = plan_inventory(
        tmp_path / "dotfiles",
        "TestHost",
        applications_root=applications_root,
        executable_finder=lambda tool: f"/fake/{tool}",
    )

    report = execute_inventory(plan)

    results = {result.spec.name: result for result in report.results}
    assert results["brew.bundle"].status is InventoryStatus.FAILED
    assert results["applications"].status is InventoryStatus.WRITTEN
    assert "[brew.bundle] FAIL timed out after 300s" in capsys.readouterr().err


def test_inventory_help_and_invalid_options_never_collect(tmp_path: Path) -> None:
    help_result, _host_dir, help_log = _run_inventory(tmp_path, "--help")
    invalid_result, _host_dir, invalid_log = _run_inventory(tmp_path, "--unknown")

    assert help_result.returncode == 0
    assert "--apply" in help_result.stdout
    assert "--json" in help_result.stdout
    assert not help_log.exists()
    assert invalid_result.returncode == 2
    assert "unrecognized arguments: --unknown" in invalid_result.stderr
    assert not invalid_log.exists()
