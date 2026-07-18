"""Shared result models for repository inspection tasks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .profiles import HostProfile

ExecutableFinder = Callable[[str], str | None]


class DriftKind(StrEnum):
    MODIFIED = "modified"
    ONLY_REFERENCE = "only-reference"
    ONLY_LIVE = "only-live"
    TYPE_CHANGED = "type-changed"
    UNREADABLE = "unreadable"


class Severity(StrEnum):
    OK = "ok"
    WARN = "warn"
    ERROR = "error"
    # TODO(cleanup): trigger=fact:finding schema_version is bumped beyond 1; action=move SKIPPED out of Severity into an applicability field
    SKIPPED = "skipped"


class FileKind(StrEnum):
    FILE = "file"
    DIRECTORY = "directory"
    LINK = "link"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class Finding:
    check: str
    severity: Severity
    code: str
    message: str
    path: Path | None = None
    action: str | None = None


@dataclass(frozen=True)
class FindingReport:
    schema_version: int
    findings: tuple[Finding, ...]

    def is_ok(self, *, strict: bool = False) -> bool:
        failing = {Severity.ERROR}
        if strict:
            failing.add(Severity.WARN)
        return all(finding.severity not in failing for finding in self.findings)


@dataclass(frozen=True)
class CheckReport(FindingReport):
    profile: HostProfile


@dataclass(frozen=True)
class LintReport(FindingReport):
    pass


@dataclass(frozen=True)
class Drift:
    application: str
    reference_path: Path
    live_path: Path
    kind: DriftKind
    reference_kind: FileKind | None
    live_kind: FileKind | None
    error: str | None = None


@dataclass(frozen=True)
class DriftReport:
    schema_version: int
    operation: str
    changes: tuple[Drift, ...]
    summary: dict[str, int]
    profile: HostProfile = HostProfile.FULL

    @property
    def ok(self) -> bool:
        return all(change.kind is not DriftKind.UNREADABLE for change in self.changes)
