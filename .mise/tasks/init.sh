#!/usr/bin/env bash
#MISE description="Initialize dotfiles"

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# -- Core init ----------------------------------------------------------------

gum spin --title "Updating mise packages..." -- mise upgrade
find .mise/tasks/ -type f -name '*.sh' -exec chmod +x {} \;

gum spin --title "Updating Zellij plugins..." -- bash -c '
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

# `ln -sf` cannot replace a non-empty directory or a regular file at the
# target path, so explicitly handle each link's existing state.
# Returns 0 if a *new* link was created (caller decides whether to restore),
# 1 if the link was already correct or could not be created safely.
ensure_mackup_link() {
  local target="$1" link="$2"
  if [ -L "$link" ]; then
    # Already a symlink — keep as-is to avoid unnecessary churn.
    return 1
  fi
  if [ -e "$link" ]; then
    gum log --level warn "$link exists and is not a symlink; skipping (move it aside to fix)"
    return 1
  fi
  ln -s "$target" "$link"
  return 0
}

newly_linked=0
ensure_mackup_link "$PWD/modules/mackup/.mackup"     "$HOME/.mackup"     && newly_linked=1 || true
ensure_mackup_link "$PWD/modules/mackup/.mackup.cfg" "$HOME/.mackup.cfg" && newly_linked=1 || true

if [ "$newly_linked" = 1 ]; then
  gum spin --title "Restoring Mackup..." -- uvx mackup restore
else
  gum log --level info "Mackup already configured"
fi

# -- Secrets & sync ------------------------------------------------------------

if op account list &>/dev/null; then
  gum spin --title "Injecting secrets..." -- \
    op inject --in-file modules/zsh/env.private.tpl.zsh \
              --out-file modules/zsh/env.private.zsh
  # shellcheck source=/dev/null
  source modules/zsh/env.private.zsh
  gum spin --title "Syncing completions & plugins..." -- mise run sync
else
  gum log --level warn "1Password CLI not signed in — skipping secret injection and sync."
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
        gum spin --title "Installing $label..." -- bash -c "$cmd"
      fi
    done
  done <<< "$selected"
fi

gum log --level info "Done ✓"
