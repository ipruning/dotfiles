"""Inspect configuration drift without changing reference or live files."""

from __future__ import annotations

import argparse
import json
import os
import signal
import stat
import sys
from collections import Counter
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import current_thread, main_thread

from .mappings import (
    MappingError,
    application_config_path,
    read_application_mapping,
    read_mapping_config,
    selected_applications,
)
from .models import Drift, DriftKind, DriftReport, FileKind
from .profiles import HostProfile, profile_applications, resolve_profile
from .render import emit_error

DRIFT_TIMEOUT_SECONDS = 180


@contextmanager
def _scan_timeout() -> Generator[None]:
    if current_thread() is not main_thread() or any(
        signal.getitimer(signal.ITIMER_REAL)
    ):
        yield
        return

    def timed_out(_signum: int, _frame: object) -> None:
        raise MappingError(
            f"Configuration drift inspection timed out after {DRIFT_TIMEOUT_SECONDS}s"
        )

    previous_handler = signal.signal(signal.SIGALRM, timed_out)
    try:
        signal.setitimer(signal.ITIMER_REAL, DRIFT_TIMEOUT_SECONDS)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def _kind(path: Path) -> FileKind | None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(mode):
        return FileKind.LINK
    if stat.S_ISREG(mode):
        return FileKind.FILE
    if stat.S_ISDIR(mode):
        return FileKind.DIRECTORY
    return FileKind.UNSUPPORTED


def _compare(application: str, reference: Path, live: Path) -> Iterator[Drift]:
    reference_kind = live_kind = None
    try:
        reference_kind = _kind(reference)
        live_kind = _kind(live)
        if (
            reference_kind in {FileKind.FILE, FileKind.DIRECTORY}
            and live_kind is FileKind.LINK
        ):
            try:
                if live.samefile(reference):
                    return
            except FileNotFoundError:
                pass
        if reference_kind != live_kind:
            if reference_kind is None:
                kind = DriftKind.ONLY_LIVE
            elif live_kind is None:
                kind = DriftKind.ONLY_REFERENCE
            else:
                kind = DriftKind.TYPE_CHANGED
        elif reference_kind is FileKind.DIRECTORY:
            names = {path.name for path in reference.iterdir()} | {
                path.name for path in live.iterdir()
            }
            for name in sorted(names):
                yield from _compare(application, reference / name, live / name)
            return
        elif (
            reference_kind is FileKind.FILE
            and reference.read_bytes() != live.read_bytes()
        ) or (
            reference_kind is FileKind.LINK and reference.readlink() != live.readlink()
        ):
            kind = DriftKind.MODIFIED
        else:
            return
    except OSError as error:
        yield Drift(
            application,
            reference,
            live,
            DriftKind.UNREADABLE,
            reference_kind,
            live_kind,
            str(error),
        )
    else:
        yield Drift(application, reference, live, kind, reference_kind, live_kind)


@_scan_timeout()
def inspect_drift(
    repo_root: Path,
    home: Path,
    application: str | None = None,
    profile: str | HostProfile = HostProfile.AUTO,
    system_name: str | None = None,
) -> DriftReport:
    """Compare mapped paths and return their locations and kinds."""
    active_profile = resolve_profile(profile, system_name)
    profile_apps = profile_applications(active_profile)
    mapping_root = repo_root / "mackup"
    config = read_mapping_config(mapping_root / "mackup.cfg")
    references = repo_root / "reference"
    if not references.is_dir():
        raise MappingError(f"Reference directory is unavailable: {references}")
    names = [application] if application else selected_applications(config)
    if not names:
        raise MappingError(f"No applications selected in {mapping_root / 'mackup.cfg'}")
    changes = []
    for name in sorted(names):
        if not application and profile_apps is not None and name not in profile_apps:
            continue
        path = application_config_path(mapping_root / "applications", name)
        if not path.is_file():
            raise MappingError(f"Unsupported application: {name}")
        mapping = read_application_mapping(path)
        paths = set(mapping.home_paths)
        if mapping.xdg_paths:
            xdg = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config")))
            if not xdg.is_relative_to(home) or ".." in xdg.parts:
                raise MappingError(f"XDG_CONFIG_HOME must be within {home}: {xdg}")
            paths.update(xdg.relative_to(home) / path for path in mapping.xdg_paths)
        for path in sorted(paths, key=str):
            changes.extend(_compare(name, references / path, home / path))
    counts = Counter(change.kind for change in changes)
    return DriftReport(
        schema_version=1,
        operation="diff",
        changes=tuple(changes),
        summary={kind.value: counts[kind] for kind in DriftKind if counts[kind]},
        profile=active_profile,
    )


def _as_json(report: DriftReport) -> dict[str, object]:
    return {
        "schema_version": report.schema_version,
        "operation": report.operation,
        "ok": report.ok,
        "profile": report.profile.value,
        "changes": [
            {
                "application": change.application,
                "reference_path": str(change.reference_path),
                "live_path": str(change.live_path),
                "kind": change.kind.value,
                "reference_kind": change.reference_kind,
                "live_kind": change.live_kind,
                "error": change.error,
            }
            for change in report.changes
        ],
        "summary": report.summary,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report configuration drift without changing files.",
    )
    parser.add_argument(
        "application", nargs="?", help="limit the report to one configured application"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit the report as JSON on stdout",
    )
    parser.add_argument(
        "--profile",
        choices=[profile.value for profile in HostProfile],
        default=HostProfile.AUTO.value,
        help="host profile that selects which applications to inspect",
    )
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    try:
        report = inspect_drift(
            repo_root, Path.home(), args.application, profile=args.profile
        )
    except MappingError as error:
        emit_error("diff", str(error), as_json=args.as_json)
        return 1
    if args.as_json:
        print(json.dumps(_as_json(report), indent=2, sort_keys=True))
    else:
        print(f"Profile: {report.profile.value}")
        for change in report.changes:
            print(f"{change.kind.value.upper():7} {change.live_path}")
            print(f"        reference: {change.reference_path}")
            if change.error:
                print(f"        error: {change.error}", file=sys.stderr)
        rendered = ", ".join(
            f"{count} {kind}" for kind, count in sorted(report.summary.items())
        )
        print(f"Summary: {rendered or 'no drift'}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
