#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "fire==0.7.1",
# ]
# ///

import subprocess
import sys

import fire


def wrap_with_tags(content: str, tag: str) -> str:
    return f"<{tag}>\n" + content + f"\n</{tag}>"


def generate_apple_script() -> str:
    return """
tell application "Google Chrome"
    activate
    if (count of windows) = 0 then make new window
    set newTab to make new tab at end of tabs of front window
    set URL of newTab to "https://chatgpt.com/"
end tell

delay 2
tell application "System Events"
    keystroke "p"
    delay 0.5
    key code 53 using {{shift down}}
    delay 0.5
    keystroke "v" using {{command down}}
    delay 0.5
    keystroke return
end tell
"""


def main(user_instructions: str | None = None, dry_run=False) -> None:
    contexts = []
    stdin_content = sys.stdin.read().strip() if not sys.stdin.isatty() else ""
    if stdin_content:
        if user_instructions:
            contexts.append(wrap_with_tags(stdin_content, "context"))
            contexts.append(wrap_with_tags(user_instructions, "user_instructions"))
        else:
            contexts.append(stdin_content)
    else:
        if user_instructions:
            contexts.append(wrap_with_tags(user_instructions, "user_instructions"))
    if len(contexts) < 1:
        raise ValueError(
            "No message provided. Please provide a message either as an argument or through stdin."
        )
    instruction = "\n\n".join(contexts)

    if dry_run:
        print(instruction)
    else:
        subprocess.run(["pbcopy"], input=instruction.encode("utf-8"))
        # subprocess.run(["switch-input-source.swift", "com.apple.keylayout.ABC"])
        subprocess.run(["osascript", "-e", generate_apple_script()])


if __name__ == "__main__":
    fire.Fire(main)
