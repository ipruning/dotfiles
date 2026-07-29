"""Update installed host tools with explicit preview and apply modes."""

from __future__ import annotations

import argparse
import codecs
import json
import os
import selectors
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

from .mise import (
    canonical_mise_environment,
    canonical_mise_executable,
    canonical_mise_path,
)
from .models import ExecutableFinder

StepCallback = Callable[["UpdateStep"], None]
NEXT_COMMANDS = (
    "git diff -- reference/.config/mise",
    "mise run runtime",
)
MISE_TOOLS_NOTE = (
    "mise.tools uses --bump and may update tracked reference/.config/mise files "
    "when the live global config is linked to this checkout."
)
PROGRESS_INTERVAL_SECONDS = 30
TIGRIS_ATTENTION = (
    "may require sudo to replace /usr/local/bin/tigris; run `tigris update` in "
    "an interactive terminal before applying the remaining plan"
)


class UpdateStatus(StrEnum):
    PLANNED = "planned"
    SKIPPED = "skipped"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class UpdateStep:
    name: str
    tool: str
    command: tuple[str, ...]
    timeout_seconds: int
    path_prepend: tuple[Path, ...] = ()
    attention: str | None = None


@dataclass(frozen=True)
class UpdateResult:
    step: UpdateStep
    status: UpdateStatus
    exit_code: int | None = None
    duration_ms: int | None = None
    reason: str | None = None


@dataclass(frozen=True)
class UpdateReport:
    apply: bool
    results: tuple[UpdateResult, ...]

    @property
    def ok(self) -> bool:
        return all(result.status is not UpdateStatus.FAILED for result in self.results)


def _emit_failure(step: UpdateStep, reason: str) -> None:
    print(f"[{step.name}] FAIL {reason}", file=sys.stderr)


def _run_with_progress(
    step: UpdateStep,
    *,
    env: dict[str, str] | None,
    progress_interval_seconds: float,
) -> subprocess.CompletedProcess[str]:
    """Stream a JSON-mode command to stderr and report quiet elapsed time."""
    print(f"[{step.name}] RUN {_display_command(step)}", file=sys.stderr, flush=True)
    started_at = time.monotonic()
    process = subprocess.Popen(
        step.command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        process_group=0,
    )
    assert process.stdout is not None
    output = process.stdout
    selector = selectors.DefaultSelector()
    selector.register(output, selectors.EVENT_READ)
    os.set_blocking(output.fileno(), False)
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    pending = ""

    def emit(data: bytes = b"", *, final: bool = False) -> None:
        nonlocal pending
        pending += decoder.decode(data, final=final)
        lines = pending.splitlines(keepends=True)
        pending = ""
        if (
            lines
            and not final
            and (not lines[-1].endswith(("\n", "\r")) or lines[-1].endswith("\r"))
        ):
            pending = lines.pop()
        for line in lines:
            print(
                f"[{step.name}] {line.removesuffix(chr(10)).removesuffix(chr(13))}",
                file=sys.stderr,
                flush=True,
            )

    def drain() -> None:
        # Preserve a bounded tail without letting an inherited, continuously
        # written pipe override the direct updater's completed exit status.
        for _ in range(16):
            try:
                chunk = os.read(output.fileno(), 65536)
            except BlockingIOError:
                return
            if not chunk:
                return
            emit(chunk)

    def kill_process_group() -> None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()

    next_progress_at = started_at + progress_interval_seconds
    try:
        while True:
            now = time.monotonic()
            remaining = step.timeout_seconds - (now - started_at)
            if remaining <= 0:
                kill_process_group()
                drain()
                emit(final=True)
                raise subprocess.TimeoutExpired(step.command, step.timeout_seconds)
            wait_seconds = min(0.1, remaining, max(0, next_progress_at - now))
            for key, _mask in selector.select(timeout=wait_seconds):
                try:
                    chunk = os.read(key.fd, 65536)
                except BlockingIOError:
                    continue
                if chunk:
                    emit(chunk)
                else:
                    selector.unregister(key.fileobj)
            exit_code = process.poll()
            if exit_code is not None:
                drain()
                emit(final=True)
                duration_seconds = round(time.monotonic() - started_at)
                print(
                    f"[{step.name}] DONE exit={exit_code} elapsed={duration_seconds}s",
                    file=sys.stderr,
                    flush=True,
                )
                return subprocess.CompletedProcess(step.command, exit_code, "", "")
            now = time.monotonic()
            if now >= next_progress_at:
                elapsed_seconds = round(now - started_at)
                print(
                    f"[{step.name}] STILL RUNNING elapsed={elapsed_seconds}s "
                    f"timeout={step.timeout_seconds}s",
                    file=sys.stderr,
                    flush=True,
                )
                next_progress_at = now + progress_interval_seconds
    finally:
        if process.poll() is None:
            kill_process_group()
        selector.close()
        output.close()


def _installed_mise_tools(home: Path, mise_executable: str) -> tuple[str, ...]:
    """Return active installed versions so upgrade cannot bootstrap missing tools."""
    command = (
        mise_executable,
        "ls",
        "--current",
        "--installed",
        "--json",
        "-C",
        str(home),
    )
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            env=canonical_mise_environment(home),
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("mise tool inventory timed out after 120s") from error
    except OSError as error:
        raise RuntimeError(
            f"could not inspect installed mise tools: {error}"
        ) from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        reason = f"mise tool inventory exited {completed.returncode}"
        raise RuntimeError(f"{reason}: {detail}" if detail else reason)
    try:
        document = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"mise tool inventory returned invalid JSON: {error}"
        ) from error
    if not isinstance(document, dict):
        raise RuntimeError("mise tool inventory must be a JSON object")

    installed: list[str] = []
    for name, raw_versions in document.items():
        if not isinstance(name, str) or not isinstance(raw_versions, list):
            raise RuntimeError("mise tool inventory has an invalid tool entry")
        for raw_version in raw_versions:
            if not isinstance(raw_version, dict):
                raise RuntimeError(f"mise tool inventory for {name} is invalid")
            version = raw_version.get("version")
            if not isinstance(version, str) or not version:
                raise RuntimeError(f"mise tool inventory for {name} has no version")
            installed.append(f"{name}@{version}")
    return tuple(sorted(set(installed)))


def _update_steps(home: Path) -> tuple[UpdateStep, ...]:
    mise_executable = str(canonical_mise_path(home))
    mise_path = (canonical_mise_path(home).parent,)
    return (
        UpdateStep("brew.metadata", "brew", ("brew", "update"), 900),
        # Package-mutating steps get transaction-scale timeouts: killing brew or
        # mise mid-upgrade leaves partial kegs, stale locks, or half-written
        # tool state, which is worse than waiting out a slow upgrade.
        UpdateStep("brew.packages", "brew", ("brew", "upgrade"), 3600),
        UpdateStep(
            "mise.self",
            "mise",
            (mise_executable, "self-update", "--yes", "--no-plugins"),
            900,
            path_prepend=mise_path,
        ),
        UpdateStep(
            "mise.tools",
            "mise",
            (mise_executable, "upgrade", "--bump", "-C", str(home)),
            1800,
            path_prepend=mise_path,
        ),
        UpdateStep(
            "mise.shims",
            "mise",
            (mise_executable, "reshim", "-C", str(home)),
            120,
            path_prepend=mise_path,
        ),
        UpdateStep(
            "gh.extensions",
            "gh",
            ("gh", "extension", "upgrade", "--all"),
            300,
        ),
        UpdateStep("tldr.pages", "tldr", ("tldr", "--update"), 300),
        UpdateStep("yazi.packages", "ya", ("ya", "pkg", "upgrade"), 300),
        UpdateStep(
            "sprite.version",
            "sprite",
            ("sprite", "upgrade"),
            300,
        ),
        UpdateStep("amp", "amp", ("amp", "update"), 300),
        UpdateStep("claude", "claude", ("claude", "update"), 300),
        UpdateStep("codex", "codex", ("codex", "update"), 300),
        UpdateStep(
            "tigris",
            "tigris",
            ("tigris", "update"),
            300,
            attention=TIGRIS_ATTENTION,
        ),
        UpdateStep(
            "pi.extensions",
            "pi",
            ("pi", "update", "--extensions"),
            300,
        ),
    )


def plan_updates(
    home: Path,
    *,
    executable_finder: ExecutableFinder = shutil.which,
) -> UpdateReport:
    """Return the exact available update plan without running commands."""
    results = []
    mise_executable = canonical_mise_executable(home)
    for step in _update_steps(home):
        available = (
            mise_executable is not None
            if step.tool == "mise"
            else executable_finder(step.tool) is not None
        )
        if available and step.name == "mise.tools":
            assert mise_executable is not None
            try:
                installed = _installed_mise_tools(home, mise_executable)
            except RuntimeError as error:
                results.append(
                    UpdateResult(
                        step=step,
                        status=UpdateStatus.FAILED,
                        reason=str(error),
                    ),
                )
                continue
            if not installed:
                results.append(
                    UpdateResult(
                        step=step,
                        status=UpdateStatus.SKIPPED,
                        reason="no active mise tools are installed",
                    ),
                )
                continue
            step = replace(step, command=(*step.command, *installed))
        results.append(
            UpdateResult(
                step=step,
                status=UpdateStatus.PLANNED if available else UpdateStatus.SKIPPED,
                reason=(
                    None
                    if available
                    else (
                        f"{canonical_mise_path(home)} is missing, symlinked, or not executable"
                        if step.tool == "mise"
                        else f"{step.tool} is not available on PATH"
                    )
                ),
            ),
        )
    return UpdateReport(apply=False, results=tuple(results))


def execute_updates(
    home: Path,
    *,
    executable_finder: ExecutableFinder = shutil.which,
    capture_output: bool = False,
    on_start: StepCallback | None = None,
    progress_interval_seconds: float = PROGRESS_INTERVAL_SECONDS,
) -> UpdateReport:
    """Run every available updater and retain independent failure results."""
    results = []
    for planned in plan_updates(home, executable_finder=executable_finder).results:
        # Carry through anything the preflight already resolved (SKIPPED, or a
        # FAILED mise inventory). Only PLANNED steps run: executing a FAILED
        # mise.tools step would run `mise upgrade` with no tool arguments and
        # upgrade every installed tool — the exact outcome the preflight avoids.
        if planned.status is not UpdateStatus.PLANNED:
            results.append(planned)
            continue
        if on_start:
            on_start(planned.step)
        started_at = time.monotonic()
        try:
            environment = (
                canonical_mise_environment(home) if planned.step.path_prepend else None
            )
            completed = (
                _run_with_progress(
                    planned.step,
                    env=environment,
                    progress_interval_seconds=progress_interval_seconds,
                )
                if capture_output
                else subprocess.run(
                    planned.step.command,
                    check=False,
                    stdin=subprocess.DEVNULL,
                    env=environment,
                    text=True,
                    timeout=planned.step.timeout_seconds,
                )
            )
        except subprocess.TimeoutExpired:
            reason = f"timed out after {planned.step.timeout_seconds}s"
            if capture_output:
                _emit_failure(planned.step, reason)
            results.append(
                UpdateResult(
                    step=planned.step,
                    status=UpdateStatus.FAILED,
                    duration_ms=round((time.monotonic() - started_at) * 1000),
                    reason=reason,
                ),
            )
            continue
        except OSError as error:
            reason = str(error)
            if capture_output:
                _emit_failure(planned.step, reason)
            results.append(
                UpdateResult(
                    step=planned.step,
                    status=UpdateStatus.FAILED,
                    duration_ms=round((time.monotonic() - started_at) * 1000),
                    reason=reason,
                ),
            )
            continue
        if capture_output and completed.returncode != 0:
            _emit_failure(
                planned.step,
                f"command exited {completed.returncode}",
            )
        results.append(
            UpdateResult(
                step=planned.step,
                status=(
                    UpdateStatus.SUCCEEDED
                    if completed.returncode == 0
                    else UpdateStatus.FAILED
                ),
                exit_code=completed.returncode,
                duration_ms=round((time.monotonic() - started_at) * 1000),
                reason=(
                    None
                    if completed.returncode == 0
                    else f"command exited {completed.returncode}"
                ),
            ),
        )
    return UpdateReport(apply=True, results=tuple(results))


def _summary(report: UpdateReport) -> dict[str, int]:
    return {
        status.value: count
        for status in (
            UpdateStatus.PLANNED,
            UpdateStatus.SUCCEEDED,
            UpdateStatus.SKIPPED,
            UpdateStatus.FAILED,
        )
        if (count := sum(result.status is status for result in report.results))
    }


def _next_commands(report: UpdateReport) -> tuple[str, ...]:
    if not report.apply:
        return (
            ("mise run update -- --apply",)
            if any(result.status is UpdateStatus.PLANNED for result in report.results)
            else ()
        )
    if not report.ok or not any(
        result.status is UpdateStatus.SUCCEEDED for result in report.results
    ):
        return ()
    return NEXT_COMMANDS


def _notes(report: UpdateReport) -> tuple[str, ...]:
    if any(
        result.step.name == "mise.tools" and result.status is not UpdateStatus.SKIPPED
        for result in report.results
    ):
        return (MISE_TOOLS_NOTE,)
    return ()


def _document(report: UpdateReport) -> dict[str, object]:
    return {
        "schema_version": 1,
        "operation": "update",
        "apply": report.apply,
        "ok": report.ok,
        "steps": [
            {
                "name": result.step.name,
                "tool": result.step.tool,
                "command": list(result.step.command),
                "environment": {
                    "PATH_prepend": [
                        str(directory) for directory in result.step.path_prepend
                    ],
                },
                "attention": result.step.attention,
                "status": result.status.value,
                "exit_code": result.exit_code,
                "duration_ms": result.duration_ms,
                "reason": result.reason,
            }
            for result in report.results
        ],
        "summary": _summary(report),
        "notes": list(_notes(report)),
        "next": list(_next_commands(report)),
    }


def _display_command(step: UpdateStep) -> str:
    command = " ".join(step.command)
    if not step.path_prepend:
        return command
    path = ":".join(str(directory) for directory in step.path_prepend)
    return f"PATH={path}:$PATH {command}"


def _render(report: UpdateReport) -> None:
    def duration(result: UpdateResult) -> str:
        return (
            f" ({result.duration_ms / 1000:.1f}s)"
            if result.duration_ms is not None
            else ""
        )

    for result in report.results:
        label = result.status.value.upper()
        if result.status is UpdateStatus.PLANNED:
            print(f"{label:7} {result.step.name}: {_display_command(result.step)}")
            if result.step.attention:
                print(f"ATTENTION {result.step.name}: {result.step.attention}")
        elif result.status is UpdateStatus.SUCCEEDED:
            print(f"{label:7} {result.step.name}{duration(result)}")
        elif result.status is UpdateStatus.SKIPPED:
            print(f"{label:7} {result.step.name}: {result.reason}")
        else:
            print(
                f"{label:7} {result.step.name}{duration(result)}: {result.reason}",
                file=sys.stderr,
            )
    summary = _summary(report)
    rendered = ", ".join(f"{count} {status}" for status, count in summary.items())
    print(f"Summary: {rendered or 'no steps'}")
    for note in _notes(report):
        print(f"Note: {note}")
    if not report.apply:
        if _next_commands(report):
            print("No commands run. Re-run with --apply to update host tools.")
        else:
            print("No update commands are available on this host.")
        return
    if not report.ok:
        print("Update incomplete. Resolve failed steps before refreshing runtime.")
        return
    next_commands = _next_commands(report)
    if not next_commands:
        print("No update commands ran.")
        return
    print("Next:")
    for command in next_commands:
        print(f"  {command}")


def _announce_step(step: UpdateStep) -> None:
    print(f"RUN {step.name}: {_display_command(step)}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Update installed tools with explicit preview and apply modes.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="run the available updaters (default: preview only)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit the report as JSON on stdout",
    )
    args = parser.parse_args(argv)
    report = (
        execute_updates(
            Path.home(),
            capture_output=args.as_json,
            on_start=None if args.as_json else _announce_step,
        )
        if args.apply
        else plan_updates(Path.home())
    )
    if args.as_json:
        print(json.dumps(_document(report), indent=2, sort_keys=True))
    else:
        _render(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
