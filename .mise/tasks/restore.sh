#!/usr/bin/env bash
#MISE description="Restore your dotfiles"

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/_lib.sh"

require_cmd git
require_cmd gum
require_cmd mise
require_cmd uvx

REPO_ROOT="$(repo_root)"
cd "$REPO_ROOT"

if [[ "${1:-}" == "--force" ]]; then
  uvx mackup restore --force
else
  gum confirm "Are you sure you want to run mackup restore (force)?" && uvx mackup restore --force
fi
