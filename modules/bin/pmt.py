#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///

import logging
import os
import sys


def _setup_logger():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    return logging.getLogger(__name__)


def _read_text_file(path: str) -> str:
    expanded = os.path.expandvars(os.path.expanduser(path))
    with open(expanded, encoding="utf-8", errors="replace") as f:
        return f.read()


def _maybe_read_user_instructions_from_args(args: list[str]) -> str | None:
    """
    Allow passing large multi-line prompts without losing newlines via shell substitution.

    Supported forms:
    - pmt.py @/path/to/prompt.md
    - pmt.py /path/to/prompt.md   (only when it's the single arg and the file exists)
    - pmt.py --file /path/to/prompt.md
    - pmt.py -f /path/to/prompt.md
    """
    log = logging.getLogger(__name__)
    if not args:
        return None

    if args[0] in {"-f", "--file"}:
        if len(args) < 2:
            log.error("Missing path after %s", args[0])
            return None
        path = args[1]
        try:
            return _read_text_file(path).rstrip()
        except OSError as e:
            log.error("Failed to read file %r: %s", path, e)
            return None

    if len(args) == 1 and args[0].startswith("@"):
        path = args[0][1:]
        if not path:
            log.error("Missing path after '@'")
            return None
        try:
            return _read_text_file(path).rstrip()
        except OSError as e:
            log.error("Failed to read file %r: %s", path, e)
            return None

    if len(args) == 1:
        path = args[0]
        expanded = os.path.expandvars(os.path.expanduser(path))
        if os.path.isfile(expanded):
            try:
                return _read_text_file(path).rstrip()
            except OSError as e:
                log.error("Failed to read file %r: %s", path, e)
                return None

    return None


def main(args: list[str]) -> None:
    other_context = ""

    if not sys.stdin.isatty():
        other_context = sys.stdin.read().rstrip()

    if not args and not other_context:
        return

    user_instructions_from_args = _maybe_read_user_instructions_from_args(args)
    user_instructions = (
        user_instructions_from_args.strip()
        if user_instructions_from_args is not None
        else ((" ".join(args)).strip() if args else other_context.strip())
    )

    if args and other_context.strip():
        print("<other_context>")
        print(other_context)
        print("</other_context>")
        print()

    if user_instructions:
        print("<user_instructions>")
        print(user_instructions)
        print("</user_instructions>")
        print()


if __name__ == "__main__":
    logger: logging.Logger = _setup_logger()
    main(sys.argv[1:])
