#!/usr/bin/env bash
#MISE description="Sync CLI Tools Completions"

set -euo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 1

[ -d config/shell/completions ] || mkdir -p config/shell/completions

if which uvx >/dev/null 2>&1; then
  _LLM_COMPLETE=zsh_source uvx llm > config/shell/completions/_llm
fi

if which bootdev >/dev/null 2>&1; then
  bootdev completion zsh > config/shell/completions/_bootdev
fi

if which ov >/dev/null 2>&1; then
  ov --completion zsh > config/shell/completions/_ov
fi
