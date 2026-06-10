#!/usr/bin/env bash
#MISE description="Initialize dotfiles"

set -euo pipefail

# shellcheck source=.mise/scripts/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/../scripts/common.sh"

dotfiles_cd_root
dotfiles_require gum git curl mise

# shellcheck source=.mise/scripts/mackup.sh
source "$(dirname "${BASH_SOURCE[0]}")/../scripts/mackup.sh"

# -- Core init ----------------------------------------------------------------

dotfiles_run "Updating mise packages..." mise upgrade --bump
find .mise/tasks/ -type f -name '*.sh' -exec chmod +x {} \;

dotfiles_run "Updating Zellij plugins..." bash -c '
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
dotfiles_ensure_mackup_link "$PWD/modules/mackup/.mackup"     "$HOME/.mackup"     && newly_linked=1 || true
dotfiles_ensure_mackup_link "$PWD/modules/mackup/.mackup.cfg" "$HOME/.mackup.cfg" && newly_linked=1 || true

if [ "$newly_linked" = 1 ]; then
  dotfiles_generate_home_zshenv
  dotfiles_restore_mackup_without_mise_self "Restoring Mackup..."
else
  gum log --level info "Mackup already configured"
fi

# -- Secrets & sync ------------------------------------------------------------

if dotfiles_has_op_session; then
  dotfiles_generate_home_zshenv
  dotfiles_run "Syncing completions & plugins..." mise run sync
else
  gum log --level warn "1Password CLI not signed in — skipping ~/.zshenv generation and sync."
  gum log --level warn "Run 'eval \$(op signin)', then re-run 'mise run init'."
fi

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
        dotfiles_run "Installing $label..." bash -c "$cmd"
      fi
    done
  done <<< "$selected"
fi

gum log --level info "Done ✓"
