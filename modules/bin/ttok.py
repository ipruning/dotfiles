#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["tiktoken>=0.12.0"]
# ///
"""Count tokens in text using tiktoken (o200k_base encoding).

Usage:
  echo "hello world" | ttok.py
  p | ttok.py                # clipboard text, or copied file paths
  ttok.py "hello world"
  ttok.py file.txt
  ttok.py < file.txt
"""

import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

TOKENIZER = "o200k_base"
MAX_CLIPBOARD_PATHS = 100


def count_tokens(text: str) -> int:
    import tiktoken

    enc = tiktoken.get_encoding(TOKENIZER)
    return len(enc.encode(text, disallowed_special=()))


def count_file(path: Path) -> int:
    return count_tokens(path.read_text(errors="replace"))


def path_from_clipboard_line(line: str) -> Path:
    if line.startswith("file://"):
        return Path(unquote(urlparse(line).path))
    return Path(line).expanduser()


def paths_from_clipboard_text(text: str) -> list[Path] | None:
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines or len(lines) > MAX_CLIPBOARD_PATHS:
        return None

    paths = [path_from_clipboard_line(line) for line in lines]
    if all(path.is_file() for path in paths):
        return paths
    return None


def main() -> None:
    if len(sys.argv) > 1:
        paths = [Path(arg).expanduser() for arg in sys.argv[1:]]
        if all(path.is_file() for path in paths):
            print(sum(count_file(path) for path in paths))
        else:
            text = " ".join(sys.argv[1:])
            print(count_tokens(text))
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
        if paths := paths_from_clipboard_text(text):
            print(sum(count_file(path) for path in paths))
        else:
            print(count_tokens(text))
    else:
        print(__doc__ or "Usage: ttok.py <text> or pipe input", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
