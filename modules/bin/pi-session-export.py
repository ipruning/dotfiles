#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Export Pi HTML or session JSONL to raw and turns-with-tools JSONL."""

from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

SESSION_DATA_RE = re.compile(
    r'<script\s+id="session-data"\s+type="application/json">(.*?)</script>', re.DOTALL
)


@dataclass
class ToolCallPreview:
    id: str | None = None
    name: str | None = None
    arguments_chars: int = 0
    arguments_preview: str = ""
    command_preview: str | None = None
    partial_json_preview: str | None = None


@dataclass
class TurnMessage:
    role: Literal["user", "assistant"]
    id: str | None = None
    parentId: str | None = None
    timestamp: str | None = None
    text: str = ""
    tool_calls: list[ToolCallPreview] = field(default_factory=list)


@dataclass
class TurnRecord:
    turn: int
    messages: list[TurnMessage]


def read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    records = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSONL line: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{lineno}: expected JSON object line")
        records.append(value)
    if not records:
        raise ValueError(f"{path}: empty JSONL")
    return records


def parse_html_to_records(path: Path) -> tuple[list[dict[str, Any]], str]:
    match = SESSION_DATA_RE.search(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"{path}: session-data block not found")
    try:
        data = json.loads(base64.b64decode(match.group(1).strip()).decode())
    except Exception as exc:
        raise ValueError(f"{path}: invalid session-data payload") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: decoded session-data must be a JSON object")
    header, entries = data.get("header"), data.get("entries")
    if not isinstance(header, dict) or not isinstance(entries, list):
        raise ValueError(f"{path}: decoded session JSON must contain object 'header' and array 'entries'")
    if not all(isinstance(entry, dict) for entry in entries):
        raise ValueError(f"{path}: decoded session entries must be JSON objects")
    return [header, *entries], str(header.get("id") or path.stem)


def infer_session_id(records: list[dict[str, Any]], fallback: str) -> str:
    for record in records[:8]:
        if record.get("type") in {"session", "header"} and isinstance(record.get("id"), str):
            return record["id"].strip() or fallback
    for record in records:
        if isinstance(record.get("id"), str) and record["id"].strip():
            return record["id"].strip()
    return fallback


def extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    return "\n".join(
        block["text"] for block in content
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
    ).strip()


def extract_tools(content: Any) -> list[ToolCallPreview]:
    calls = []
    for block in content if isinstance(content, list) else []:
        if not isinstance(block, dict) or block.get("type") != "toolCall":
            continue
        arguments = block.get("arguments")
        raw = json.dumps(arguments, ensure_ascii=False, default=str)
        calls.append(ToolCallPreview(
            id=block.get("id"), name=block.get("name"), arguments_chars=len(raw),
            arguments_preview=raw[:240],
            command_preview=arguments.get("command", "")[:240] if isinstance(arguments, dict) and isinstance(arguments.get("command"), str) else None,
            partial_json_preview=str(block["partialJson"])[:240] if block.get("partialJson") is not None else None,
        ))
    return calls


def records_to_turns_with_tools(records: list[dict[str, Any]]) -> list[TurnRecord]:
    turns: list[TurnRecord] = []
    for record in records:
        message = record.get("message")
        if record.get("type") != "message" or not isinstance(message, dict):
            continue
        role = message.get("role")
        if role not in {"user", "assistant"}:
            continue
        item = TurnMessage(role=role, id=record.get("id"), parentId=record.get("parentId"),
            timestamp=record.get("timestamp"), text=extract_text(message.get("content")),
            tool_calls=extract_tools(message.get("content")) if role == "assistant" else [])
        if role == "user" or not turns:
            turns.append(TurnRecord(len(turns) + 1, [item]))
        else:
            turns[-1].messages.append(item)
    return turns


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [clean(item) for item in value]
    return value


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(clean(row), ensure_ascii=False) for row in rows) + "\n")


def convert(input_path: Path, output_dir: Path | None, stem: str | None) -> None:
    input_path = input_path.expanduser().resolve()
    if not input_path.is_file():
        raise ValueError(f"{input_path}: file not found")
    out = output_dir.expanduser().resolve() if output_dir else input_path.parent
    out.mkdir(parents=True, exist_ok=True)
    if input_path.suffix.lower() == ".html":
        source, (records, session_id) = "html", parse_html_to_records(input_path)
    elif input_path.suffix.lower() == ".jsonl":
        source, records = "jsonl", read_jsonl_records(input_path)
        session_id = infer_session_id(records, input_path.stem)
    else:
        raise ValueError("input must be .html or .jsonl")
    raw_path = out / f"{stem or session_id}.jsonl"
    turns_path = out / f"{stem or session_id}.turns.with-tools.jsonl"
    if source == "jsonl" and input_path != raw_path:
        shutil.copyfile(input_path, raw_path)
    elif source == "html":
        write_jsonl(raw_path, records)
    turns = records_to_turns_with_tools(records)
    write_jsonl(turns_path, [asdict(turn) for turn in turns])
    users = sum(msg.role == "user" for turn in turns for msg in turn.messages)
    assistants = sum(msg.role == "assistant" for turn in turns for msg in turn.messages)
    tools = sum(len(msg.tool_calls) for turn in turns for msg in turn.messages)
    print(f"status: ok\nsource: {source}\nraw: {raw_path}\nturns_with_tools: {turns_path}\nturns: {len(turns)}\nuser messages: {users}\nassistant messages: {assistants}\ntool calls: {tools}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pi session export utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)
    command = subparsers.add_parser("convert", help="Convert a Pi session export")
    command.add_argument("input_path", type=Path)
    command.add_argument("-o", "--output-dir", type=Path)
    command.add_argument("--stem")
    args = parser.parse_args()
    try:
        convert(args.input_path, args.output_dir, args.stem)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
