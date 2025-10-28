#!/usr/bin/env bash
#MISE description="Initialize Monorepo CI/CD tools"

set -euo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 1

command -v mise >/dev/null 2>&1 || exit 1
command -v uv >/dev/null 2>&1 || exit 1

printf '\n\033[1;34m▶ Updating mise packages and tasks\033[0m\n'
mise upgrade
find "$(git rev-parse --show-toplevel)"/.mise/tasks/ -type f -exec chmod +x {} \;

printf '\n\033[1;34m▶ Updating Zellij Plugins\033[0m\n'
mkdir -p home/.config/zellij/plugins/
curl -sSL -o home/.config/zellij/plugins/zjstatus.wasm https://github.com/dj95/zjstatus/releases/latest/download/zjstatus.wasm
curl -sSL -o home/.config/zellij/plugins/zellij-sessionizer.wasm https://github.com/laperlej/zellij-sessionizer/releases/latest/download/zellij-sessionizer.wasm

printf '\n\033[1;34m▶ Updating ZSH Plugins\033[0m\n'

[ -d config/shell/plugins/fzf-tab ]                  || git clone --depth=1 https://github.com/Aloxaf/fzf-tab                             config/shell/plugins/fzf-tab
[ -d config/shell/plugins/ugit ]                     || git clone --depth=1 https://github.com/Bhupesh-V/ugit.git                         config/shell/plugins/ugit
[ -d config/shell/plugins/zsh-autocomplete ]         || git clone --depth=1 https://github.com/marlonrichert/zsh-autocomplete             config/shell/plugins/zsh-autocomplete
[ -d config/shell/plugins/zsh-autosuggestions ]      || git clone --depth=1 https://github.com/zsh-users/zsh-autosuggestions              config/shell/plugins/zsh-autosuggestions
[ -d config/shell/plugins/fast-syntax-highlighting ] || git clone --depth=1 https://github.com/zdharma-continuum/fast-syntax-highlighting config/shell/plugins/fast-syntax-highlighting

if which gfold >/dev/null 2>&1; then
  gfold -d json "$@" 2>/dev/null |
  jq -r '.[] | (.parent | rtrimstr("/")) + "/" + .name' |
  while read -r repo; do
    printf '\n\033[1;34m▶ Updating %s\033[0m\n' "$repo"
    git -C "$repo" pull --ff-only
  done
else
  printf '\033[1;31m[WARN]\033[0m gfold not found, skipping gfold update\n' >&2
fi

printf '\n\033[1;34m▶ Restoring Mackup\033[0m\n'
if [ ! -L "$HOME/.mackup" ] || [ ! -L "$HOME/.mackup.cfg" ]; then
  [ ! -L "$HOME/.mackup" ] && ln -sf "$HOME/dotfiles/config/mackup/.mackup" "$HOME"/.mackup
  [ ! -L "$HOME/.mackup.cfg" ] && ln -sf "$HOME/dotfiles/config/mackup/.mackup.cfg" "$HOME"/.mackup.cfg
  uvx mackup restore
else
  printf '\n\033[1;34m▶ Mackup is already configured\033[0m\n'
fi

printf '\n\033[1;34m▶ Syncing Completion\033[0m\n'
mise sync-completion

printf '\n\033[1;34m▶ Injecting Private Environment\033[0m\n'
op inject --in-file config/shell/env.private.tpl.zsh --out-file config/shell/env.private.zsh

printf '\n\033[1;34m▶ Done\033[0m\n'
