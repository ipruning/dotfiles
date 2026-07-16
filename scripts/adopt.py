"""Adopt one application's live configuration into the reference explicitly."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .diff import DriftProtocolError, MackupCommandError, inspect_drift
from .models import Drift, DriftKind
from .render import emit_error


class AdoptStatus(StrEnum):
    PLANNED = "planned"
    APPLIED = "applied"
    FAILED = "failed"


class AdoptError(RuntimeError):
    """A planned adoption path cannot be applied safely."""


@dataclass(frozen=True)
class AdoptResult:
    drift: Drift
    action: str | None
    status: AdoptStatus
    error: str | None = None


@dataclass(frozen=True)
class AdoptReport:
    application: str
    apply: bool
    results: tuple[AdoptResult, ...]

    @property
    def ok(self) -> bool:
        return all(result.status is not AdoptStatus.FAILED for result in self.results)


def plan_adopt(repo_root: Path, home: Path, application: str) -> AdoptReport:
    """Return a location-only plan that would make the reference match live."""
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
            DriftKind.ONLY_LIVE,
            DriftKind.TYPE_CHANGED,
        }:
            results.append(
                AdoptResult(drift, action="copy", status=AdoptStatus.PLANNED),
            )
        elif drift.kind is DriftKind.ONLY_REFERENCE:
            results.append(
                AdoptResult(drift, action="remove", status=AdoptStatus.PLANNED),
            )
        else:
            results.append(
                AdoptResult(
                    drift,
                    action=None,
                    status=AdoptStatus.FAILED,
                    error=drift.error or "drift path is unreadable",
                ),
            )
    return AdoptReport(application=application, apply=False, results=tuple(results))


def _relative_path(path: Path, root: Path, label: str) -> Path:
    try:
        relative = path.absolute().relative_to(root.absolute())
    except ValueError as error:
        raise AdoptError(f"{label} is outside {root}: {path}") from error
    if ".." in relative.parts:
        raise AdoptError(f"{label} traverses outside {root}: {path}")
    return relative


def _dirty_reference_paths(repo_root: Path, plan: AdoptReport) -> list[str]:
    reference_root = repo_root / "reference"
    relative_paths = [
        str(
            _relative_path(result.drift.reference_path, repo_root, "reference path"),
        )
        for result in plan.results
        if result.status is AdoptStatus.PLANNED
    ]
    for relative in relative_paths:
        _relative_path(repo_root / relative, reference_root, "reference path")
    if not relative_paths:
        return []
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "status",
            "--porcelain",
            "-z",
            "--",
            *relative_paths,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise AdoptError(
            completed.stderr.strip() or "unable to inspect reference worktree state",
        )
    entries = [entry for entry in completed.stdout.split("\0") if entry]
    dirty: list[str] = []
    skip_next = False
    for entry in entries:
        if skip_next:
            # Rename/copy records emit the origin path as a bare second
            # entry that carries no status prefix.
            skip_next = False
            dirty.append(entry)
            continue
        dirty.append(entry[3:])
        skip_next = entry[0] in "RC"
    return dirty


def _validate_reference_parent(reference_path: Path, reference_root: Path) -> None:
    """Confine the nearest existing ancestor before mkdir can follow symlinks."""
    existing = reference_path.parent
    while not (existing.exists() or existing.is_symlink()):
        if existing == existing.parent:
            raise AdoptError(
                f"reference parent has no existing ancestor: {reference_path}"
            )
        existing = existing.parent
    _relative_path(existing.resolve(), reference_root.resolve(), "reference parent")


def _validate_live_parent(live_path: Path, home: Path) -> None:
    """Refuse live paths whose parent chain escapes home through a symlink.

    Leaf symlinks are mirrored as symlinks, but a symlinked parent directory
    would make the copy read content from outside $HOME into tracked data.
    Restore applies the same confinement in the opposite direction.
    """
    existing = live_path.parent
    while not (existing.exists() or existing.is_symlink()):
        if existing == existing.parent:
            raise AdoptError(f"live parent has no existing ancestor: {live_path}")
        existing = existing.parent
    _relative_path(existing.resolve(), home.resolve(), "live parent")


def _copy_live_into_reference(live_path: Path, reference_path: Path) -> None:
    if live_path.is_dir() and not live_path.is_symlink():
        with tempfile.TemporaryDirectory(
            dir=reference_path.parent,
            prefix=".adopt-",
        ) as staging:
            staged = Path(staging) / reference_path.name
            # symlinks=True mirrors the live tree instead of materializing
            # link targets (possibly outside $HOME) into tracked data.
            shutil.copytree(live_path, staged, symlinks=True)
            if reference_path.is_dir() and not reference_path.is_symlink():
                shutil.rmtree(reference_path)
            elif reference_path.exists() or reference_path.is_symlink():
                reference_path.unlink()
            staged.rename(reference_path)
        return
    descriptor = tempfile.NamedTemporaryFile(
        dir=reference_path.parent,
        prefix=".adopt-",
        delete=False,
    )
    descriptor.close()
    staged_file = Path(descriptor.name)
    try:
        if live_path.is_symlink():
            staged_file.unlink()
            staged_file.symlink_to(os.readlink(live_path))
        else:
            shutil.copy2(live_path, staged_file)
        if reference_path.is_dir() and not reference_path.is_symlink():
            shutil.rmtree(reference_path)
        staged_file.replace(reference_path)
    except OSError:
        staged_file.unlink(missing_ok=True)
        raise


def apply_adopt(repo_root: Path, home: Path, plan: AdoptReport) -> AdoptReport:
    """Copy live truth into the reference; git history protects the old state."""
    reference_root = repo_root / "reference"
    try:
        dirty = _dirty_reference_paths(repo_root, plan)
    except AdoptError as error:
        dirty_error = str(error)
        return AdoptReport(
            application=plan.application,
            apply=True,
            results=tuple(
                AdoptResult(
                    result.drift, result.action, AdoptStatus.FAILED, dirty_error
                )
                if result.status is AdoptStatus.PLANNED
                else result
                for result in plan.results
            ),
        )
    if dirty:
        summary = ", ".join(sorted(dirty))
        precondition = (
            f"reference paths have uncommitted changes; commit them first: {summary}"
        )
        return AdoptReport(
            application=plan.application,
            apply=True,
            results=tuple(
                AdoptResult(
                    result.drift, result.action, AdoptStatus.FAILED, precondition
                )
                if result.status is AdoptStatus.PLANNED
                else result
                for result in plan.results
            ),
        )

    results = []
    for planned in plan.results:
        if planned.status is not AdoptStatus.PLANNED:
            results.append(planned)
            continue
        drift = planned.drift
        try:
            _relative_path(drift.reference_path, reference_root, "reference path")
            _relative_path(drift.live_path, home, "live path")
            _validate_reference_parent(drift.reference_path, reference_root)
            if planned.action == "copy":
                if not (drift.live_path.exists() or drift.live_path.is_symlink()):
                    raise AdoptError(f"live path does not exist: {drift.live_path}")
                _validate_live_parent(drift.live_path, home)
                drift.reference_path.parent.mkdir(parents=True, exist_ok=True)
            _relative_path(
                drift.reference_path.parent.resolve(),
                reference_root.resolve(),
                "reference parent",
            )
            if planned.action == "copy":
                _copy_live_into_reference(drift.live_path, drift.reference_path)
            elif (
                drift.reference_path.is_dir() and not drift.reference_path.is_symlink()
            ):
                shutil.rmtree(drift.reference_path)
            else:
                drift.reference_path.unlink(missing_ok=True)
        except (OSError, AdoptError) as error:
            results.append(
                AdoptResult(
                    drift,
                    action=planned.action,
                    status=AdoptStatus.FAILED,
                    error=str(error),
                ),
            )
            continue
        results.append(
            AdoptResult(drift, action=planned.action, status=AdoptStatus.APPLIED),
        )
    return AdoptReport(application=plan.application, apply=True, results=tuple(results))


def _document(report: AdoptReport) -> dict[str, object]:
    summary = {
        status.value: sum(result.status is status for result in report.results)
        for status in AdoptStatus
        if any(result.status is status for result in report.results)
    }
    return {
        "schema_version": 1,
        "operation": "adopt",
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
                "error": result.error,
            }
            for result in report.results
        ],
        "summary": summary,
    }


def _render(report: AdoptReport) -> None:
    for result in report.results:
        label = result.status.value.upper()
        print(f"{label:7} {result.drift.reference_path}")
        print(f"        live: {result.drift.live_path}")
        if result.action:
            print(f"        action: {result.action}")
        if result.error:
            print(f"        error: {result.error}", file=sys.stderr)
    if not report.apply:
        print(
            "No files changed. Re-run with --apply to adopt this application's"
            " live configuration.",
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Adopt one application's live configuration into the reference.",
    )
    parser.add_argument(
        "application",
        help="configured application whose live files should be adopted",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="copy live truth into the reference (default: preview only)",
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
        report = plan_adopt(repo_root, Path.home(), args.application)
    except (DriftProtocolError, MackupCommandError) as error:
        emit_error("adopt", str(error), as_json=args.as_json)
        return 1
    if args.apply:
        report = apply_adopt(repo_root, Path.home(), report)
    if args.as_json:
        print(json.dumps(_document(report), indent=2, sort_keys=True))
        for result in report.results:
            if result.status is AdoptStatus.FAILED:
                print(
                    f"[{report.application}] FAIL {result.drift.reference_path}: {result.error}",
                    file=sys.stderr,
                )
    else:
        _render(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
