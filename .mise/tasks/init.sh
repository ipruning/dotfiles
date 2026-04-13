#!/usr/bin/env bash
#MISE description="Initialize dotfiles"

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# -- Core init ----------------------------------------------------------------

gum spin --title "Updating mise packages..." -- mise upgrade
find .mise/tasks/ -type f -exec chmod +x {} \;

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

if [ ! -L "$HOME/.mackup" ] || [ ! -L "$HOME/.mackup.cfg" ]; then
  [ ! -L "$HOME/.mackup" ] && ln -sf "$PWD/modules/mackup/.mackup" "$HOME"/.mackup
  [ ! -L "$HOME/.mackup.cfg" ] && ln -sf "$PWD/modules/mackup/.mackup.cfg" "$HOME"/.mackup.cfg
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

optional_clis=(
  "Amp CLI:curl -fsSL https://ampcode.com/install.sh | bash"
  "Sprites CLI:curl -fsSL https://sprites.dev/install.sh | sh"
  "Tigris CLI:curl -fsSL https://raw.githubusercontent.com/tigrisdata/cli/main/scripts/install.sh | sh"
)

available=()
for item in "${optional_clis[@]}"; do
  label="${item%%:*}"
  bin="${label%% *}"
  bin="$(echo "$bin" | tr '[:upper:]' '[:lower:]')"
  case "$bin" in
    amp)     command -v amp     &>/dev/null && continue ;;
    sprites) command -v sprites &>/dev/null && continue ;;
    tigris)  command -v tigris  &>/dev/null && continue ;;
  esac
  available+=("$label")
done

if [ ${#available[@]} -gt 0 ]; then
  selected=$(gum choose --no-limit --header "Install optional CLIs?" "${available[@]}" || true)
  while IFS= read -r pick; do
    [ -n "$pick" ] || continue
    for item in "${optional_clis[@]}"; do
      label="${item%%:*}"
      cmd="${item#*:}"
      if [[ "$label" == "$pick" ]]; then
        gum spin --title "Installing $label..." -- bash -c "$cmd"
      fi
    done
  done <<< "$selected"
fi

gum log --level info "Done ✓"
