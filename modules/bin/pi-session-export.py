#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# ///
"""Export Pi sessions into two JSONL artifacts only.

Outputs:
1) <session-id>.jsonl
   Raw event stream (session/header + entries), preserving original data.

2) <session-id>.turns.with-tools.jsonl
   Multi-turn JSONL, each line one turn, containing user + assistant messages.
   Assistant tool calls are preserved from message.content[type=toolCall].

Usage:
  pi-session-export.py /path/to/pi-session-xxx.html
  pi-session-export.py /path/to/session.jsonl
  pi-session-export.py /path/to/session.jsonl -o /tmp/out
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

SESSION_DATA_RE = re.compile(
    r'<script\s+id="session-data"\s+type="application/json">(.*?)</script>',
    re.S,
)

VALID_ROLES = {"user", "assistant"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    content = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text(content + "\n", encoding="utf-8")


def extract_session_from_html(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    text = path.read_text(encoding="utf-8")
    match = SESSION_DATA_RE.search(text)
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

    dict_entries = [e for e in entries if isinstance(e, dict)]
    return header, dict_entries


def infer_session_id(records: list[dict[str, Any]], fallback: str) -> str:
    for rec in records[:5]:
        t = rec.get("type")
        sid = rec.get("id")
        if t in {"session", "header"} and isinstance(sid, str) and sid.strip():
            return sid.strip()

    for rec in records:
        sid = rec.get("id")
        if isinstance(sid, str) and sid.strip():
            return sid.strip()

    return fallback


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


def extract_tool_calls_from_blocks(content: Any) -> list[dict[str, Any]]:
    if not isinstance(content, list):
        return []

    calls: list[dict[str, Any]] = []
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

        call: dict[str, Any] = {
            "id": block.get("id"),
            "name": block.get("name"),
            "arguments_chars": len(arguments_raw),
            "arguments_preview": arguments_raw[:240],
        }

        if isinstance(arguments, dict) and isinstance(arguments.get("command"), str):
            call["command_preview"] = arguments["command"][:240]

        if block.get("partialJson") is not None:
            partial_raw = str(block.get("partialJson"))
            call["partial_json_preview"] = partial_raw[:240]

        calls.append(call)

    return calls


def normalize_message_event(record: dict[str, Any]) -> dict[str, Any] | None:
    if record.get("type") != "message":
        return None

    msg = record.get("message")
    if not isinstance(msg, dict):
        return None

    role = msg.get("role")
    if role not in VALID_ROLES:
        return None

    event: dict[str, Any] = {
        "id": record.get("id"),
        "parentId": record.get("parentId"),
        "timestamp": record.get("timestamp"),
        "role": role,
        "text": extract_text_from_blocks(msg.get("content")),
    }

    if role == "assistant":
        tool_calls = extract_tool_calls_from_blocks(msg.get("content"))
        if tool_calls:
            event["tool_calls"] = tool_calls

    return event


def extract_message_events(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for rec in records:
        event = normalize_message_event(rec)
        if event is not None:
            events.append(event)
    return events


def build_turns_with_tools(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []

    for event in events:
        role = event.get("role")

        if role == "user":
            turns.append({"turn": len(turns) + 1, "messages": [event]})
            continue

        if not turns:
            turns.append({"turn": 1, "messages": [event]})
            continue

        turns[-1]["messages"].append(event)

    return turns


def summarize_turns(turns: list[dict[str, Any]]) -> tuple[int, int, int, int]:
    users = 0
    assistants = 0
    tool_calls = 0

    for turn in turns:
        for msg in turn.get("messages", []):
            role = msg.get("role")
            if role == "user":
                users += 1
            elif role == "assistant":
                assistants += 1
                tool_calls += len(msg.get("tool_calls") or [])

    return len(turns), users, assistants, tool_calls


def format_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    unit = units[0]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            break
        value /= 1024
    if unit == "B":
        return f"{int(value)} {unit}"
    return f"{value:.1f} {unit}"


def print_report(
    source_kind: str,
    input_path: Path,
    raw_path: Path,
    turns_path: Path,
    summary: tuple[int, int, int, int],
) -> None:
    turns_n, users_n, assistants_n, tool_calls_n = summary
    raw_size = format_bytes(raw_path.stat().st_size)
    turns_size = format_bytes(turns_path.stat().st_size)

    print("✅ pi-session-export complete")
    print(f"  source   : {source_kind}  {input_path}")
    print("  outputs  :")
    print(f"    - raw   : {raw_path} ({raw_size})")
    print(f"    - turns : {turns_path} ({turns_size})")
    print("  summary  :")
    print(f"    - turns          : {turns_n}")
    print(f"    - user messages  : {users_n}")
    print(f"    - assistant msgs : {assistants_n}")
    print(f"    - tool calls     : {tool_calls_n}")


def export_from_html(
    input_path: Path,
    output_dir: Path,
    stem: str | None,
) -> tuple[Path, Path, tuple[int, int, int, int]]:
    header, entries = extract_session_from_html(input_path)
    session_id = stem or str(header.get("id") or input_path.stem)

    raw_jsonl_path = output_dir / f"{session_id}.jsonl"
    raw_records = [header] + entries
    write_jsonl(raw_jsonl_path, raw_records)

    events = extract_message_events(raw_records)
    turns = build_turns_with_tools(events)

    turns_jsonl_path = output_dir / f"{session_id}.turns.with-tools.jsonl"
    write_jsonl(turns_jsonl_path, turns)

    summary = summarize_turns(turns)
    return raw_jsonl_path, turns_jsonl_path, summary


def export_from_jsonl(
    input_path: Path,
    output_dir: Path,
    stem: str | None,
) -> tuple[Path, Path, tuple[int, int, int, int]]:
    records = read_jsonl(input_path)
    session_id = stem or infer_session_id(records, input_path.stem)

    raw_jsonl_path = output_dir / f"{session_id}.jsonl"

    if input_path.resolve() != raw_jsonl_path.resolve():
        shutil.copyfile(input_path, raw_jsonl_path)

    events = extract_message_events(records)
    turns = build_turns_with_tools(events)

    turns_jsonl_path = output_dir / f"{session_id}.turns.with-tools.jsonl"
    write_jsonl(turns_jsonl_path, turns)

    summary = summarize_turns(turns)
    return raw_jsonl_path, turns_jsonl_path, summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Pi session HTML/JSONL into raw JSONL + turns-with-tools JSONL"
    )
    parser.add_argument("input", help="Path to pi-session HTML file or session JSONL file")
    parser.add_argument(
        "-o",
        "--output-dir",
        help="Output directory (default: same dir as input)",
    )
    parser.add_argument(
        "--stem",
        help="Override output stem/session id (default: inferred from session/header id)",
    )

    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists() or not input_path.is_file():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else input_path.parent
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        suffix = input_path.suffix.lower()
        if suffix == ".html":
            raw_path, turns_path, summary = export_from_html(input_path, output_dir, args.stem)
            source_kind = "html"
        elif suffix == ".jsonl":
            raw_path, turns_path, summary = export_from_jsonl(input_path, output_dir, args.stem)
            source_kind = "jsonl"
        else:
            raise ValueError("input must be .html or .jsonl")
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print_report(source_kind, input_path, raw_path, turns_path, summary)


if __name__ == "__main__":
    main()
