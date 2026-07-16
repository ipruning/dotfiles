"""Snapshot installed host software into inventory/<host>/."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .models import ExecutableFinder

StepCallback = Callable[["InventorySpec"], None]
NEXT_COMMANDS = ("git diff inventory/",)
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
    dry_run: bool
    results: tuple[InventoryResult, ...]

    @property
    def ok(self) -> bool:
        return all(
            result.status is not InventoryStatus.FAILED for result in self.results
        )


class SnapshotParseError(ValueError):
    """Collector output cannot be turned into a snapshot."""


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
        ),
        InventorySpec("applications", "applications.txt", scan_dir=applications_root),
        InventorySpec("setapp", "setapp.txt", scan_dir=applications_root / "Setapp"),
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
            available = spec.scan_dir.is_dir()
            reason = None if available else f"{spec.scan_dir} is not a directory"
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
    return InventoryReport(host=host, dry_run=True, results=tuple(results))


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
            + (f"\n{completed.stderr}" if completed.stderr else "")
        )
    return _parse_output(spec, completed.stdout), completed.returncode


def execute_inventory(
    plan: InventoryReport,
    *,
    on_start: StepCallback | None = None,
) -> InventoryReport:
    """Run every planned collector and retain independent failure results."""
    results = []
    for planned in plan.results:
        if planned.status is InventoryStatus.SKIPPED:
            results.append(planned)
            continue
        if on_start:
            on_start(planned.spec)
        started_at = time.monotonic()
        exit_code: int | None = None
        try:
            content, exit_code = _collect(planned.spec)
            if not content:
                raise SnapshotParseError(
                    "collector produced empty output; kept existing snapshot"
                )
            if planned.target.exists() and planned.target.read_text() == content:
                status = InventoryStatus.UNCHANGED
            else:
                planned.target.parent.mkdir(parents=True, exist_ok=True)
                planned.target.write_text(content)
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
    return InventoryReport(host=plan.host, dry_run=False, results=tuple(results))


def _document(report: InventoryReport, repo_root: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "operation": "inventory",
        "host": report.host,
        "dry_run": report.dry_run,
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
        "next": list(NEXT_COMMANDS),
    }


def _render(report: InventoryReport, repo_root: Path) -> None:
    for result in report.results:
        target = result.target.relative_to(repo_root)
        if result.status is InventoryStatus.PLANNED:
            source = (
                " ".join(result.spec.command)
                if result.spec.command
                else f"scan {result.spec.scan_dir}"
            )
            print(f"PLAN {result.spec.name}: {source} -> {target}")
        elif result.status is InventoryStatus.SKIPPED:
            print(f"SKIP {result.spec.name}: {result.reason}")
        elif result.status is InventoryStatus.WRITTEN:
            print(f"WROTE {result.spec.name}: {target}")
        elif result.status is InventoryStatus.UNCHANGED:
            print(f"KEEP {result.spec.name}: {target} unchanged")
        else:
            print(f"FAIL {result.spec.name}: {result.reason}", file=sys.stderr)
    if report.dry_run:
        print("No snapshots written.")
    print("Next:")
    for command in NEXT_COMMANDS:
        print(f"  {command}")


def _announce_step(spec: InventorySpec) -> None:
    source = " ".join(spec.command) if spec.command else f"scan {spec.scan_dir}"
    print(f"RUN {spec.name}: {source}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Snapshot installed host software into inventory/<host>/.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[1]
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
    if not args.dry_run:
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
