#!/usr/bin/env bash
#MISE description="Initialize dotfiles"

set -euo pipefail

# shellcheck source=.mise/scripts/task-lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../scripts/task-lib.sh"

dotfiles_enter_repo
dotfiles_require_commands gum git curl mise

# shellcheck source=.mise/scripts/mackup-lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../scripts/mackup-lib.sh"

# -- Core init ----------------------------------------------------------------

dotfiles_spin "Updating mise packages..." mise upgrade --bump
find .mise/tasks/ -type f -name '*.sh' -exec chmod +x {} \;

dotfiles_spin "Updating Zellij plugins..." bash -c '
  mkdir -p home/.config/zellij/plugins/
  curl -fsSL -o home/.config/zellij/plugins/zjstatus.wasm \
    https://github.com/dj95/zjstatus/releases/latest/download/zjstatus.wasm
  curl -fsSL -o home/.config/zellij/plugins/zellij-sessionizer.wasm \
    https://github.com/laperlej/zellij-sessionizer/releases/latest/download/zellij-sessionizer.wasm
'

gum log --level info "Cloning ZSH plugins..."
mkdir -p generated/plugins
plugins=(
  "fzf-tab|https://github.com/Aloxaf/fzf-tab"
  "ugit|https://github.com/Bhupesh-V/ugit.git"
  "zsh-autocomplete|https://github.com/marlonrichert/zsh-autocomplete"
  "zsh-autosuggestions|https://github.com/zsh-users/zsh-autosuggestions"
  "fast-syntax-highlighting|https://github.com/zdharma-continuum/fast-syntax-highlighting"
)
for entry in "${plugins[@]}"; do
  name="${entry%%|*}"
  url="${entry##*|}"
  if [ ! -d "generated/plugins/$name" ]; then
    gum spin --title "  Cloning $name..." -- git clone --depth=1 "$url" "generated/plugins/$name"
  fi
done

# -- Mackup --------------------------------------------------------------------

newly_linked=0
dotfiles_ensure_mackup_symlink "$PWD/modules/mackup/.mackup"     "$HOME/.mackup"     && newly_linked=1 || true
dotfiles_ensure_mackup_symlink "$PWD/modules/mackup/.mackup.cfg" "$HOME/.mackup.cfg" && newly_linked=1 || true

if [ "$newly_linked" = 1 ]; then
  dotfiles_prepare_zshenv
  dotfiles_mackup_restore_safely "Restoring Mackup..."
else
  gum log --level info "Mackup already configured"
fi

# -- Secrets & sync ------------------------------------------------------------

dotfiles_prepare_zshenv
dotfiles_spin "Syncing completions & plugins..." mise run sync

# -- Optional CLIs -------------------------------------------------------------

# Each entry: "Label|binary-name|install-cmd". Pipe is unused in URLs.
optional_clis=(
  "Amp CLI|amp|curl -fsSL https://ampcode.com/install.sh | bash"
  "Sprites CLI|sprite|curl -fsSL https://sprites.dev/install.sh | sh"
  "Tigris CLI|tigris|curl -fsSL https://raw.githubusercontent.com/tigrisdata/cli/main/scripts/install.sh | sh"
)

available=()
for item in "${optional_clis[@]}"; do
  IFS='|' read -r label bin _ <<< "$item"
  command -v "$bin" &>/dev/null && continue
  available+=("$label")
done

if [ ${#available[@]} -gt 0 ]; then
  selected=$(gum choose --no-limit --header "Install optional CLIs?" "${available[@]}" || true)
  while IFS= read -r pick; do
    [ -n "$pick" ] || continue
    for item in "${optional_clis[@]}"; do
      IFS='|' read -r label _ cmd <<< "$item"
      if [[ "$label" == "$pick" ]]; then
        dotfiles_spin "Installing $label..." bash -c "$cmd"
      fi
    done
  done <<< "$selected"
fi

gum log --level info "Done ✓"
