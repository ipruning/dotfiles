#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["typer>=0.21.1", "pydantic>=2.10.0", "rich>=14.3.2"]
# ///
"""Export Pi session files into two JSONL artifacts.

Outputs:
1) <session-id>.jsonl
   Raw event stream (session/header + entries), preserving original data.

2) <session-id>.turns.with-tools.jsonl
   Multi-turn JSONL (one turn per line), containing user + assistant messages.
   Assistant tool calls are preserved from message.content[type=toolCall].

Supports input:
- Pi exported HTML (contains base64 session payload)
- Raw session JSONL

Examples:
  pi-session-export.py convert ~/Downloads/pi-session-xxx.html
  pi-session-export.py convert ~/Downloads/abc.jsonl -o ~/Downloads

Backward-compatible shortcut (no explicit command):
  pi-session-export.py ~/Downloads/pi-session-xxx.html
"""

from __future__ import annotations

import base64
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Literal

import typer
from pydantic import BaseModel, Field
from rich import box
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Pi session export utilities",
)
console = Console()

SESSION_DATA_RE = re.compile(
    r'<script\s+id="session-data"\s+type="application/json">(.*?)</script>',
    re.S,
)


class ToolCallPreview(BaseModel):
    id: str | None = None
    name: str | None = None
    arguments_chars: int = 0
    arguments_preview: str = ""
    command_preview: str | None = None
    partial_json_preview: str | None = None


class TurnMessage(BaseModel):
    id: str | None = None
    parentId: str | None = None
    timestamp: str | None = None
    role: Literal["user", "assistant"]
    text: str = ""
    tool_calls: list[ToolCallPreview] = Field(default_factory=list)


class TurnRecord(BaseModel):
    turn: int
    messages: list[TurnMessage]


class TurnSummary(BaseModel):
    turns: int
    user_messages: int
    assistant_messages: int
    tool_calls: int


def read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    lines = path.read_text(encoding="utf-8").splitlines()

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSONL line: {exc}") from exc

        if not isinstance(obj, dict):
            raise ValueError(f"{path}:{lineno}: expected JSON object line")

        records.append(obj)

    if not records:
        raise ValueError(f"{path}: empty JSONL")

    return records


def write_dict_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    content = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text(content + "\n", encoding="utf-8")


def write_turns_jsonl(path: Path, turns: list[TurnRecord]) -> None:
    rows = [turn.model_dump(exclude_none=True) for turn in turns]
    write_dict_jsonl(path, rows)


def parse_html_to_records(path: Path) -> tuple[list[dict[str, Any]], str]:
    html = path.read_text(encoding="utf-8")
    match = SESSION_DATA_RE.search(html)
    if not match:
        raise ValueError(f"{path}: session-data block not found")

    b64 = match.group(1).strip()
    try:
        decoded = base64.b64decode(b64)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"{path}: invalid base64 session-data block") from exc

    try:
        data = json.loads(decoded.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"{path}: decoded session-data is not valid JSON") from exc

    if not isinstance(data, dict):
        raise ValueError(f"{path}: decoded session-data must be a JSON object")

    header = data.get("header")
    entries = data.get("entries")
    if not isinstance(header, dict) or not isinstance(entries, list):
        raise ValueError(
            f"{path}: decoded session JSON must contain object 'header' and array 'entries'"
        )

    records: list[dict[str, Any]] = [header] + [e for e in entries if isinstance(e, dict)]
    session_id = str(header.get("id") or path.stem)
    return records, session_id


def infer_session_id(records: list[dict[str, Any]], fallback: str) -> str:
    for rec in records[:8]:
        kind = rec.get("type")
        sid = rec.get("id")
        if kind in {"session", "header"} and isinstance(sid, str) and sid.strip():
            return sid.strip()

    for rec in records:
        sid = rec.get("id")
        if isinstance(sid, str) and sid.strip():
            return sid.strip()

    return fallback


def parse_jsonl_to_records(path: Path) -> tuple[list[dict[str, Any]], str]:
    records = read_jsonl_records(path)
    return records, infer_session_id(records, path.stem)


def extract_text_from_blocks(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if not isinstance(content, list):
        return ""

    chunks: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            chunks.append(block["text"])

    return "\n".join(chunks).strip()


def extract_tool_calls_from_blocks(content: Any) -> list[ToolCallPreview]:
    if not isinstance(content, list):
        return []

    calls: list[ToolCallPreview] = []

    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "toolCall":
            continue

        arguments = block.get("arguments")
        try:
            arguments_raw = json.dumps(arguments, ensure_ascii=False)
        except Exception:  # noqa: BLE001
            arguments_raw = str(arguments)

        payload = {
            "id": block.get("id"),
            "name": block.get("name"),
            "arguments_chars": len(arguments_raw),
            "arguments_preview": arguments_raw[:240],
        }

        if isinstance(arguments, dict) and isinstance(arguments.get("command"), str):
            payload["command_preview"] = arguments["command"][:240]

        if block.get("partialJson") is not None:
            payload["partial_json_preview"] = str(block.get("partialJson"))[:240]

        calls.append(ToolCallPreview(**payload))

    return calls


def normalize_message(record: dict[str, Any]) -> TurnMessage | None:
    if record.get("type") != "message":
        return None

    message = record.get("message")
    if not isinstance(message, dict):
        return None

    role = message.get("role")
    if role not in {"user", "assistant"}:
        return None

    content = message.get("content")

    return TurnMessage(
        id=record.get("id"),
        parentId=record.get("parentId"),
        timestamp=record.get("timestamp"),
        role=role,
        text=extract_text_from_blocks(content),
        tool_calls=extract_tool_calls_from_blocks(content) if role == "assistant" else [],
    )


def records_to_turns_with_tools(records: list[dict[str, Any]]) -> list[TurnRecord]:
    messages = [m for rec in records if (m := normalize_message(rec)) is not None]

    turns: list[TurnRecord] = []

    for msg in messages:
        if msg.role == "user":
            turns.append(TurnRecord(turn=len(turns) + 1, messages=[msg]))
            continue

        if not turns:
            turns.append(TurnRecord(turn=1, messages=[msg]))
            continue

        turns[-1].messages.append(msg)

    return turns


def summarize_turns(turns: list[TurnRecord]) -> TurnSummary:
    users = 0
    assistants = 0
    tool_calls = 0

    for turn in turns:
        for msg in turn.messages:
            if msg.role == "user":
                users += 1
            else:
                assistants += 1
                tool_calls += len(msg.tool_calls)

    return TurnSummary(
        turns=len(turns),
        user_messages=users,
        assistant_messages=assistants,
        tool_calls=tool_calls,
    )


def format_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024

    return f"{int(size)} B"


def print_report(
    source_kind: str,
    input_path: Path,
    raw_path: Path,
    turns_path: Path,
    summary: TurnSummary,
) -> None:
    source_table = Table(title="pi-session-export", box=box.ASCII)
    source_table.add_column("Field", style="cyan", no_wrap=True)
    source_table.add_column("Value", overflow="fold")
    source_table.add_row("status", "ok")
    source_table.add_row("source", source_kind)
    source_table.add_row("input", str(input_path))

    outputs_table = Table(title="outputs", box=box.ASCII)
    outputs_table.add_column("artifact", style="cyan", no_wrap=True)
    outputs_table.add_column("path", overflow="fold")
    outputs_table.add_column("size", justify="right", no_wrap=True)
    outputs_table.add_row("raw", str(raw_path), format_bytes(raw_path.stat().st_size))
    outputs_table.add_row(
        "turns_with_tools",
        str(turns_path),
        format_bytes(turns_path.stat().st_size),
    )

    summary_table = Table(title="summary", box=box.ASCII)
    summary_table.add_column("metric", style="cyan", no_wrap=True)
    summary_table.add_column("value", justify="right")
    summary_table.add_row("turns", str(summary.turns))
    summary_table.add_row("user messages", str(summary.user_messages))
    summary_table.add_row("assistant messages", str(summary.assistant_messages))
    summary_table.add_row("tool calls", str(summary.tool_calls))

    console.print(source_table)
    console.print(outputs_table)
    console.print(summary_table)


def write_raw_output(
    source_kind: str,
    input_path: Path,
    output_path: Path,
    records: list[dict[str, Any]],
) -> None:
    if source_kind == "jsonl":
        if input_path.resolve() != output_path.resolve():
            shutil.copyfile(input_path, output_path)
        return

    write_dict_jsonl(output_path, records)


@app.callback()
def root() -> None:
    """Pi session export CLI."""


@app.command("convert")
def convert(
    input_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to pi-session HTML or session JSONL",
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Output directory (default: same dir as input)",
    ),
    stem: str | None = typer.Option(
        None,
        "--stem",
        help="Override output stem/session id",
    ),
) -> None:
    """Convert input into raw JSONL + turns-with-tools JSONL."""

    out_dir = output_dir.expanduser().resolve() if output_dir else input_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    suffix = input_path.suffix.lower()
    if suffix == ".html":
        source_kind = "html"
        records, inferred_session_id = parse_html_to_records(input_path)
    elif suffix == ".jsonl":
        source_kind = "jsonl"
        records, inferred_session_id = parse_jsonl_to_records(input_path)
    else:
        raise typer.BadParameter("input must be .html or .jsonl")

    session_id = stem or inferred_session_id
    raw_path = out_dir / f"{session_id}.jsonl"
    turns_path = out_dir / f"{session_id}.turns.with-tools.jsonl"

    write_raw_output(source_kind, input_path, raw_path, records)
    turns = records_to_turns_with_tools(records)
    write_turns_jsonl(turns_path, turns)
    summary = summarize_turns(turns)

    print_report(source_kind, input_path, raw_path, turns_path, summary)


def main() -> None:
    # Backward compatibility: allow `pi-session-export.py <input>` by injecting
    # default command when first arg looks like a positional input path.
    if len(sys.argv) > 1:
        first = sys.argv[1]
        known = {"convert", "--help", "-h", "--version"}
        if first not in known and not first.startswith("-"):
            sys.argv.insert(1, "convert")

    app()


if __name__ == "__main__":
    main()
