#!/usr/bin/env bash
#MISE description="Run code linting and formatting"

set -euo pipefail

mise x -- pre-commit install --install-hooks && git ls-files | xargs mise x -- pre-commit run --show-diff-on-failure --files
