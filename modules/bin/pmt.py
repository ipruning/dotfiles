#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# ///

import logging
import os
import subprocess
import sys
import tempfile

IS_CUSTOM_INSTRUCTIONS_ENABLED: bool = False
IS_ZELLIJ_CONTEXT_ENABLED: bool = False


def _setup_logger():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    return logging.getLogger(__name__)


def _get_custom_instructions() -> str | None:
    CUSTOM_INSTRUCTIONS: str | None = """\
    在 Assistant 回答问题前，一定要揣测下：为什么 User 要问 Assistant 这个问题？User 问题背后有没有隐藏的假设？很多时候 User 交给 Assistant 的任务是在更大的 Scope 与 Context 下。

    Assistant 要有思考深度。如果 User 的提问不是最优，请 Assistant 突破 User 的假设（可能是错误的假设），问出更加本质的问题。Assistant 的目标永远是帮 User 规避 X-Y Problem，帮 User 获得对问题 First Principle 的理解与启发。Assistant 觉得若有未解决的问题，列在末尾。

    Do not use em dashes in your reply.

    Do not output three consecutive hyphens anywhere in your reply.

    Do not overuse bold formatting (only use bold when it is necessary).

    Use only Markdown headings at levels 1 to 3. Use level 1 at most once, as the title. Do not use level 4 headings.

    User 爱阅读「中英文间有适当空格」，「中文标点恰当使用」的文字。比如，请用「我学到了大模型 LLMs 的发展，以及缩放定律。」而非“我学到了大模型 llms 的发展，以及缩放定律.”。

    User 的 MacBook 环境是：

    - nushell>=0.108.0
    - python>=3.13.9
    - pydantic>=2.12.4
    - bun>=1.3.2"""  # noqa: E501

    return CUSTOM_INSTRUCTIONS


def _catscreen() -> str | None:
    if "ZELLIJ" not in os.environ or not os.environ["ZELLIJ"]:
        logger.warning("Not running inside a Zellij session.")
        return None

    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            temp_filename = tmp_file.name

        subprocess.run(["zellij", "action", "dump-screen", temp_filename], check=True)

        with open(temp_filename) as f:
            content = f.read().splitlines()

        filtered_content = [line for line in content if line.strip()]

        os.remove(temp_filename)

        return "\n".join(filtered_content)

    except subprocess.CalledProcessError:
        logger.error("Failed to execute zellij command")
        return None


def _get_terminal_output() -> str | None:
    terminal_content = _catscreen()
    if terminal_content:
        lines = terminal_content.splitlines()
        if lines:
            return "\n".join(lines[:-2])
    return None


def main(args: list[str]) -> None:
    terminal_context = ""
    other_context = ""

    if IS_ZELLIJ_CONTEXT_ENABLED:
        tc = _get_terminal_output()
        if tc:
            terminal_context = tc

    if not sys.stdin.isatty():
        other_context = sys.stdin.read().rstrip()

    if not args and not other_context and not terminal_context:
        return

    user_instructions = (" ".join(args)).strip() if args else other_context.strip()

    if terminal_context:
        print("<terminal_context>")
        print(terminal_context)
        print("</terminal_context>")
        print()

    if args and other_context.strip():
        print("<other_context>")
        print(other_context)
        print("</other_context>")
        print()

    if IS_CUSTOM_INSTRUCTIONS_ENABLED:
        ci = _get_custom_instructions()
        if ci:
            print("<custom_instructions>")
            print(ci)
            print("</custom_instructions>")

    if user_instructions:
        print("<user_instructions>")
        print(user_instructions)
        print("</user_instructions>")
        print()


if __name__ == "__main__":
    logger: logging.Logger = _setup_logger()
    main(sys.argv[1:])
