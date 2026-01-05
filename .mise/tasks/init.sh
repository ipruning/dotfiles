#!/usr/bin/env bash
#MISE description="Initialize dotfiles"

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/_lib.sh"

require_cmd git
require_cmd mise
require_cmd uvx
require_cmd curl
require_cmd op

REPO_ROOT="$(repo_root)"
cd "$REPO_ROOT"

log_info "Updating mise packages and tasks..."
mise upgrade
find "$REPO_ROOT/.mise/tasks/" -type f -exec chmod +x {} \;

log_info "Updating Zellij Plugins..."
mkdir -p home/.config/zellij/plugins/
curl -fsSL -o home/.config/zellij/plugins/zjstatus.wasm https://github.com/dj95/zjstatus/releases/latest/download/zjstatus.wasm
curl -fsSL -o home/.config/zellij/plugins/zellij-sessionizer.wasm https://github.com/laperlej/zellij-sessionizer/releases/latest/download/zellij-sessionizer.wasm

log_info "Updating ZSH Plugins..."

mkdir -p vendor/plugins
[ -d vendor/plugins/fzf-tab ]                  || git clone --depth=1 https://github.com/Aloxaf/fzf-tab                             vendor/plugins/fzf-tab
[ -d vendor/plugins/ugit ]                     || git clone --depth=1 https://github.com/Bhupesh-V/ugit.git                         vendor/plugins/ugit
[ -d vendor/plugins/zsh-autocomplete ]         || git clone --depth=1 https://github.com/marlonrichert/zsh-autocomplete             vendor/plugins/zsh-autocomplete
[ -d vendor/plugins/zsh-autosuggestions ]      || git clone --depth=1 https://github.com/zsh-users/zsh-autosuggestions              vendor/plugins/zsh-autosuggestions
[ -d vendor/plugins/fast-syntax-highlighting ] || git clone --depth=1 https://github.com/zdharma-continuum/fast-syntax-highlighting vendor/plugins/fast-syntax-highlighting

if command -v gfold >/dev/null 2>&1; then
  require_cmd jq
  gfold -d json "$@" 2>/dev/null |
  jq -r '.[] | (.parent | rtrimstr("/")) + "/" + .name' |
  while read -r repo; do
    log_info "Updating $repo..."
    git -C "$repo" pull --ff-only
  done
else
  log_warn "gfold not found, skipping gfold update..."
fi

log_info "Restoring Mackup..."
if [ ! -L "$HOME/.mackup" ] || [ ! -L "$HOME/.mackup.cfg" ]; then
  [ ! -L "$HOME/.mackup" ] && ln -sf "$REPO_ROOT/modules/mackup/.mackup" "$HOME"/.mackup
  [ ! -L "$HOME/.mackup.cfg" ] && ln -sf "$REPO_ROOT/modules/mackup/.mackup.cfg" "$HOME"/.mackup.cfg
  uvx mackup restore
else
  log_info "Mackup is already configured..."
fi

log_info "Syncing Completion..."
mise sync-completion

log_info "Injecting Private Environment..."
op inject --in-file modules/zsh/env.private.tpl.zsh --out-file modules/zsh/env.private.zsh

log_info "Done..."
