"""Shared contracts for host tool update operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import Status


@dataclass(frozen=True)
class UpdateStep:
    name: str
    tool: str
    command: tuple[str, ...]
    timeout_seconds: int
    path_prepend: tuple[Path, ...] = ()
    environment: tuple[tuple[str, str], ...] = ()
    stdin_text: str | None = None
    failure_note: str | None = None
    cwd: Path | None = None


@dataclass(frozen=True)
class UpdateResult:
    step: UpdateStep
    status: Status
    exit_code: int | None = None
    duration_ms: int | None = None
    reason: str | None = None
    stdout_tail: str | None = None
    stderr_tail: str | None = None


@dataclass(frozen=True)
class UpdateReport:
    apply: bool
    results: tuple[UpdateResult, ...]
    runtime: dict[str, object] | None = None

    @property
    def ok(self) -> bool:
        return all(result.status is not Status.FAILED for result in self.results) and (
            self.runtime is None or bool(self.runtime["ok"])
        )
