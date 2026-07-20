import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# These tests induce a write failure by making a directory read-only. Root
# bypasses directory permission checks (CAP_DAC_OVERRIDE), so the failure path
# never triggers and the assertions are meaningless — skip them there.
skip_as_root = pytest.mark.skipif(
    os.geteuid() == 0,
    reason="permission-denied write failure cannot be induced as root",
)


def test_skillshare_source_uses_a_descriptive_non_system_command_name() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    executable = repo_root / "modules/bin/skillshare-source"

    assert executable.is_file()
    assert not (repo_root / "modules/bin/ss").exists()

    completed = subprocess.run(
        [str(executable), "--version"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout.strip() == "skillshare-source 0.2.0"


def test_zsh_profile_reports_invalid_input_without_optional_gum(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    executable = repo_root / "scripts/zsh-profile"
    tool_bin = tmp_path / "bin"
    tool_bin.mkdir()
    # Real bash and dirname serve the script preamble; the bare PATH keeps an
    # optional host gum from hijacking the plain-error output this test pins.
    import shutil as _shutil

    for real in ("bash", "dirname"):
        source = _shutil.which(real)
        assert source is not None
        (tool_bin / real).symlink_to(source)

    completed = subprocess.run(
        [str(executable), "invalid"],
        env={"HOME": str(tmp_path), "PATH": str(tool_bin)},
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert (
        completed.stderr.strip()
        == "error: runs must be a positive integer (got: invalid)"
    )


def test_zsh_profile_validates_arity_and_numeric_bounds_before_tools(
    tmp_path: Path,
) -> None:
    executable = Path(__file__).resolve().parents[1] / "scripts/zsh-profile"
    tool_bin = tmp_path / "bin"
    tool_bin.mkdir()
    import shutil as _shutil

    for real in ("bash", "dirname"):
        source = _shutil.which(real)
        assert source is not None
        (tool_bin / real).symlink_to(source)

    cases = [
        (["1", "2", "3"], 2, "Usage:"),
        (["0"], 1, "runs must be a positive integer"),
        (["1", "-1"], 1, "warmup must be a nonnegative integer"),
    ]
    for args, returncode, diagnostic in cases:
        completed = subprocess.run(
            [str(executable), *args],
            env={"HOME": str(tmp_path), "PATH": str(tool_bin)},
            capture_output=True,
            text=True,
        )
        assert completed.returncode == returncode
        assert completed.stdout == ""
        assert diagnostic in completed.stderr
        assert "Missing required" not in completed.stderr


def _write_executable(path: Path, contents: str) -> None:
    path.write_text(contents)
    path.chmod(0o755)


def test_pi_session_export_requires_an_explicit_command(tmp_path: Path) -> None:
    executable = (
        Path(__file__).resolve().parents[1] / "modules/bin/pi-session-export.py"
    )
    input_path = tmp_path / "session.jsonl"
    input_path.write_text("")

    completed = subprocess.run(
        [sys.executable, str(executable), str(input_path)],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "No such command" in completed.stderr
    assert "COMMAND [ARGS]" in completed.stderr


def test_watchdog_reports_probe_failure_as_unknown(tmp_path: Path) -> None:
    watchdog = (
        Path(__file__).resolve().parents[1] / "modules/bin/cursoruiviewservice-watchdog"
    )
    probe = tmp_path / "probe"
    for probe_output in ("probe-failed", "unexpected-output"):
        _write_executable(probe, f"#!/bin/sh\necho {probe_output}\n")
        completed = subprocess.run(
            [str(watchdog)],
            env={**os.environ, "WATCHDOG_OSASCRIPT": str(probe)},
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 1
        assert completed.stdout == ""
        assert "accessibility probe failed" in completed.stderr
        assert "not hung" not in completed.stderr


def test_watchdog_does_not_claim_termination_when_pid_remains(tmp_path: Path) -> None:
    watchdog = (
        Path(__file__).resolve().parents[1] / "modules/bin/cursoruiviewservice-watchdog"
    )
    probe, pgrep, kill, sleep = (
        tmp_path / name for name in ("probe", "pgrep", "kill", "sleep")
    )
    _write_executable(probe, "#!/bin/sh\necho true\n")
    _write_executable(pgrep, "#!/bin/sh\necho 123\n")
    _write_executable(kill, "#!/bin/sh\nexit 0\n")
    _write_executable(sleep, "#!/bin/sh\nexit 0\n")
    completed = subprocess.run(
        [str(watchdog)],
        env={
            **os.environ,
            "WATCHDOG_OSASCRIPT": str(probe),
            "WATCHDOG_PGREP": str(pgrep),
            "WATCHDOG_KILL": str(kill),
            "WATCHDOG_SLEEP": str(sleep),
        },
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert "remains after KILL" in completed.stderr
    assert "is terminated" not in completed.stdout


def test_watchdog_rejects_extra_arguments_before_probing(tmp_path: Path) -> None:
    watchdog = (
        Path(__file__).resolve().parents[1] / "modules/bin/cursoruiviewservice-watchdog"
    )
    probe = tmp_path / "probe"
    probe_log = tmp_path / "probe.log"
    _write_executable(probe, f"#!/bin/sh\ntouch '{probe_log}'\necho false\n")

    completed = subprocess.run(
        [str(watchdog), "first", "second"],
        env={**os.environ, "WATCHDOG_OSASCRIPT": str(probe)},
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "Usage:" in completed.stderr
    assert not probe_log.exists()


@skip_as_root
def test_skillshare_exec_restore_failure_overrides_child_success(
    tmp_path: Path,
) -> None:
    executable = Path(__file__).resolve().parents[1] / "modules/bin/skillshare-source"
    config_dir = tmp_path / "skillshare"
    config_dir.mkdir()
    config = config_dir / "config.yaml"
    original = tmp_path / "original"
    temporary = tmp_path / "temporary"
    config.write_text(f"source: {original}\n")
    (config_dir / "sources.json").write_text(json.dumps({"temporary": str(temporary)}))
    tool_bin = tmp_path / "bin"
    tool_bin.mkdir()
    _write_executable(
        tool_bin / "skillshare",
        f'#!/bin/sh\nprintf \'%s\\n\' \'{{"source":{{"path":"{original}"}}}}\'\n',
    )
    child = tmp_path / "child"
    _write_executable(child, f"#!/bin/sh\nchmod 555 '{config_dir}'\nexit 0\n")
    try:
        completed = subprocess.run(
            [str(executable), "exec", "temporary", "--", str(child)],
            env={
                **os.environ,
                "PATH": f"{tool_bin}:{os.environ['PATH']}",
                "SKILLSHARE_CONFIG": str(config),
            },
            capture_output=True,
            text=True,
        )
    finally:
        config_dir.chmod(0o755)
    assert completed.returncode != 0
    assert "Failed to restore source" in completed.stderr
    assert "Restore manually by editing" in completed.stderr


def test_skillshare_exec_requires_a_command_before_switching_source(
    tmp_path: Path,
) -> None:
    executable = Path(__file__).resolve().parents[1] / "modules/bin/skillshare-source"
    config_dir = tmp_path / "skillshare"
    config_dir.mkdir()
    config = config_dir / "config.yaml"
    config.write_text("source: /original\n")
    (config_dir / "sources.json").write_text(json.dumps({"temporary": "/temporary"}))

    completed = subprocess.run(
        [str(executable), "exec", "temporary", "--"],
        env={**os.environ, "SKILLSHARE_CONFIG": str(config)},
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "Missing argument 'CMD...'" in completed.stderr
    assert config.read_text() == "source: /original\n"


@skip_as_root
def test_skillshare_exec_switch_failure_preserves_config(tmp_path: Path) -> None:
    executable = Path(__file__).resolve().parents[1] / "modules/bin/skillshare-source"
    config_dir = tmp_path / "skillshare"
    config_dir.mkdir()
    config = config_dir / "config.yaml"
    original = tmp_path / "original"
    original_contents = f"source: {original}\nother: retained\n"
    config.write_text(original_contents)
    (config_dir / "sources.json").write_text(json.dumps({"temporary": "/temporary"}))
    tool_bin = tmp_path / "bin"
    tool_bin.mkdir()
    _write_executable(
        tool_bin / "skillshare",
        f'#!/bin/sh\nprintf \'%s\\n\' \'{{"source":{{"path":"{original}"}}}}\'\n',
    )

    config_dir.chmod(0o555)
    try:
        completed = subprocess.run(
            [str(executable), "exec", "temporary", "--", "true"],
            env={
                **os.environ,
                "PATH": f"{tool_bin}:{os.environ['PATH']}",
                "SKILLSHARE_CONFIG": str(config),
            },
            capture_output=True,
            text=True,
        )
    finally:
        config_dir.chmod(0o755)

    assert completed.returncode == 1
    assert "Failed to switch source" in completed.stderr
    assert "Traceback" not in completed.stderr
    assert config.read_text() == original_contents
    assert not list(config_dir.glob(".config.yaml.*"))


def test_skillshare_exec_preserves_symlinked_config(tmp_path: Path) -> None:
    executable = Path(__file__).resolve().parents[1] / "modules/bin/skillshare-source"
    config_dir = tmp_path / "skillshare"
    config_dir.mkdir()
    actual_config = tmp_path / "shared/config.yaml"
    actual_config.parent.mkdir()
    original = "/original"
    actual_config.write_text(f"source: {original}\nother: retained\n")
    config = config_dir / "config.yaml"
    config.symlink_to(actual_config)
    (config_dir / "sources.json").write_text(json.dumps({"temporary": "/temporary"}))
    tool_bin = tmp_path / "bin"
    tool_bin.mkdir()
    _write_executable(
        tool_bin / "skillshare",
        f'#!/bin/sh\nprintf \'%s\\n\' \'{{"source":{{"path":"{original}"}}}}\'\n',
    )

    completed = subprocess.run(
        [str(executable), "exec", "temporary", "--", "true"],
        env={
            **os.environ,
            "PATH": f"{tool_bin}:{os.environ['PATH']}",
            "SKILLSHARE_CONFIG": str(config),
        },
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert config.is_symlink()
    assert actual_config.read_text() == f"source: {original}\nother: retained\n"


def test_skillshare_add_preserves_symlinked_sources_registry(tmp_path: Path) -> None:
    executable = Path(__file__).resolve().parents[1] / "modules/bin/skillshare-source"
    config_dir = tmp_path / "skillshare"
    config_dir.mkdir()
    config = config_dir / "config.yaml"
    config.write_text("source: /original\n")
    actual_registry = tmp_path / "shared/sources.json"
    actual_registry.parent.mkdir()
    actual_registry.write_text(json.dumps({"original": "/original"}))
    registry = config_dir / "sources.json"
    registry.symlink_to(actual_registry)
    added_source = tmp_path / "added"
    added_source.mkdir()

    completed = subprocess.run(
        [str(executable), "add", "added", str(added_source)],
        env={**os.environ, "SKILLSHARE_CONFIG": str(config)},
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert registry.is_symlink()
    assert json.loads(actual_registry.read_text()) == {
        "original": "/original",
        "added": str(added_source),
    }
