"""Inspect configuration drift without changing reference or live files."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Protocol, cast

from .models import Drift, DriftKind, DriftReport

MACKUP_SOURCE = (
    "git+https://github.com/ipruning/mackup@d3fa03a7f1cb3cea7f6e2f14a345c9e02ee921df"
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


class SubprocessMackupRunner:
    """Run the immutable Mackup fork through uv's isolated tool environment."""

    def inspect(
        self,
        repo_root: Path,
        home: Path,
        application: str | None,
    ) -> dict[str, object]:
        command = [
            "uvx",
            "--isolated",
            "--from",
            MACKUP_SOURCE,
            "mackup",
            "--config-file",
            str(repo_root / "mackup/mackup.cfg"),
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
        if completed.returncode != 0 and not completed.stdout:
            detail = completed.stderr.strip() or "Mackup produced no report"
            raise MackupCommandError(f"{' '.join(command)}: {detail}")
        try:
            document = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise MackupCommandError(
                f"Mackup returned invalid JSON: {error}",
            ) from error
        if not isinstance(document, dict):
            raise MackupCommandError("Mackup returned a non-object JSON document")
        return document


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
                reference_kind=_string_or_none(
                    typed_change.get("reference_kind"),
                    "reference_kind",
                ),
                live_kind=_string_or_none(
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
    )


def inspect_drift(
    repo_root: Path,
    home: Path,
    application: str | None = None,
    runner: MackupRunner | None = None,
) -> DriftReport:
    """Return typed, location-only drift from the pinned Mackup fork."""
    active_runner = runner or SubprocessMackupRunner()
    return _parse_document(active_runner.inspect(repo_root, home, application))


def _as_json(report: DriftReport) -> dict[str, object]:
    return {
        "schema_version": report.schema_version,
        "operation": report.operation,
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
    parser.add_argument("application", nargs="?")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    try:
        report = inspect_drift(repo_root, Path.home(), args.application)
    except (DriftProtocolError, MackupCommandError) as error:
        print(f"ERROR diff_failed {error}", file=sys.stderr)
        return 1
    if args.as_json:
        print(json.dumps(_as_json(report), indent=2, sort_keys=True))
    else:
        for change in report.changes:
            print(f"{change.kind.value.upper()} {change.live_path}")
            print(f"  reference: {change.reference_path}")
            if change.error:
                print(f"  error: {change.error}")
        rendered = ", ".join(
            f"{count} {kind}" for kind, count in sorted(report.summary.items())
        )
        print(f"Summary: {rendered or 'no drift'}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
