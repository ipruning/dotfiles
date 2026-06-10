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

gum log --level info "Updating mise packages..."
dotfiles_run_with_timeout "${DOTFILES_INIT_NETWORK_TIMEOUT:-300}" mise upgrade --bump \
  || gum log --level warn "mise upgrade failed; continuing"
find .mise/tasks/ -type f -name '*.sh' -exec chmod +x {} \;

dotfiles_run_with_timeout "${DOTFILES_INIT_NETWORK_TIMEOUT:-300}" bash -c '
  mkdir -p home/.config/zellij/plugins/
  curl -fsSL --connect-timeout 10 --max-time 120 -o home/.config/zellij/plugins/zjstatus.wasm \
    https://github.com/dj95/zjstatus/releases/latest/download/zjstatus.wasm
  curl -fsSL --connect-timeout 10 --max-time 120 -o home/.config/zellij/plugins/zellij-sessionizer.wasm \
    https://github.com/laperlej/zellij-sessionizer/releases/latest/download/zellij-sessionizer.wasm
' || gum log --level warn "Zellij plugin update failed; continuing"

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
    gum log --level info "  Cloning $name..."
    dotfiles_run_with_timeout "${DOTFILES_GIT_CLONE_TIMEOUT:-120}" git clone --depth=1 "$url" "generated/plugins/$name" \
      || gum log --level warn "$name clone failed; continuing"
  fi
done

# -- Mackup --------------------------------------------------------------------

newly_linked=0
dotfiles_ensure_mackup_symlink "$PWD/modules/mackup/.mackup"     "$HOME/.mackup"     && newly_linked=1 || true
dotfiles_ensure_mackup_symlink "$PWD/modules/mackup/.mackup.cfg" "$HOME/.mackup.cfg" && newly_linked=1 || true

if [ "$newly_linked" = 1 ]; then
  dotfiles_prepare_private_zshenv
  dotfiles_mackup_restore_safely "Restoring Mackup..."
else
  gum log --level info "Mackup already configured"
fi

# -- Secrets & sync ------------------------------------------------------------

dotfiles_prepare_private_zshenv
gum log --level info "Syncing completions & plugins..."
dotfiles_run_with_timeout "${DOTFILES_SYNC_TIMEOUT:-300}" mise run sync \
  || gum log --level warn "sync failed; continuing"

# -- Optional CLIs -------------------------------------------------------------

# Each entry: "Label|binary-name|install-cmd". Pipe is unused in URLs.
optional_clis=(
  "Amp CLI|amp|curl -fsSL --connect-timeout 10 --max-time 120 https://ampcode.com/install.sh | bash"
  "Sprites CLI|sprite|curl -fsSL --connect-timeout 10 --max-time 120 https://sprites.dev/install.sh | sh"
  "Tigris CLI|tigris|curl -fsSL --connect-timeout 10 --max-time 120 https://raw.githubusercontent.com/tigrisdata/cli/main/scripts/install.sh | sh"
)

available=()
for item in "${optional_clis[@]}"; do
  IFS='|' read -r label bin _ <<< "$item"
  command -v "$bin" &>/dev/null && continue
  available+=("$label")
done

if [ ${#available[@]} -gt 0 ] && [ -t 0 ] && [ -t 1 ]; then
  selected=$(gum choose --no-limit --header "Install optional CLIs?" "${available[@]}" || true)
  while IFS= read -r pick; do
    [ -n "$pick" ] || continue
    for item in "${optional_clis[@]}"; do
      IFS='|' read -r label _ cmd <<< "$item"
      if [[ "$label" == "$pick" ]]; then
        gum log --level info "Installing $label..."
        dotfiles_run_with_timeout "${DOTFILES_OPTIONAL_INSTALL_TIMEOUT:-300}" bash -c "$cmd" \
          || gum log --level warn "$label install failed"
      fi
    done
  done <<< "$selected"
elif [ ${#available[@]} -gt 0 ]; then
  gum log --level warn "Non-interactive shell; skipping optional CLI installer prompt"
fi

gum log --level info "Done ✓"
