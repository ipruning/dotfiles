"""真实子进程验证维护命令的输出、超时和进度边界。"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from scripts.process import run_process_group


def test_failure_keeps_bounded_diagnostics_without_polluting_stdout(
    capfd: pytest.CaptureFixture[str],
) -> None:
    result = run_process_group(
        (
            sys.executable,
            "-c",
            (
                "import sys; print('x' * 200000 + 'END'); "
                "print('failure details', file=sys.stderr); sys.exit(7)"
            ),
        ),
        timeout_seconds=5,
        capture_output=True,
        output_limit_chars=128,
    )
    assert result.returncode == 7
    assert result.stdout is not None
    assert len(result.stdout) == 128
    assert result.stdout.endswith("END\n")
    assert result.stderr == "failure details\n"
    assert capfd.readouterr().out == ""


def test_generator_keeps_complete_stdout_and_accepts_stdin() -> None:
    result = run_process_group(
        (sys.executable, "-c", "import sys; sys.stdout.write(sys.stdin.read())"),
        timeout_seconds=5,
        capture_output=True,
        stdin_text="中" * 100000,
    )
    assert result.returncode == 0
    assert result.stdout == "中" * 100000


def test_progress_and_live_output(
    capfd: pytest.CaptureFixture[str],
) -> None:
    progress: list[float] = []
    result = run_process_group(
        (
            sys.executable,
            "-c",
            "import time; print('ready', flush=True); time.sleep(.2)",
        ),
        timeout_seconds=5,
        capture_output=True,
        output_limit_chars=100,
        inherit_output=True,
        on_progress=progress.append,
        progress_interval_seconds=0.02,
    )
    assert result.returncode == 0
    assert progress
    assert progress == sorted(progress)
    assert capfd.readouterr().out == "ready\n"
    assert result.stdout == "ready\n"


def test_timeout_keeps_diagnostics_and_covers_blocked_stdin() -> None:
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired) as failure:
        run_process_group(
            (
                sys.executable,
                "-c",
                "import time; print('waiting', flush=True); time.sleep(30)",
            ),
            timeout_seconds=0.3,
            capture_output=True,
            stdin_text="x" * 1000000,
            output_limit_chars=100,
        )
    assert time.monotonic() - started < 3
    assert failure.value.output == "waiting\n"


def test_timeout_does_not_wait_for_escaped_child_pipe(tmp_path: Path) -> None:
    pid_path = tmp_path / "child.pid"
    child_code = (
        "import os,time,pathlib; "
        f"pathlib.Path({str(pid_path)!r}).write_text(str(os.getpid())); time.sleep(30)"
    )
    parent_code = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}], start_new_session=True); "
        "time.sleep(.1)"
    )
    started = time.monotonic()
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            run_process_group(
                (sys.executable, "-c", parent_code),
                timeout_seconds=0.5,
                capture_output=True,
                output_limit_chars=100,
            )
        assert time.monotonic() - started < 3
        assert pid_path.exists()
    finally:
        if pid_path.exists():
            try:
                os.kill(int(pid_path.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass
