"""Inspect configuration drift without changing reference or live files."""

from __future__ import annotations

import argparse
import configparser
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Protocol, cast

from .models import Drift, DriftKind, DriftReport, FileKind
from .profiles import HostProfile, profile_applications, resolve_profile
from .render import emit_error

MACKUP_SOURCE = (
    "git+https://github.com/ipruning/mackup@faa5cb8cd0f5fea83711b4fc75a4996d4b8a7497"
)


class DriftProtocolError(ValueError):
    """Mackup returned a document that does not satisfy schema version 1."""


class MackupCommandError(RuntimeError):
    """Mackup could not complete the requested inspection."""


class MackupRunner(Protocol):
    def inspect(
        self,
        repo_root: Path,
        home: Path,
        application: str | None,
    ) -> dict[str, object]: ...


class _CaseConfigParser(configparser.ConfigParser):
    def optionxform(self, optionstr: str) -> str:
        return optionstr


class SubprocessMackupRunner:
    """Run the immutable Mackup fork through uv's isolated tool environment."""

    def inspect(
        self,
        repo_root: Path,
        home: Path,
        application: str | None,
    ) -> dict[str, object]:
        source_config = repo_root / "mackup/mackup.cfg"
        config = _CaseConfigParser(allow_no_value=True, interpolation=None)
        try:
            if not config.read(source_config) or not config.has_section("storage"):
                raise MackupCommandError(f"Invalid Mackup config: {source_config}")
            config.set("storage", "path", str(repo_root))
            with tempfile.TemporaryDirectory(prefix="dotfiles-mackup-") as temp_dir:
                runtime_config = Path(temp_dir) / "mackup.cfg"
                with runtime_config.open("w") as config_file:
                    config.write(config_file)
                command = [
                    "uvx",
                    "--isolated",
                    "--from",
                    MACKUP_SOURCE,
                    "mackup",
                    "--config-file",
                    str(runtime_config),
                    "--applications-dir",
                    str(repo_root / "mackup/applications"),
                    "--json",
                    "diff",
                ]
                if application:
                    command.append(application)
                environment = os.environ.copy()
                environment["HOME"] = str(home)
                completed = subprocess.run(
                    command,
                    cwd=repo_root,
                    env=environment,
                    check=False,
                    capture_output=True,
                    text=True,
                )
        except (configparser.Error, OSError) as error:
            raise MackupCommandError(
                f"Unable to prepare Mackup config {source_config}: {error}",
            ) from error
        if completed.returncode != 0 and not completed.stdout:
            detail = completed.stderr.strip() or "Mackup produced no report"
            raise MackupCommandError(detail)
        try:
            document = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise MackupCommandError(
                f"Mackup returned invalid JSON: {error}",
            ) from error
        if not isinstance(document, dict):
            raise MackupCommandError("Mackup returned a non-object JSON document")
        return document


def _file_kind(value: object, field: str) -> FileKind | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise DriftProtocolError(f"{field} must be a string or null")
    try:
        return FileKind(value)
    except ValueError as error:
        raise DriftProtocolError(f"{field} has unknown file kind {value}") from error


def _string_or_none(value: object, field: str) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise DriftProtocolError(f"{field} must be a string or null")


def _parse_document(document: dict[str, object]) -> DriftReport:
    if document.get("schema_version") != 1:
        raise DriftProtocolError("unsupported Mackup diff schema_version")
    if document.get("operation") != "diff":
        raise DriftProtocolError("Mackup document operation must be diff")
    raw_changes = document.get("changes")
    raw_summary = document.get("summary")
    if not isinstance(raw_changes, list):
        raise DriftProtocolError("changes must be a list")
    if not isinstance(raw_summary, dict):
        raise DriftProtocolError("summary must map strings to integers")
    summary: dict[str, int] = {}
    for key, value in raw_summary.items():
        if not isinstance(key, str) or not isinstance(value, int):
            raise DriftProtocolError("summary must map strings to integers")
        summary[key] = value

    changes: list[Drift] = []
    for index, raw_change in enumerate(raw_changes):
        if not isinstance(raw_change, dict):
            raise DriftProtocolError(f"changes[{index}] must be an object")
        typed_change = cast("dict[str, object]", raw_change)
        try:
            application = typed_change["application"]
            reference_path = typed_change["reference_path"]
            live_path = typed_change["live_path"]
            raw_kind = typed_change["kind"]
        except KeyError as error:
            raise DriftProtocolError(
                f"changes[{index}] is missing {error.args[0]}",
            ) from error
        if not isinstance(application, str):
            raise DriftProtocolError(
                f"changes[{index}] identity fields must be strings",
            )
        if not isinstance(reference_path, str):
            raise DriftProtocolError(
                f"changes[{index}] identity fields must be strings",
            )
        if not isinstance(live_path, str) or not isinstance(raw_kind, str):
            raise DriftProtocolError(
                f"changes[{index}] identity fields must be strings",
            )
        try:
            kind = DriftKind(raw_kind)
        except ValueError as error:
            raise DriftProtocolError(
                f"changes[{index}] has unknown kind {raw_kind}",
            ) from error
        changes.append(
            Drift(
                application=application,
                reference_path=Path(reference_path),
                live_path=Path(live_path),
                kind=kind,
                reference_kind=_file_kind(
                    typed_change.get("reference_kind"),
                    "reference_kind",
                ),
                live_kind=_file_kind(
                    typed_change.get("live_kind"),
                    "live_kind",
                ),
                error=_string_or_none(typed_change.get("error"), "error"),
            ),
        )
    return DriftReport(
        schema_version=1,
        operation="diff",
        changes=tuple(changes),
        summary=summary,
        profile=HostProfile.FULL,
    )


def inspect_drift(
    repo_root: Path,
    home: Path,
    application: str | None = None,
    profile: str | HostProfile = HostProfile.AUTO,
    system_name: str | None = None,
    runner: MackupRunner | None = None,
) -> DriftReport:
    """Return typed, location-only drift from the pinned Mackup fork."""
    active_runner = runner or SubprocessMackupRunner()
    report = _parse_document(active_runner.inspect(repo_root, home, application))
    active_profile = resolve_profile(profile, system_name)
    selected_applications = profile_applications(active_profile)
    changes = report.changes
    if application is None and selected_applications is not None:
        changes = tuple(
            change for change in changes if change.application in selected_applications
        )
    summary = {
        kind.value: sum(change.kind is kind for change in changes)
        for kind in DriftKind
        if any(change.kind is kind for change in changes)
    }
    return DriftReport(
        schema_version=report.schema_version,
        operation=report.operation,
        changes=changes,
        summary=summary,
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
                "reference_kind": (
                    change.reference_kind.value if change.reference_kind else None
                ),
                "live_kind": change.live_kind.value if change.live_kind else None,
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
        "application",
        nargs="?",
        help="limit the report to one configured application",
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
            repo_root,
            Path.home(),
            args.application,
            profile=args.profile,
        )
    except (DriftProtocolError, MackupCommandError) as error:
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
