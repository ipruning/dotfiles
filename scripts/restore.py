"""Apply one reference application to the current home explicitly."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from .diff import DriftProtocolError, MackupCommandError, inspect_drift
from .models import Drift, DriftKind
from .render import emit_error


class RestoreStatus(StrEnum):
    PLANNED = "planned"
    APPLIED = "applied"
    SKIPPED = "skipped"
    FAILED = "failed"


class RestoreError(RuntimeError):
    """A planned restore path cannot be applied safely."""


@dataclass(frozen=True)
class RestoreResult:
    drift: Drift
    action: str | None
    status: RestoreStatus
    backup_path: Path | None = None
    error: str | None = None


@dataclass(frozen=True)
class RestoreReport:
    application: str
    apply: bool
    results: tuple[RestoreResult, ...]

    @property
    def ok(self) -> bool:
        return all(result.status is not RestoreStatus.FAILED for result in self.results)


def plan_restore(repo_root: Path, home: Path, application: str) -> RestoreReport:
    """Return a location-only plan for one configured application."""
    drift_report = inspect_drift(
        repo_root,
        home,
        application=application,
        profile="full",
    )
    results = []
    for drift in drift_report.changes:
        if drift.kind in {
            DriftKind.MODIFIED,
            DriftKind.ONLY_REFERENCE,
            DriftKind.TYPE_CHANGED,
        }:
            results.append(
                RestoreResult(drift, action="link", status=RestoreStatus.PLANNED),
            )
        elif drift.kind is DriftKind.UNREADABLE:
            results.append(
                RestoreResult(
                    drift,
                    action=None,
                    status=RestoreStatus.FAILED,
                    error=drift.error or "drift path is unreadable",
                ),
            )
        else:
            results.append(
                RestoreResult(
                    drift,
                    action=None,
                    status=RestoreStatus.SKIPPED,
                    error="reference path is unavailable",
                ),
            )
    return RestoreReport(application=application, apply=False, results=tuple(results))


def _relative_path(path: Path, root: Path, label: str) -> Path:
    try:
        relative = path.absolute().relative_to(root.absolute())
    except ValueError as error:
        raise RestoreError(f"{label} is outside {root}: {path}") from error
    if ".." in relative.parts:
        raise RestoreError(f"{label} traverses outside {root}: {path}")
    return relative


def _path_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _validate_live_parent(path: Path, home: Path) -> None:
    existing = path
    while not _path_exists(existing):
        if existing == existing.parent:
            raise RestoreError(f"live parent has no existing ancestor: {path}")
        existing = existing.parent
    _relative_path(existing.resolve(), home.resolve(), "live parent")


def apply_restore(repo_root: Path, home: Path, plan: RestoreReport) -> RestoreReport:
    """Back up changed live paths and link them to their reference paths."""
    reference_root = repo_root / "reference"
    backup_root = (
        home
        / ".local/state/dotfiles/restore-backups"
        / datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    )
    results = []
    for planned in plan.results:
        if planned.status is not RestoreStatus.PLANNED:
            results.append(planned)
            continue
        drift = planned.drift
        backup_path = None
        moved_live = False
        try:
            _relative_path(drift.reference_path, reference_root, "reference path")
            live_relative = _relative_path(drift.live_path, home, "live path")
            if not _path_exists(drift.reference_path):
                raise RestoreError(
                    f"reference path does not exist: {drift.reference_path}"
                )
            resolved_reference = drift.reference_path.resolve()
            _relative_path(
                resolved_reference, reference_root.resolve(), "reference target"
            )
            _validate_live_parent(drift.live_path.parent, home)
            drift.live_path.parent.mkdir(parents=True, exist_ok=True)
            resolved_parent = drift.live_path.parent.resolve()
            _relative_path(resolved_parent, home.resolve(), "live parent")
            if _path_exists(drift.live_path):
                backup_path = backup_root / live_relative
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                drift.live_path.rename(backup_path)
                moved_live = True
            try:
                drift.live_path.symlink_to(
                    drift.reference_path,
                    target_is_directory=drift.reference_path.is_dir(),
                )
            except OSError:
                if moved_live and backup_path:
                    backup_path.rename(drift.live_path)
                    moved_live = False
                    backup_path = None
                raise
        except (OSError, RestoreError) as error:
            results.append(
                RestoreResult(
                    drift,
                    action="link",
                    status=RestoreStatus.FAILED,
                    backup_path=backup_path if moved_live else None,
                    error=str(error),
                ),
            )
            continue
        results.append(
            RestoreResult(
                drift,
                action="link",
                status=RestoreStatus.APPLIED,
                backup_path=backup_path,
            ),
        )
    return RestoreReport(
        application=plan.application, apply=True, results=tuple(results)
    )


def _document(report: RestoreReport) -> dict[str, object]:
    summary = {
        status.value: sum(result.status is status for result in report.results)
        for status in RestoreStatus
        if any(result.status is status for result in report.results)
    }
    return {
        "schema_version": 1,
        "operation": "restore",
        "application": report.application,
        "apply": report.apply,
        "ok": report.ok,
        "changes": [
            {
                "reference_path": str(result.drift.reference_path),
                "live_path": str(result.drift.live_path),
                "kind": result.drift.kind.value,
                "action": result.action,
                "status": result.status.value,
                "backup_path": (
                    str(result.backup_path) if result.backup_path else None
                ),
                "error": result.error,
            }
            for result in report.results
        ],
        "summary": summary,
    }


def _render(report: RestoreReport) -> None:
    for result in report.results:
        label = result.status.value.upper()
        print(f"{label:7} {result.drift.live_path}")
        print(f"        reference: {result.drift.reference_path}")
        if result.error:
            print(f"        error: {result.error}", file=sys.stderr)
    if not report.apply:
        print("No files changed. Re-run with --apply to restore this application.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Restore one reference application into the current home.",
    )
    parser.add_argument(
        "application",
        help="configured application whose reference files should be restored",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="back up live paths and link them to the reference (default: preview only)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit the report as JSON on stdout",
    )
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    try:
        report = plan_restore(repo_root, Path.home(), args.application)
    except (DriftProtocolError, MackupCommandError) as error:
        emit_error("restore", str(error), as_json=args.as_json)
        return 1
    if args.apply:
        report = apply_restore(repo_root, Path.home(), report)
    if args.as_json:
        print(json.dumps(_document(report), indent=2, sort_keys=True))
        for result in report.results:
            if result.status is RestoreStatus.FAILED:
                print(
                    f"[{report.application}] FAIL {result.drift.live_path}: {result.error}",
                    file=sys.stderr,
                )
    else:
        _render(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
