#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["tiktoken==0.12.0"]
# ///
"""Count tokens in text using tiktoken (o200k_base encoding).

Usage:
  echo "hello world" | ttok.py
  ttok.py "hello world"
  ttok.py < file.txt
"""

import sys

TOKENIZER = "o200k_base"


def count_tokens_stream(stream) -> int:
    import tiktoken

    enc = tiktoken.get_encoding(TOKENIZER)
    total = 0
    while chunk := stream.read(65536):
        total += len(enc.encode(chunk, disallowed_special=()))
    return total


def count_tokens(text: str) -> int:
    import tiktoken

    enc = tiktoken.get_encoding(TOKENIZER)
    return len(enc.encode(text, disallowed_special=()))


def main() -> None:
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
        print(count_tokens(text))
    elif not sys.stdin.isatty():
        print(count_tokens_stream(sys.stdin))
    else:
        print(__doc__ or "Usage: ttok.py <text> or pipe input", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
