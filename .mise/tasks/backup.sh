#!/usr/bin/env bash
#MISE description="Backup your dotfiles"

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

gum confirm "Are you sure you want to run mackup backup (force)?" && uvx mackup backup --force
