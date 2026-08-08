#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["autocorrect-py==2.14.0"]
# ///
"""Format Chinese plain text. This command is not Markdown-safe."""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import autocorrect_py

_CJK_PUNCT = set("，。！？：；「」『』《》【】（）")
_BLANK_SEP_RE = re.compile(r"(\n[ \t]*\n+)")


def _has_cjk_context(text: str) -> bool:
    return any(
        ch in _CJK_PUNCT
        or 0x3400 <= ord(ch) <= 0x4DBF
        or 0x4E00 <= ord(ch) <= 0x9FFF
        or 0xF900 <= ord(ch) <= 0xFAFF
        or 0x20000 <= ord(ch) <= 0x2EBEF
        for ch in text
    )


def _is_wordish(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def _looks_like_apostrophe(text: str, index: int) -> bool:
    previous = text[index - 1] if index else ""
    following = text[index + 1] if index + 1 < len(text) else ""
    if previous and following and _is_wordish(previous) and _is_wordish(following):
        return True
    return bool(
        following
        and following.isdigit()
        and (
            not previous
            or previous.isspace()
            or unicodedata.category(previous).startswith("P")
        )
    )


def _convert_quotes(text: str, ascii_double: bool) -> str:
    text = text.replace("“", "「").replace("”", "」")
    output: list[str] = []
    in_single = False
    open_double = True
    for index, char in enumerate(text):
        if char == "‘":
            output.append("『")
            in_single = True
        elif char == "’" and in_single and not _looks_like_apostrophe(text, index):
            output.append("』")
            in_single = False
        elif char == '"' and ascii_double:
            output.append("「" if open_double else "」")
            open_double = not open_double
        else:
            output.append(char)
    return "".join(output)


@dataclass
class Options:
    autocorrect: bool = True
    ascii_double: bool = False
    all_text: bool = False


def format_text(text: str, options: Options) -> str:
    output: list[str] = []
    for part in _BLANK_SEP_RE.split(text):
        if (
            not part
            or _BLANK_SEP_RE.fullmatch(part)
            or (not options.all_text and not _has_cjk_context(part))
        ):
            output.append(part)
        else:
            formatted = autocorrect_py.format(part) if options.autocorrect else part
            output.append(_convert_quotes(formatted, options.ascii_double))
    return "".join(output)


def _read_input(files: list[str]) -> str:
    if not files:
        if sys.stdin.isatty():
            raise SystemExit("No input. Pipe plain text via stdin, or pass file paths.")
        return sys.stdin.read()
    return "".join(
        sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
        for path in files
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Format Chinese plain text (spacing and quotes). Not Markdown-safe."
    )
    parser.add_argument("--no-autocorrect", action="store_true")
    parser.add_argument("--ascii-double", action="store_true")
    parser.add_argument("--all", action="store_true", help="Also process non-Chinese paragraphs")
    parser.add_argument("files", nargs="*", help="Plain-text files; use '-' for stdin")
    args = parser.parse_args()
    options = Options(not args.no_autocorrect, args.ascii_double, args.all)
    sys.stdout.write(format_text(_read_input(args.files), options))


if __name__ == "__main__":
    main()
