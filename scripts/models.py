"""Shared result models for read-only repository tasks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


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
    SKIPPED = "skipped"


@dataclass(frozen=True)
class Finding:
    check: str
    severity: Severity
    code: str
    message: str
    path: Path | None = None
    action: str | None = None


@dataclass(frozen=True)
class CheckReport:
    schema_version: int
    findings: tuple[Finding, ...]

    @property
    def ok(self) -> bool:
        return self.is_ok()

    def is_ok(self, *, strict: bool = False) -> bool:
        failing = {Severity.ERROR}
        if strict:
            failing.add(Severity.WARN)
        return all(finding.severity not in failing for finding in self.findings)


@dataclass(frozen=True)
class LintReport:
    schema_version: int
    findings: tuple[Finding, ...]

    @property
    def ok(self) -> bool:
        return self.is_ok()

    def is_ok(self, *, strict: bool = False) -> bool:
        failing = {Severity.ERROR}
        if strict:
            failing.add(Severity.WARN)
        return all(finding.severity not in failing for finding in self.findings)


@dataclass(frozen=True)
class Drift:
    application: str
    reference_path: Path
    live_path: Path
    kind: DriftKind
    reference_kind: str | None
    live_kind: str | None
    error: str | None = None


@dataclass(frozen=True)
class DriftReport:
    schema_version: int
    operation: str
    changes: tuple[Drift, ...]
    summary: dict[str, int]

    @property
    def ok(self) -> bool:
        return all(change.kind is not DriftKind.UNREADABLE for change in self.changes)
