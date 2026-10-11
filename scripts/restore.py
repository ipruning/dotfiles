"""Apply one reference application to the current home explicitly."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .diff import DriftProtocolError, MackupCommandError, inspect_drift
from .home_paths import path_exists, relative_path, validate_live_parent
from .host_policy import HostPolicyError, mutation_allowed, require_mutation_allowed
from .models import Drift, DriftKind, Status, status_summary
from .render import emit_error


class RestoreError(RuntimeError):
    """A planned restore path cannot be applied safely."""


@dataclass(frozen=True)
class RestoreResult:
    drift: Drift
    action: str | None
    status: Status
    backup_path: Path | None = None
    reason: str | None = None


@dataclass(frozen=True)
class RestoreReport:
    application: str
    apply: bool
    results: tuple[RestoreResult, ...]

    @property
    def ok(self) -> bool:
        return all(result.status is not Status.FAILED for result in self.results)


def _next_commands(
    report: RestoreReport,
    *,
    apply_allowed: bool = True,
) -> tuple[str, ...]:
    if (
        apply_allowed
        and not report.apply
        and report.ok
        and any(result.status is Status.PLANNED for result in report.results)
    ):
        return (
            shlex.join(["mise", "run", "restore", "--", report.application, "--apply"]),
        )
    return ()


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
                RestoreResult(drift, action="link", status=Status.PLANNED),
            )
        elif drift.kind is DriftKind.UNREADABLE:
            results.append(
                RestoreResult(
                    drift,
                    action=None,
                    status=Status.FAILED,
                    reason=drift.error or "drift path is unreadable",
                ),
            )
        else:
            results.append(
                RestoreResult(
                    drift,
                    action=None,
                    status=Status.SKIPPED,
                    reason="reference path is unavailable",
                ),
            )
    return RestoreReport(application=application, apply=False, results=tuple(results))


def apply_restore(repo_root: Path, home: Path, plan: RestoreReport) -> RestoreReport:
    """Back up changed live paths and link them to their reference paths."""
    require_mutation_allowed(home)
    reference_root = repo_root / "reference"
    backup_root = (
        home
        / ".local/state/dotfiles/restore-backups"
        / datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    )
    results = []
    for planned in plan.results:
        if planned.status is not Status.PLANNED:
            results.append(planned)
            continue
        drift = planned.drift
        backup_path = None
        moved_live = False
        try:
            relative_path(
                drift.reference_path, reference_root, "reference path", RestoreError
            )
            live_relative = relative_path(
                drift.live_path, home, "live path", RestoreError
            )
            if not path_exists(drift.reference_path):
                raise RestoreError(
                    f"reference path does not exist: {drift.reference_path}"
                )
            relative_path(
                drift.reference_path.parent.resolve(),
                reference_root.resolve(),
                "reference parent",
                RestoreError,
            )
            if drift.reference_path.is_symlink():
                link_target = drift.reference_path.readlink()
            else:
                resolved_reference = drift.reference_path.resolve()
                relative_path(
                    resolved_reference,
                    reference_root.resolve(),
                    "reference target",
                    RestoreError,
                )
                link_target = drift.reference_path
            validate_live_parent(drift.live_path, home, RestoreError)
            drift.live_path.parent.mkdir(parents=True, exist_ok=True)
            resolved_parent = drift.live_path.parent.resolve()
            relative_path(resolved_parent, home.resolve(), "live parent", RestoreError)
            if path_exists(drift.live_path):
                backup_path = backup_root / live_relative
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                drift.live_path.rename(backup_path)
                moved_live = True
            try:
                drift.live_path.symlink_to(
                    link_target,
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
                    status=Status.FAILED,
                    backup_path=backup_path if moved_live else None,
                    reason=str(error),
                ),
            )
            continue
        results.append(
            RestoreResult(
                drift,
                action="link",
                status=Status.SUCCEEDED,
                backup_path=backup_path,
            ),
        )
    return RestoreReport(
        application=plan.application, apply=True, results=tuple(results)
    )


def _document(
    report: RestoreReport,
    *,
    apply_allowed: bool = True,
) -> dict[str, object]:
    summary = status_summary(result.status for result in report.results)
    return {
        "schema_version": 1,
        "operation": "restore",
        "application": report.application,
        "apply": report.apply,
        "ok": report.ok,
        "next": list(_next_commands(report, apply_allowed=apply_allowed)),
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
                "reason": result.reason,
            }
            for result in report.results
        ],
        "summary": summary,
    }


def render_restore(report: RestoreReport, *, apply_allowed: bool = True) -> None:
    for result in report.results:
        label = result.status.value.upper()
        print(f"{label:7} {result.drift.live_path}")
        print(f"        reference: {result.drift.reference_path}")
        if result.backup_path:
            print(f"        backup: {result.backup_path}")
        if result.reason:
            stream = sys.stderr if result.status is Status.FAILED else sys.stdout
            print(f"        reason: {result.reason}", file=stream)
    summary = status_summary(result.status for result in report.results)
    rendered = ", ".join(f"{count} {status}" for status, count in summary.items())
    print(f"Summary: {rendered or 'no changes'}")
    if not report.apply and summary.get(Status.PLANNED.value):
        if apply_allowed:
            print("No files changed. Re-run with --apply to restore this application.")
            print("Next:")
            for command in _next_commands(report):
                print(f"  {command}")
        else:
            print("No files changed. Host policy disables restore apply.")


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
    home = Path.home()
    try:
        apply_allowed = mutation_allowed(home)
        if args.apply:
            require_mutation_allowed(home)
        report = plan_restore(repo_root, home, args.application)
    except HostPolicyError as error:
        emit_error(
            "restore",
            str(error),
            as_json=args.as_json,
            apply=args.apply,
            code=error.code,
        )
        return 1
    except (DriftProtocolError, MackupCommandError) as error:
        emit_error("restore", str(error), as_json=args.as_json, apply=args.apply)
        return 1
    if args.apply:
        report = apply_restore(repo_root, home, report)
    if args.as_json:
        print(
            json.dumps(
                _document(report, apply_allowed=apply_allowed),
                indent=2,
                sort_keys=True,
            ),
        )
        for result in report.results:
            if result.status is Status.FAILED:
                print(
                    f"[{report.application}] FAIL {result.drift.live_path}: {result.reason}",
                    file=sys.stderr,
                )
    else:
        render_restore(report, apply_allowed=apply_allowed)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
