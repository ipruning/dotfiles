#!/usr/bin/env bash
#MISE description="Sync CLI Tools Completions"

cd "$(git rev-parse --show-toplevel)" || exit 1

_LLM_COMPLETE=zsh_source llm > config/shell/completions/_llm
bootdev completion zsh > config/shell/completions/_bootdev
