#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = ["tiktoken==0.12.0"]
# ///

import sys

import tiktoken

TOKENIZER = "o200k_base"

enc = tiktoken.get_encoding(TOKENIZER)

if __name__ == "__main__":
    print(len(enc.encode(sys.stdin.read(), disallowed_special=())))
