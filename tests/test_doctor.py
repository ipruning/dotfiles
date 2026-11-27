import json
import subprocess
from pathlib import Path

import pytest

from scripts.doctor import inspect_doctor
from scripts.models import Severity


def _write_mise(home: Path) -> Path:
    executable = home / ".local/bin/mise"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    return executable


def test_doctor_aggregates_internal_and_external_checks_without_mutation(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    mise = _write_mise(home)
    calls: list[tuple[str, ...]] = []

    def runner(
        command: tuple[str, ...],
        _environment: dict[str, str],
        _timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if "-m" in command:
            module = command[command.index("-m") + 1]
            reports = {
                "scripts.check": {"ok": True, "summary": {"warn": 1}},
                "scripts.diff": {
                    "ok": True,
                    "changes": [{"kind": "modified"}],
                    "summary": {"modified": 1},
                },
                "scripts.mise_sync": {"ok": True, "summary": {}},
                "scripts.lint": {"ok": True, "summary": {"warn": 0}},
            }
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps(reports[module]),
                "",
            )
        if command[0] == str(mise):
            return subprocess.CompletedProcess(command, 0, "No problems found\n", "")
        if command[0].endswith("/jh"):
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps({
                    "ok": True,
                    "data": {"logged_in": True, "refresh_valid": True},
                }),
                "",
            )
        if command[0].endswith("skillshare"):
            raise AssertionError(
                "Skillshare diagnostics must not run during inspection"
            )
        return subprocess.CompletedProcess(command, 0, "healthy\n", "")

    report = inspect_doctor(
        home,
        executable_finder=lambda tool: f"/tools/{tool}",
        runner=runner,
    )

    results = {result.step.name: result for result in report.results}
    assert results["dotfiles.check"].severity is Severity.WARN
    assert results["dotfiles.diff"].severity is Severity.WARN
    assert results["mise.doctor"].severity is Severity.OK
    assert results["gh.auth"].severity is Severity.OK
    assert results["jh.auth"].severity is Severity.OK
    assert report.ok is True
    assert [
        command[command.index("-m") + 1] for command in calls if "-m" in command
    ] == [
        "scripts.check",
        "scripts.diff",
        "scripts.mise_sync",
        "scripts.lint",
    ]


def test_doctor_skips_unavailable_external_owners(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    def runner(
        command: tuple[str, ...],
        _environment: dict[str, str],
        _timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps({"ok": True, "summary": {}}),
            "",
        )

    report = inspect_doctor(home, executable_finder=lambda _tool: None, runner=runner)

    skipped = {result.step.name for result in report.results if result.severity is None}
    assert skipped == {
        "brew.doctor",
        "gh.auth",
        "jh.auth",
        "mise.doctor",
        "pueue.status",
    }
    assert report.ok is True


def test_doctor_flags_expired_gh_jh_and_static_mise_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("MISE_GITHUB_TOKEN", "synthetic-stale-token")

    def runner(
        command: tuple[str, ...],
        _environment: dict[str, str],
        _timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        if "-m" in command:
            return subprocess.CompletedProcess(
                command, 0, json.dumps({"ok": True, "summary": {}}), ""
            )
        if command[0].endswith("/gh"):
            return subprocess.CompletedProcess(
                command, 1, "", "HTTP 401: Bad credentials\n"
            )
        if command[0].endswith("/jh"):
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps({
                    "ok": True,
                    "data": {"logged_in": True, "refresh_valid": False},
                }),
                "",
            )
        return subprocess.CompletedProcess(command, 0, "ok\n", "")

    report = inspect_doctor(
        home,
        executable_finder=lambda tool: (
            f"/tools/{tool}" if tool in {"gh", "jh"} else None
        ),
        runner=runner,
    )
    results = {result.step.name: result for result in report.results}
    assert results["gh.auth"].severity is Severity.ERROR
    assert results["jh.auth"].severity is Severity.WARN
    assert results["env.mise-github-token"].severity is Severity.WARN
    assert report.ok is False
