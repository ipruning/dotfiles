"""Run bounded commands and stop their process group on timeout."""

from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path


def kill_process_group(
    process: subprocess.Popen[bytes] | subprocess.Popen[str],
) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def run_process_group(
    command: tuple[str, ...],
    *,
    timeout_seconds: float,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    capture_output: bool = False,
    stdin_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
        env=env,
        cwd=cwd,
        process_group=0,
        text=True,
    )
    try:
        stdout, stderr = process.communicate(
            input=stdin_text,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        kill_process_group(process)
        stdout, stderr = process.communicate()
        raise subprocess.TimeoutExpired(
            command,
            timeout_seconds,
            output=stdout,
            stderr=stderr,
        ) from error
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
