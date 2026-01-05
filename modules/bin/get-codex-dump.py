#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["typer==0.21.0"]
# ///
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer


@dataclass
class ParseError:
    path: Path
    reason: str


@dataclass
class ParseResult:
    path: Path
    items: list[str]


def format_tag(tag: str, content: str, **attrs: str) -> str:
    attr_str = " ".join(f'{k}="{v}"' for k, v in attrs.items() if v)
    opening = f"<{tag} {attr_str}>" if attr_str else f"<{tag}>"
    return f"{opening}\n{content}\n</{tag}>\n"


def extract_message_text(content: list[dict]) -> str:
    parts = []
    for item in content:
        if item.get("type") == "input_text":
            parts.append(item.get("text", ""))
    return "\n".join(parts)


def format_response_item(payload: dict) -> str | None:
    ptype = payload.get("type")

    match ptype:
        case "message":
            role = payload.get("role", "")
            content = payload.get("content", [])
            text = (
                extract_message_text(content)
                if isinstance(content, list)
                else str(content)
            )
            if not text.strip():
                return None
            return format_tag(f"message_{role}", text)

        case "reasoning":
            summary = payload.get("summary", [])
            text = "\n".join(s.get("text", "") for s in summary if s.get("text"))
            if not text:
                return None
            return format_tag("reasoning", text)

        case "function_call":
            return format_tag(
                "function_call",
                payload.get("arguments", ""),
                name=payload.get("name", ""),
                call_id=payload.get("call_id", ""),
            )

        # case "function_call_output":
        #     return format_tag(
        #         "function_call_output",
        #         payload.get("output", ""),
        #         call_id=payload.get("call_id", ""),
        #     )

        case _:
            return None


def parse_file(path: Path) -> ParseResult | ParseError:
    if not path.exists():
        return ParseError(path, "file not found")
    if not path.is_file():
        return ParseError(path, "not a file")

    try:
        text = path.read_text()
    except OSError as e:
        return ParseError(path, str(e))

    results = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        if data.get("type") != "response_item":
            continue

        payload = data.get("payload", {})
        if formatted := format_response_item(payload):
            results.append(formatted)

    return ParseResult(path, results)


def resolve_input(path: Path) -> list[Path] | ParseError:
    if not path.exists():
        return ParseError(path, "path not found")

    if path.is_file():
        return [path]

    if path.is_dir():
        files = sorted(path.glob("*.jsonl"))
        if not files:
            return ParseError(path, "no .jsonl files in directory")
        return files

    return ParseError(path, "not a file or directory")


def main(
    path: Annotated[
        Path,
        typer.Argument(help="Path to JSONL file or directory containing .jsonl files"),
    ],
    output: Annotated[
        Path | None,
        typer.Option("-o", "--output", help="Output file path. Defaults to stdout."),
    ] = None,
) -> None:
    """Export Codex CLI session logs to readable XML format."""
    resolved = resolve_input(path)
    if isinstance(resolved, ParseError):
        typer.echo(f"Error: {resolved.path}: {resolved.reason}", err=True)
        raise typer.Exit(1)

    all_items: list[str] = []
    for file_path in resolved:
        result = parse_file(file_path)
        if isinstance(result, ParseError):
            typer.echo(f"Warning: {result.path}: {result.reason}", err=True)
            continue
        all_items.extend(result.items)

    if not all_items:
        typer.echo("No response items found.", err=True)
        raise typer.Exit(1)

    result = "\n".join(all_items)
    if output:
        output.write_text(result)
        typer.echo(f"Exported to {output}", err=True)
    else:
        sys.stdout.write(result)


if __name__ == "__main__":
    typer.run(main)
