import json
import subprocess
from pathlib import Path

from scripts.doctor import DoctorStatus, inspect_doctor


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
        if command[0].endswith("skillshare"):
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps({"ok": True, "summary": {"warnings": 2}}),
                "",
            )
        if command[0].endswith("rotom"):
            return subprocess.CompletedProcess(
                command,
                1,
                json.dumps({"ok": False}),
                "codex configuration required",
            )
        return subprocess.CompletedProcess(command, 0, "healthy\n", "")

    report = inspect_doctor(
        home,
        executable_finder=lambda tool: f"/tools/{tool}",
        runner=runner,
    )

    results = {result.step.name: result for result in report.results}
    assert results["dotfiles.check"].status is DoctorStatus.WARN
    assert results["dotfiles.diff"].status is DoctorStatus.WARN
    assert results["mise.doctor"].status is DoctorStatus.PASS
    assert results["skillshare.doctor"].status is DoctorStatus.WARN
    assert results["rotom.status"].status is DoctorStatus.ERROR
    assert report.ok is False
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

    skipped = {
        result.step.name
        for result in report.results
        if result.status is DoctorStatus.SKIPPED
    }
    assert skipped == {
        "brew.doctor",
        "mise.doctor",
        "pueue.status",
        "rotom.status",
        "skillshare.doctor",
    }
    assert report.ok is True
