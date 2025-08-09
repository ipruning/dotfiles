#!/usr/bin/env bash
#MISE description="Sync CLI Tools Completions"

set -euo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 1

[ -d config/shell/completions ] || mkdir -p config/shell/completions

_LLM_COMPLETE=zsh_source uvx llm > config/shell/completions/_llm
bootdev completion zsh > config/shell/completions/_bootdev
ov --completion zsh > config/shell/completions/_ov
