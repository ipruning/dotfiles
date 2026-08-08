#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "loguru==0.7.3",
#     "rich==15.0.0",
# ]
# ///

import os
import re
import subprocess
import sys

from loguru import logger
from rich.console import Console
from rich.text import Text

logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <level>{message}</level>",
    level="INFO",
    colorize=True,
)

FILE_REGEX = re.compile(r"(?:^|(?<=\s))(file://[^\n\r<>]+|~[^\n\r<>]+|/[^\n\r<>]+)")

URL_REGEX = re.compile(
    r"(?:<)?((?:https?|ftp)://[^\s<>]+|"
    r"(?:www\.)[^\s<>]+|"
    r"(?:[a-zA-Z0-9][-a-zA-Z0-9]*\.)+(?:com|net|org|edu|gov|mil|int|io|dev|ai|sh)[^\s<>]*)(?:>)?"
)

URL_COLOR = "\033[36m"
PATH_COLOR = "\033[32m"
UUID_COLOR = "\033[35m"
CMD_COLOR = "\033[33m"
RESET = "\033[0m"
USAGE = """\
Usage: link.py

Extract URLs, paths, UUIDs, and resume commands from stdin or a Zellij screen dump.
"""


# Precompiled helpers
ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
HTTP_SUFFIX_RE = re.compile(r"HTTP/\d+\.\d.*$")

# UUID patterns moved to module scope to avoid recompilation
UUID_PATTERNS: list[re.Pattern[str]] = [
    # Standard dashed UUID (accept any version nibble, include v6/v7)
    re.compile(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
    ),
    # Dashed UUID with a single-letter prefix like t-<uuid>
    re.compile(
        r"\b[a-zA-Z]-([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12})\b"
    ),
    # Plain 32 hex UUID without dashes
    re.compile(r"\b[0-9a-fA-F]{32}\b"),
    # URN prefixed UUID
    re.compile(
        r"\burn:uuid:([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12})\b",
        re.IGNORECASE,
    ),
]

# Command patterns for resume/continue commands (e.g. codex resume <uuid>, amp threads continue <id>)
CMD_PATTERNS: list[re.Pattern[str]] = [
    # codex resume <uuid>
    re.compile(
        r"(codex\s+resume\s+[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
    ),
    # amp threads continue <thread-id>
    re.compile(
        r"(amp\s+threads\s+continue\s+[A-Za-z]-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
    ),
    # claude --resume <uuid>
    re.compile(
        r"(claude\s+--resume\s+[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
    ),
]


def sanitize_url(raw: str) -> str:
    s = raw.strip()
    # Trim surrounding angle brackets or quotes
    if s.startswith("<") and s.endswith(">"):
        s = s[1:-1]
    s = s.strip("'\"")

    # Cut off appended HTTP status residue like ...<url>HTTP/1.1 404 Not Found
    m = HTTP_SUFFIX_RE.search(s)
    if m:
        s = s[: m.start()].rstrip()

    # Drop common trailing punctuation not typically part of URLs
    while s and s[-1] in "'\"),.;]}":
        # Avoid stripping a path closing parenthesis if it is balanced
        if s[-1] == ")" and s.count("(") >= s.count(")"):
            break
        s = s[:-1]

    return s


def sanitize_path(raw: str) -> str:
    s = raw.strip().strip("'\"")
    return s


def is_noise_path(path: str) -> bool:
    """Filter out noisy/partial paths that aren't useful."""
    # Skip very short paths (likely fragments)
    if len(path) < 5:
        return True
    # Skip paths that are just directory components
    if path in ("/", "//", "./", "../"):
        return True
    # Skip paths ending with common noise patterns
    noise_suffixes = (
        ")",  # Trailing paren from markdown/code
        "|",  # Pipe fragments
        "&&",  # Shell operator fragments
        ";",  # Command separator
    )
    if path.endswith(noise_suffixes):
        return True
    # Skip paths that look like shell command fragments
    if path.startswith("/dev/") and path != "/dev/null":
        return True
    # Skip inline code/markdown artifacts
    if "`" in path or "```" in path:
        return True
    return False


def get_zellij_screen() -> str:
    if not os.environ.get("ZELLIJ"):
        return ""

    result = subprocess.run(
        ["zellij", "action", "dump-screen"],
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout


def extract_items(text: str) -> dict[str, str]:
    items_dict = {}

    file_matches = FILE_REGEX.findall(text)
    for path_str in file_matches:
        candidate = sanitize_path(path_str)
        if not candidate:
            continue

        # Convert common escape sequences (e.g. "\ " → " ") so that real
        # filesystem paths with spaces are preserved.
        candidate = candidate.replace("\\ ", " ")

        # Handle file:// URLs by stripping the prefix so we get a plain path
        if candidate.startswith("file://"):
            candidate = candidate[7:]

        # Expand a leading tilde to the user home directory.
        candidate = os.path.expanduser(candidate)

        # Finally, only add if we have not seen it before and not noise.
        if candidate not in items_dict and not is_noise_path(candidate):
            items_dict[candidate] = "PATH"

    # Check if there are plain local files in the text
    for line in text.splitlines():
        words = re.findall(r"\S+", line)
        for word in words:
            clean = sanitize_path(word)
            if (
                os.path.exists(clean)
                and clean not in items_dict
                and not is_noise_path(clean)
            ):
                items_dict[clean] = "PATH"

    # Identify URLs
    angle_urls = re.findall(r"<(https?://[^>]+)>", text)
    for au in angle_urls:
        su = sanitize_url(au)
        if su and su not in items_dict:
            items_dict[su] = "URL"

    # Use the main URL_REGEX
    for line in text.splitlines():
        for match in URL_REGEX.finditer(line):
            raw_url = match.group(1)  # Extract the URL part
            raw_url = sanitize_url(raw_url)
            if raw_url and raw_url not in items_dict:
                # Prepend https:// if no scheme is present
                if not re.match(r"^(https?|ftp)://", raw_url):
                    raw_url = f"https://{raw_url}"
                items_dict[raw_url] = "URL"

    # Identify UUID-like strings
    for line in text.splitlines():
        for pat in UUID_PATTERNS:
            for m in pat.finditer(line):
                uuid_str = m.group(1) if m.lastindex else m.group(0)
                if uuid_str not in items_dict:
                    items_dict[uuid_str] = "UUID"

    # Identify resume/continue commands
    for line in text.splitlines():
        for pat in CMD_PATTERNS:
            for m in pat.finditer(line):
                cmd_str = m.group(1)
                if cmd_str not in items_dict:
                    items_dict[cmd_str] = "CMD"

    return items_dict


def open_item(item: str, kind: str) -> None:
    if kind == "URL":
        logger.info(f"Opening URL: {item}")
        subprocess.run(["open", item], check=True)
    elif kind == "UUID":
        logger.info(f"Copying UUID to clipboard: {item}")
        subprocess.run(["pbcopy"], input=item, text=True, check=True)
    elif kind == "CMD":
        logger.info(f"Copying command to clipboard: {item}")
        subprocess.run(["pbcopy"], input=item, text=True, check=True)
    else:
        logger.info(f"Opening file/path: {item}")
        subprocess.run(["open", item], check=True)


def fuzzy_select_items(items_dict: dict[str, str]) -> None:
    if not items_dict:
        logger.info("No supported links, paths, UUIDs, or commands found.")
        return

    console = Console()
    for item, kind in sorted(items_dict.items(), key=lambda x: (x[1], x[0])):
        text_obj = Text()
        if kind == "URL":
            text_obj.append(item, style="cyan")
        elif kind == "CMD":
            text_obj.append(item, style="yellow")
        elif kind == "UUID":
            text_obj.append(item, style="magenta")
        else:
            text_obj.append(item, style="green")
        console.print(text_obj)

    lines_for_fzf = []
    for item in items_dict:
        if items_dict[item] == "URL":
            color = URL_COLOR
        elif items_dict[item] == "UUID":
            color = UUID_COLOR
        elif items_dict[item] == "CMD":
            color = CMD_COLOR
        else:
            color = PATH_COLOR
        lines_for_fzf.append(f"{color}{item}{RESET}")

    process = subprocess.run(
        ["fzf", "--ansi"],
        input="\n".join(lines_for_fzf),
        text=True,
        capture_output=True,
    )
    if process.returncode != 0:
        return

    selected_line = process.stdout.strip()
    # Remove ANSI codes
    selected_clean = ANSI_ESCAPE_RE.sub("", selected_line)

    if selected_clean in items_dict:
        open_item(selected_clean, items_dict[selected_clean])
        return

    logger.error(f"No matching item found for selection: '{selected_clean}'")


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if argv in (["-h"], ["--help"]):
        print(USAGE, end="")
        return
    if argv:
        print(f"link.py: unexpected arguments: {' '.join(argv)}", file=sys.stderr)
        sys.exit(2)

    zellij_text = get_zellij_screen()
    stdin_text = "" if sys.stdin.isatty() else sys.stdin.read()
    if not zellij_text and not stdin_text:
        print(
            "link.py: no input; pipe text on stdin or run inside Zellij so its screen can be dumped",
            file=sys.stderr,
        )
        sys.exit(1)

    combined_text = f"{zellij_text}\n{stdin_text}"

    items_dict = extract_items(combined_text)
    fuzzy_select_items(items_dict)


if __name__ == "__main__":
    main()
