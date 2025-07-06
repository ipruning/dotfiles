#!/usr/bin/env bash
#MISE description="Initialize Monorepo CI/CD tools"
#MISE env={MISE_DEBUG=1,MISE_LOG_HTTP=1,MISE_RAW=1,MISE_JOBS=1}

cd "$(git rev-parse --show-toplevel)" || exit 1

type mise || exit 1

mise install

mise x -- pre-commit install

mise cfg

mise tasks

find "$(git rev-parse --show-toplevel)"/.mise/tasks/ -type f -exec chmod +x {} \;

printf '\n\033[1;34m▶ Updating Zellij Plugins %s\033[0m\n'
mkdir -p home/.config/zellij/plugins/
curl -L -o home/.config/zellij/plugins/zjstatus.wasm https://github.com/dj95/zjstatus/releases/latest/download/zjstatus.wasm
curl -L -o home/.config/zellij/plugins/zellij-sessionizer.wasm https://github.com/cunialino/zellij-sessionizer/releases/latest/download/sessionizer.wasm

printf '\n\033[1;34m▶ Updating ZSH Plugins %s\033[0m\n'

[ -d config/shell/plugins/fzf-tab ]                  || git clone --depth=1 https://github.com/Aloxaf/fzf-tab                             config/shell/plugins/fzf-tab
[ -d config/shell/plugins/ugit ]                     || git clone --depth=1 https://github.com/Bhupesh-V/ugit.git                         config/shell/plugins/ugit
[ -d config/shell/plugins/zsh-autocomplete ]         || git clone --depth=1 https://github.com/marlonrichert/zsh-autocomplete             config/shell/plugins/zsh-autocomplete
[ -d config/shell/plugins/zsh-autosuggestions ]      || git clone --depth=1 https://github.com/zsh-users/zsh-autosuggestions              config/shell/plugins/zsh-autosuggestions
[ -d config/shell/plugins/fast-syntax-highlighting ] || git clone --depth=1 https://github.com/zdharma-continuum/fast-syntax-highlighting config/shell/plugins/fast-syntax-highlighting

gfold -d json "$@" 2>/dev/null |
  jq -r '.[] | (.parent | rtrimstr("/")) + "/" + .name' |
  while read -r repo; do
      printf '\n\033[1;34m▶ Updating %s\033[0m\n' "$repo"
      git -C "$repo" pull --ff-only
  done
