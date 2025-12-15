#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "argcomplete==3.6.3",
#     "loguru==0.7.3",
#     "tiktoken==0.12.0",
# ]
# ///
# PYTHON_ARGCOMPLETE_OK

import argparse
import json
import os
import sys
from pathlib import Path
from typing import TextIO

import argcomplete
import tiktoken
from loguru import logger


def setup_logger() -> None:
    logger.remove()

    use_color = os.environ.get("NO_COLOR") is None

    logger.add(
        sys.stderr,
        format="<level>{level}</level> | <level>{message}</level>",
        level="INFO",
        colorize=use_color,
    )


def count_tokens(text: str) -> int:
    encoding = tiktoken.encoding_for_model("gpt-4o-mini")
    return len(encoding.encode(text, disallowed_special=()))


def count_tokens_from_stream(stream: TextIO) -> int:
    encoding = tiktoken.encoding_for_model("gpt-4o-mini")
    total_tokens = 0

    content = stream.read()
    if content:
        total_tokens = len(encoding.encode(content, disallowed_special=()))

    return total_tokens


def is_binary_file(file_path: Path) -> bool:
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            return b"\0" in chunk
    except Exception as e:
        logger.error(f"Error checking file type: {e}")
        return True


def count_tokens_from_file(file_path: Path) -> int:
    file_path = Path(file_path)

    if not file_path.exists():
        logger.error(f"{file_path} does not exist. Please provide a valid file path.")
        return 0

    if is_binary_file(file_path):
        logger.warning(
            f"{file_path} appears to be a binary file. Skipping token count."
        )
        return 0

    try:
        with open(file_path, encoding="utf-8") as f:
            return count_tokens_from_stream(f)
    except UnicodeDecodeError:
        logger.error(
            f"{file_path} contains non-UTF-8 characters. Skipping token count."
        )
        return 0


def count_single_file(file_path: Path, output_format: str | None = None) -> int | str:
    count = count_tokens_from_file(file_path)

    if output_format == "json":
        return json.dumps(
            {
                "file": str(file_path),
                "tokens": count,
            }
        )
    elif output_format == "table":
        return f"{count} {file_path}"
    else:
        return count


def count_multiple_files(
    file_paths: list[Path], output_format: str | None = None
) -> int | str:
    file_counts = []
    total_count = 0

    for file_path in file_paths:
        file_count = count_tokens_from_file(file_path)
        total_count += file_count
        file_counts.append({"file": str(file_path), "tokens": file_count})

    if output_format == "json":
        return json.dumps(
            {
                "files": file_counts,
                "total_tokens": total_count,
            }
        )
    elif output_format == "table":
        lines = [f"{fc['tokens']} {fc['file']}" for fc in file_counts]
        lines.append(f"{total_count} TOTAL")
        return "\n".join(lines)
    else:
        return total_count


def count_from_stdin(output_format: str | None = None) -> int | str:
    if sys.stdin.isatty():
        logger.error("No input from stdin")
        return 0

    count = count_tokens_from_stream(sys.stdin)

    if output_format == "json":
        return json.dumps(
            {
                "source": "stdin",
                "tokens": count,
            }
        )
    elif output_format == "table":
        return f"{count} stdin"
    else:
        return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Count tokens in files or from stdin using tiktoken"
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Files to count tokens in. If not provided, reads from stdin.",
    )
    parser.add_argument(
        "--output-format",
        "-o",
        choices=["json", "table"],
        help="Output format for the results",
    )

    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    if not args.files and not sys.stdin.isatty():
        input_content = sys.stdin.read().strip()
        # Only treat as file paths if input contains null bytes and no newlines
        if input_content and "\0" in input_content and "\n" not in input_content:
            file_paths = [Path(path) for path in input_content.split("\0") if path]
            if file_paths and all(p.exists() for p in file_paths):
                result = count_multiple_files(file_paths, args.output_format)
                print(result)
                return

        count = count_tokens(input_content)

        if args.output_format == "json":
            result = json.dumps({"source": "stdin", "tokens": count})
        elif args.output_format == "table":
            result = f"{count} stdin"
        else:
            result = count

        print(result)
        return

    if args.files:
        if len(args.files) == 1:
            result = count_single_file(args.files[0], args.output_format)
        else:
            result = count_multiple_files(args.files, args.output_format)
    else:
        parser.print_help()
        return

    print(result)


setup_logger()

if __name__ == "__main__":
    main()
