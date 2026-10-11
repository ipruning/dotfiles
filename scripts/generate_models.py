"""Shared contracts for generate operations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .models import Status

Downloader = Callable[[str, int], bytes]
AtomicWriter = Callable[[Path], object]


class GenerateAction(StrEnum):
    GENERATE = "generate"
    CLONE = "clone"
    UPDATE = "update"
    RUN = "run"
    DOWNLOAD = "download"
    REMOVE = "remove"
    VALIDATE = "validate"


@dataclass(frozen=True)
class GenerateSpec:
    name: str
    tool: str | None
    target: Path | None = None
    command: tuple[str, ...] = ()
    source: str | None = None
    revision: str | None = None
    sha256: str | None = None
    entrypoint: str | None = None
    environment: tuple[tuple[str, str], ...] = ()
    timeout_seconds: int = 120


@dataclass(frozen=True)
class ShellInitSpec:
    name: str
    tool: str
    shell: str
    command: tuple[str, ...]
    filename: str


@dataclass(frozen=True)
class GenerateResult:
    spec: GenerateSpec
    status: Status
    action: GenerateAction
    reason: str | None = None
    exit_code: int | None = None


StepCallback = Callable[[GenerateSpec, GenerateAction], None]


@dataclass(frozen=True)
class GenerateReport:
    apply: bool
    results: tuple[GenerateResult, ...]
    generated_root: Path | None = None
    network: bool = True

    @property
    def ok(self) -> bool:
        return all(result.status is not Status.FAILED for result in self.results)
