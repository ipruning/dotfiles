"""Snapshot installed host software into inventory/<host>/."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .models import ExecutableFinder

StepCallback = Callable[["InventorySpec"], None]
APPLY_COMMAND = "mise run inventory -- --apply"
REVIEW_COMMAND = "git diff inventory/"
HOST_NAME_RE = re.compile(r"[^A-Za-z0-9._-]")


class InventoryStatus(StrEnum):
    PLANNED = "planned"
    SKIPPED = "skipped"
    WRITTEN = "written"
    UNCHANGED = "unchanged"
    FAILED = "failed"


@dataclass(frozen=True)
class InventorySpec:
    name: str
    filename: str
    tool: str | None = None
    command: tuple[str, ...] = ()
    scan_dir: Path | None = None
    timeout_seconds: int = 300
    allow_empty: bool = False


@dataclass(frozen=True)
class InventoryResult:
    spec: InventorySpec
    status: InventoryStatus
    target: Path
    reason: str | None = None
    exit_code: int | None = None
    duration_ms: int | None = None


@dataclass(frozen=True)
class InventoryReport:
    host: str
    apply: bool
    results: tuple[InventoryResult, ...]

    @property
    def ok(self) -> bool:
        return all(
            result.status is not InventoryStatus.FAILED for result in self.results
        )


class SnapshotParseError(ValueError):
    """Collector output cannot be turned into a snapshot."""

    def __init__(self, message: str, exit_code: int | None = None) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def sanitize_host(raw: str) -> str:
    cleaned = HOST_NAME_RE.sub("-", raw)
    if cleaned in {"", ".", ".."}:
        return "unknown-host"
    return cleaned


def detect_host() -> str:
    return sanitize_host(socket.gethostname().split(".")[0])


def _inventory_specs(applications_root: Path) -> tuple[InventorySpec, ...]:
    return (
        InventorySpec(
            "brew.bundle",
            "Brewfile",
            tool="brew",
            command=("brew", "bundle", "dump", "--file=-", "--quiet"),
            timeout_seconds=300,
        ),
        InventorySpec(
            "gh.extensions",
            "gh_extensions.txt",
            tool="gh",
            command=("gh", "extension", "list"),
            timeout_seconds=120,
            # Zero installed extensions is a legitimate host state, not a
            # broken collector; the successful exit code already guards that.
            allow_empty=True,
        ),
        InventorySpec("applications", "applications.txt", scan_dir=applications_root),
        InventorySpec(
            "setapp",
            "setapp.txt",
            scan_dir=applications_root / "Setapp",
            # Setapp is optional: an absent or empty Setapp directory is a
            # legitimate zero-app state that must overwrite a stale snapshot,
            # not be skipped. Availability is gated on the /Applications root
            # (below) so a non-macOS host still skips it.
            allow_empty=True,
        ),
    )


def _parse_gh_extensions(stdout: str) -> str:
    repositories = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) >= 2 and "/" in fields[1]:
            repositories.append(fields[1].strip())
            continue
        raise SnapshotParseError(
            f"unrecognized gh extension list line: {line.strip()!r}"
        )
    return "".join(f"{repo}\n" for repo in sorted(repositories, key=str.casefold))


def _parse_output(spec: InventorySpec, stdout: str) -> str:
    if spec.name == "gh.extensions":
        return _parse_gh_extensions(stdout)
    if stdout and not stdout.endswith("\n"):
        return f"{stdout}\n"
    return stdout


def _scan_applications(scan_dir: Path) -> str:
    names = sorted(
        (entry.name.removesuffix(".app") for entry in scan_dir.glob("*.app")),
        key=str.casefold,
    )
    return "".join(f"{name}\n" for name in names)


def plan_inventory(
    repo_root: Path,
    host: str,
    *,
    applications_root: Path = Path("/Applications"),
    executable_finder: ExecutableFinder = shutil.which,
) -> InventoryReport:
    """Return the exact snapshot plan without running collectors."""
    host_dir = repo_root / "inventory" / host
    results = []
    for spec in _inventory_specs(applications_root):
        if spec.tool is not None:
            available = executable_finder(spec.tool) is not None
            reason = None if available else f"{spec.tool} is not available on PATH"
        else:
            assert spec.scan_dir is not None
            # A scan is applicable whenever the /Applications root exists, so a
            # macOS host records zero apps for an absent Setapp subdirectory
            # instead of leaving a stale snapshot; a non-macOS host (no
            # /Applications) skips both scans.
            available = applications_root.is_dir()
            reason = None if available else f"{applications_root} is not a directory"
        results.append(
            InventoryResult(
                spec=spec,
                status=(
                    InventoryStatus.PLANNED if available else InventoryStatus.SKIPPED
                ),
                target=host_dir / spec.filename,
                reason=reason,
            ),
        )
    return InventoryReport(host=host, apply=False, results=tuple(results))


def _emit_failure(spec: InventorySpec, reason: str, stderr: str = "") -> None:
    for line in stderr.splitlines():
        print(f"[{spec.name}] {line}", file=sys.stderr)
    print(f"[{spec.name}] FAIL {reason}", file=sys.stderr)


def _collect(spec: InventorySpec) -> tuple[str, int | None]:
    """Return snapshot content for one planned spec, raising on failure."""
    if spec.scan_dir is not None:
        return _scan_applications(spec.scan_dir), None
    completed = subprocess.run(
        spec.command,
        check=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=spec.timeout_seconds,
    )
    if completed.returncode != 0:
        raise SnapshotParseError(
            f"command exited {completed.returncode}"
            + (f"\n{completed.stderr}" if completed.stderr else ""),
            completed.returncode,
        )
    try:
        content = _parse_output(spec, completed.stdout)
    except SnapshotParseError as error:
        raise SnapshotParseError(str(error), completed.returncode) from error
    return content, completed.returncode


def execute_inventory(
    plan: InventoryReport,
    *,
    on_start: StepCallback | None = None,
) -> InventoryReport:
    """Run every planned collector and retain independent failure results."""
    results = []
    for planned in plan.results:
        if planned.status is not InventoryStatus.PLANNED:
            results.append(planned)
            continue
        if on_start:
            on_start(planned.spec)
        started_at = time.monotonic()
        exit_code: int | None = None
        try:
            content, exit_code = _collect(planned.spec)
            if not content and not planned.spec.allow_empty:
                raise SnapshotParseError(
                    "collector produced empty output; kept existing snapshot"
                )
            if planned.target.exists() and planned.target.read_text() == content:
                status = InventoryStatus.UNCHANGED
            else:
                planned.target.parent.mkdir(parents=True, exist_ok=True)
                descriptor, temporary_name = tempfile.mkstemp(
                    dir=planned.target.parent,
                    prefix=f".{planned.target.name}.tmp-",
                )
                temporary = Path(temporary_name)
                try:
                    os.fchmod(descriptor, 0o644)
                    with os.fdopen(descriptor, "w") as snapshot:
                        snapshot.write(content)
                        snapshot.flush()
                        os.fsync(snapshot.fileno())
                    temporary.replace(planned.target)
                finally:
                    temporary.unlink(missing_ok=True)
                status = InventoryStatus.WRITTEN
            results.append(
                InventoryResult(
                    spec=planned.spec,
                    status=status,
                    target=planned.target,
                    exit_code=exit_code,
                    duration_ms=round((time.monotonic() - started_at) * 1000),
                ),
            )
        except subprocess.TimeoutExpired:
            reason = f"timed out after {planned.spec.timeout_seconds}s"
            _emit_failure(planned.spec, reason)
            results.append(
                InventoryResult(
                    spec=planned.spec,
                    status=InventoryStatus.FAILED,
                    target=planned.target,
                    reason=reason,
                    duration_ms=round((time.monotonic() - started_at) * 1000),
                ),
            )
        except (OSError, SnapshotParseError) as error:
            if isinstance(error, SnapshotParseError) and error.exit_code is not None:
                exit_code = error.exit_code
            reason, _, stderr = str(error).partition("\n")
            _emit_failure(planned.spec, reason, stderr)
            results.append(
                InventoryResult(
                    spec=planned.spec,
                    status=InventoryStatus.FAILED,
                    target=planned.target,
                    reason=reason,
                    exit_code=exit_code,
                    duration_ms=round((time.monotonic() - started_at) * 1000),
                ),
            )
    return InventoryReport(host=plan.host, apply=True, results=tuple(results))


def _summary(report: InventoryReport) -> dict[str, int]:
    return {
        status.value: count
        for status in (
            InventoryStatus.PLANNED,
            InventoryStatus.WRITTEN,
            InventoryStatus.UNCHANGED,
            InventoryStatus.SKIPPED,
            InventoryStatus.FAILED,
        )
        if (count := sum(result.status is status for result in report.results))
    }


def _next_commands(report: InventoryReport) -> tuple[str, ...]:
    if not report.apply:
        return (
            (APPLY_COMMAND,)
            if any(
                result.status is InventoryStatus.PLANNED for result in report.results
            )
            else ()
        )
    return (
        (REVIEW_COMMAND,)
        if any(result.status is InventoryStatus.WRITTEN for result in report.results)
        else ()
    )


def _document(report: InventoryReport, repo_root: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "operation": "inventory",
        "host": report.host,
        "apply": report.apply,
        "ok": report.ok,
        "steps": [
            {
                "name": result.spec.name,
                "status": result.status.value,
                "tool": result.spec.tool,
                "command": list(result.spec.command),
                "scan_dir": (
                    str(result.spec.scan_dir) if result.spec.scan_dir else None
                ),
                "target": str(result.target.relative_to(repo_root)),
                "reason": result.reason,
                "exit_code": result.exit_code,
                "duration_ms": result.duration_ms,
            }
            for result in report.results
        ],
        "summary": _summary(report),
        "next": list(_next_commands(report)),
    }


def _render(report: InventoryReport, repo_root: Path) -> None:
    for result in report.results:
        target = result.target.relative_to(repo_root)
        label = result.status.value.upper()
        if result.status is InventoryStatus.PLANNED:
            source = (
                " ".join(result.spec.command)
                if result.spec.command
                else f"scan {result.spec.scan_dir}"
            )
            print(f"{label:7} {result.spec.name}: {source} -> {target}")
        elif result.status is InventoryStatus.SKIPPED:
            print(f"{label:7} {result.spec.name}: {result.reason}")
        elif result.status is InventoryStatus.WRITTEN:
            print(f"{label:7} {result.spec.name}: {target}")
        elif result.status is InventoryStatus.UNCHANGED:
            print(f"{label:7} {result.spec.name}: {target} unchanged")
        else:
            print(
                f"{label:7} {result.spec.name}: {result.reason}",
                file=sys.stderr,
            )
    summary = _summary(report)
    rendered = ", ".join(f"{count} {status}" for status, count in summary.items())
    print(f"Summary: {rendered or 'no steps'}")
    if not report.apply:
        if _next_commands(report):
            print("No snapshots written. Re-run with --apply to snapshot this host.")
        else:
            print("No inventory collectors are available on this host.")
        return
    next_commands = _next_commands(report)
    if not next_commands:
        print("No inventory changes.")
        return
    print("Next:")
    for command in next_commands:
        print(f"  {command}")


def _announce_step(spec: InventorySpec) -> None:
    source = " ".join(spec.command) if spec.command else f"scan {spec.scan_dir}"
    print(f"RUN {spec.name}: {source}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Snapshot installed host software into inventory/<host>/.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the planned snapshots (default: preview only)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit the report as JSON on stdout",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root that owns inventory/ (default: this checkout)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="snapshot directory name; defaults to the sanitized short hostname",
    )
    parser.add_argument(
        "--applications-root",
        type=Path,
        default=Path("/Applications"),
        help="application scan root; Setapp is scanned at <root>/Setapp",
    )
    args = parser.parse_args(argv)
    if args.host is not None and sanitize_host(args.host) != args.host:
        parser.error("--host must use only [A-Za-z0-9._-] and must not be '.' or '..'")
    host = args.host if args.host is not None else detect_host()
    report = plan_inventory(
        args.repo_root,
        host,
        applications_root=args.applications_root,
    )
    if args.apply:
        report = execute_inventory(
            report,
            on_start=None if args.as_json else _announce_step,
        )
    if args.as_json:
        print(json.dumps(_document(report, args.repo_root), indent=2, sort_keys=True))
    else:
        _render(report, args.repo_root)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
