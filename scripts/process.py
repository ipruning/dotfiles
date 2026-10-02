"""执行限时进程组，按需保留输出尾部并报告进度。"""

from __future__ import annotations

import codecs
import os
import selectors
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path


def kill_process_group(
    process: subprocess.Popen[bytes] | subprocess.Popen[str],
) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        # macOS 对已消失的进程组也可能返回 EPERM；活进程的权限错误保留。
        if process.poll() is None:
            raise
    process.wait()


class _Output:
    def __init__(self, limit: int | None) -> None:
        self.limit = limit
        self.chunks: list[str] = []
        self.tail = ""
        self.decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

    def append(self, data: bytes, *, final: bool = False) -> str:
        text = self.decoder.decode(data, final=final)
        if self.limit is None:
            self.chunks.append(text)
        else:
            self.tail = (self.tail + text)[-self.limit :] if self.limit else ""
        return text

    def value(self) -> str:
        return "".join(self.chunks) if self.limit is None else self.tail


def run_process_group(
    command: tuple[str, ...],
    *,
    timeout_seconds: float,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    capture_output: bool = False,
    stdin_text: str | None = None,
    output_limit_chars: int | None = None,
    inherit_output: bool = False,
    on_progress: Callable[[float], None] | None = None,
    progress_interval_seconds: float = 15,
) -> subprocess.CompletedProcess[str]:
    """保留完整生成输出；维护命令可指定尾部上限，避免日志占满内存。

    超时同时覆盖 stdin 写入和子进程继承的输出管道。超时后不再等待
    管道 EOF，以免脱离进程组的后代持有管道导致清理无限等待。
    """
    if output_limit_chars is not None and output_limit_chars < 0:
        raise ValueError("output_limit_chars must be nonnegative")
    if progress_interval_seconds <= 0:
        raise ValueError("progress_interval_seconds must be positive")
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
        env=env,
        cwd=cwd,
        process_group=0,
    )
    outputs = {
        "stdout": _Output(output_limit_chars),
        "stderr": _Output(output_limit_chars),
    }
    pending_input = memoryview((stdin_text or "").encode())
    started = time.monotonic()
    next_progress = started + progress_interval_seconds
    with selectors.DefaultSelector() as selector:
        for name, pipe in (("stdout", process.stdout), ("stderr", process.stderr)):
            if pipe is not None:
                os.set_blocking(pipe.fileno(), False)
                selector.register(pipe, selectors.EVENT_READ, name)
        if process.stdin is not None:
            if pending_input:
                os.set_blocking(process.stdin.fileno(), False)
                selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
            else:
                process.stdin.close()
        try:
            while selector.get_map() or process.poll() is None:
                now = time.monotonic()
                remaining = timeout_seconds - (now - started)
                if remaining <= 0:
                    kill_process_group(process)
                    raise subprocess.TimeoutExpired(
                        command,
                        timeout_seconds,
                        output=outputs["stdout"].value() if capture_output else None,
                        stderr=outputs["stderr"].value() if capture_output else None,
                    )
                if on_progress is not None and now >= next_progress:
                    on_progress(now - started)
                    next_progress = now + progress_interval_seconds
                delay = min(0.1, remaining)
                if on_progress is not None:
                    delay = min(delay, max(0, next_progress - now))
                for key, _ in selector.select(delay):
                    pipe = key.fileobj
                    if key.data == "stdin":
                        try:
                            written = os.write(key.fd, pending_input[:65536])
                            pending_input = pending_input[written:]
                        except BrokenPipeError:
                            pending_input = memoryview(b"")
                        if not pending_input:
                            selector.unregister(pipe)
                            assert process.stdin is not None
                            process.stdin.close()
                        continue
                    data = os.read(key.fd, 65536)
                    name = str(key.data)
                    text = outputs[name].append(data, final=not data)
                    if inherit_output:
                        stream = sys.stdout if name == "stdout" else sys.stderr
                        stream.write(text)
                        stream.flush()
                    if not data:
                        selector.unregister(pipe)
        finally:
            if process.poll() is None:
                kill_process_group(process)
            for pipe in (process.stdin, process.stdout, process.stderr):
                if pipe is not None:
                    pipe.close()
    return subprocess.CompletedProcess(
        command,
        process.returncode,
        outputs["stdout"].value() if capture_output else None,
        outputs["stderr"].value() if capture_output else None,
    )
