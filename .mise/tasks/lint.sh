#!/usr/bin/env bash
#MISE description="Run code linting and formatting"

set -euo pipefail

if which pre-commit >/dev/null 2>&1; then
  mise x -- pre-commit install
else
  printf '\033[1;31m[WARN]\033[0m pre-commit not found, skipping pre-commit install\n' >&2
fi

mise x -- pre-commit install --install-hooks && git ls-files | xargs mise x -- pre-commit run --show-diff-on-failure --files
