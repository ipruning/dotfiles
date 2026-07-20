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


# Rendering/summary label for a finding whose check did not apply to this host.
NOT_APPLICABLE = "skipped"


class FileKind(StrEnum):
    FILE = "file"
    DIRECTORY = "directory"
    LINK = "link"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class Finding:
    check: str
    # None severity means the check did not apply to this host (no zsh,
    # launchctl on Linux, macOS-only path). It is not assessed, so it never
    # gates and always renders loudly under the NOT_APPLICABLE label.
    severity: Severity | None
    code: str
    message: str
    path: Path | None = None
    action: str | None = None

    @property
    def applicable(self) -> bool:
        return self.severity is not None

    @property
    def label(self) -> str:
        return self.severity.value if self.severity is not None else NOT_APPLICABLE


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
