#!/usr/bin/env bash
#MISE description="Initialize dotfiles"

set -euo pipefail

command -v git >/dev/null 2>&1 || { echo "Error: git not found" >&2; exit 1; }
command -v mise >/dev/null 2>&1 || exit 1
command -v uv >/dev/null 2>&1 || exit 1
command -v curl >/dev/null 2>&1 || { echo "Error: curl not found" >&2; exit 1; }
command -v op >/dev/null 2>&1 || { echo "Error: op (1Password CLI) not found" >&2; exit 1; }

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "Error: not inside a git repo" >&2; exit 1; }
cd "$REPO_ROOT" || exit 1

printf "\033[34m==> Updating mise packages and tasks...\033[0m\n"
mise upgrade
find "$REPO_ROOT/.mise/tasks/" -type f -exec chmod +x {} \;

printf "\033[34m==> Updating Zellij Plugins...\033[0m\n"
mkdir -p home/.config/zellij/plugins/
curl -sSL -o home/.config/zellij/plugins/zjstatus.wasm https://github.com/dj95/zjstatus/releases/latest/download/zjstatus.wasm
curl -sSL -o home/.config/zellij/plugins/zellij-sessionizer.wasm https://github.com/laperlej/zellij-sessionizer/releases/latest/download/zellij-sessionizer.wasm

printf "\033[34m==> Updating ZSH Plugins...\033[0m\n"

[ -d vendor/plugins/fzf-tab ]                  || git clone --depth=1 https://github.com/Aloxaf/fzf-tab                             vendor/plugins/fzf-tab
[ -d vendor/plugins/ugit ]                     || git clone --depth=1 https://github.com/Bhupesh-V/ugit.git                         vendor/plugins/ugit
[ -d vendor/plugins/zsh-autocomplete ]         || git clone --depth=1 https://github.com/marlonrichert/zsh-autocomplete             vendor/plugins/zsh-autocomplete
[ -d vendor/plugins/zsh-autosuggestions ]      || git clone --depth=1 https://github.com/zsh-users/zsh-autosuggestions              vendor/plugins/zsh-autosuggestions
[ -d vendor/plugins/fast-syntax-highlighting ] || git clone --depth=1 https://github.com/zdharma-continuum/fast-syntax-highlighting vendor/plugins/fast-syntax-highlighting

if command -v gfold >/dev/null 2>&1; then
  command -v jq >/dev/null 2>&1 || { echo "Error: jq not found (required for gfold update)" >&2; exit 1; }
  gfold -d json "$@" 2>/dev/null |
  jq -r '.[] | (.parent | rtrimstr("/")) + "/" + .name' |
  while read -r repo; do
    printf "\033[34m==> Updating %s...\033[0m\n" "$repo"
    git -C "$repo" pull --ff-only
  done
else
  printf "\033[31m==> gfold not found, skipping gfold update...\033[0m\n" >&2
fi

printf "\033[34m==> Restoring Mackup...\033[0m\n"
if [ ! -L "$HOME/.mackup" ] || [ ! -L "$HOME/.mackup.cfg" ]; then
  [ ! -L "$HOME/.mackup" ] && ln -sf "$REPO_ROOT/modules/mackup/.mackup" "$HOME"/.mackup
  [ ! -L "$HOME/.mackup.cfg" ] && ln -sf "$REPO_ROOT/modules/mackup/.mackup.cfg" "$HOME"/.mackup.cfg
  uvx mackup restore
else
  printf "\033[34m==> Mackup is already configured...\033[0m\n"
fi

printf "\033[34m==> Syncing Completion...\033[0m\n"
mise sync-completion

printf "\033[34m==> Injecting Private Environment...\033[0m\n"
op inject --in-file modules/zsh/env.private.tpl.zsh --out-file modules/zsh/env.private.zsh

printf "\033[34m==> Done...\033[0m\n"
