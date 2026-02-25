GENERATED_COMPLETIONS_DIR="$HOME/dotfiles/generated/completions"
GENERATED_FUNCTIONS_DIR="$HOME/dotfiles/generated/functions"
PLUGINS_DIR="$HOME/dotfiles/generated/plugins"

# 👇 XDG Config Home
export XDG_CONFIG_HOME="$HOME/.config"

# 👇 Emacs Mode
bindkey -e

# 👇 zsh Theme
if command -v starship >/dev/null 2>&1; then
  source "$GENERATED_FUNCTIONS_DIR/_starship.zsh"
fi

# 👇 zsh options
setopt interactivecomments
zstyle ":completion:*" matcher-list "m:{a-z}={A-Za-z}"

# 👇 Tips
autoload -U edit-command-line
zle -N edit-command-line
bindkey "^x^e" edit-command-line

function copy-command {
  print -rn -- "$BUFFER" | c
  zle -M "Copied to clipboard"
}
zle -N copy-command
bindkey "^x^y" copy-command

bindkey ' ' magic-space

# 👇 Wordchars
WORDCHARS=${WORDCHARS//.}
WORDCHARS=${WORDCHARS//\/}
WORDCHARS=${WORDCHARS//=}

# 👇 Keybindings
bindkey '\e[1;5C' forward-word
bindkey '\e[1;5D' backward-word
bindkey "^A" beginning-of-line
bindkey "^B" backward-char
bindkey "^D" delete-word
bindkey "^E" end-of-line
bindkey "^F" forward-char

# 👇 Editor
if [[ "$TERM_PROGRAM" == "vscode" ]]; then
  export EDITOR="/usr/local/bin/cursor --wait"
  export VISUAL="$EDITOR"
fi

if [[ "$TERM_PROGRAM" == "zed" ]]; then
  export EDITOR="/opt/homebrew/bin/zed --wait"
  export VISUAL="$EDITOR"
fi

if [[ "$TERM_PROGRAM" == "ghostty" ]]; then
  export EDITOR="/opt/homebrew/bin/nvim"
  export EDITOR="/opt/homebrew/bin/zed --wait"
  export VISUAL="$EDITOR"
fi

# 👇 Functions
source "$HOME/dotfiles/modules/zsh/macos.zsh"
source "$HOME/dotfiles/modules/zsh/surge.zsh"

# 👇 1Password Environment Loader
openv() {
  local id="${1:-}"

  if [[ -z "$id" ]]; then
    echo "Usage: openv <1password-environment-id>" >&2
    return 2
  fi

  if ! command -v op >/dev/null 2>&1; then
    echo "op CLI not found" >&2
    return 1
  fi

  while IFS= read -r line; do
    [[ -n "$line" ]] && export "$line"
  done < <(op environment read "$id")
}

openv-longbridge() {
  openv qikdfxnulzghidg6iu7jf3sboq
}

# 👇 Brew
export HOMEBREW_NO_ANALYTICS=1

# 👇 Prek
export PREK_COLOR="never"

# 👇 tailspin
if command -v tailspin >/dev/null 2>&1; then
  if command -v ov >/dev/null 2>&1; then
    export TAILSPIN_PAGER="ov -f [FILE]"
  fi
fi

# 👇 OrbStack
source "$HOME/.orbstack/shell/init.zsh" 2>/dev/null || :

# 👇 zoxide
if command -v zoxide >/dev/null 2>&1; then
  eval "$(zoxide init zsh --cmd j)"
fi

# 👇 tv
_tv_search() {
  emulate -L zsh
  zle -I

  local current_prompt
  current_prompt=$LBUFFER

  local output

  output=$(tv --autocomplete-prompt "$current_prompt" $*)

  zle reset-prompt

  if [[ -n $output ]]; then
    RBUFFER=""
    LBUFFER=$current_prompt$output

    # uncomment this to automatically accept the line
    # (i.e. run the command without having to press enter twice)
    # zle accept-line
  fi
}

zle -N tv-search _tv_search

bindkey '^T' tv-search

# 👇 fzf
export FZF_DEFAULT_COMMAND="fd"

export FZF_DEFAULT_OPTS=" \
--multi \
--style minimal \
--bind 'ctrl-y:accept' \
--color=bg+:#313244,bg:#1e1e2e,spinner:#f5e0dc,hl:#f38ba8 \
--color=fg:#cdd6f4,header:#f38ba8,info:#cba6f7,pointer:#f5e0dc \
--color=marker:#b4befe,fg+:#cdd6f4,prompt:#cba6f7,hl+:#f38ba8 \
--color=selected-bg:#45475a"

# 👇 fzf-tab
if [[ -f "$PLUGINS_DIR"/fzf-tab/fzf-tab.plugin.zsh ]]; then
  source "$PLUGINS_DIR"/fzf-tab/fzf-tab.plugin.zsh
  zstyle ':completion:*:descriptions' format '[%d]'
  zstyle ':completion:*' menu no
  zstyle ':fzf-tab:*' use-fzf-default-opts yes
fi

# 👇 zsh-autosuggestions
if [[ -f "$PLUGINS_DIR"/zsh-autosuggestions/zsh-autosuggestions.zsh ]]; then
  source "$PLUGINS_DIR"/zsh-autosuggestions/zsh-autosuggestions.zsh
fi

# 👇 fast-syntax-highlighting
if [[ -f "$PLUGINS_DIR"/fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh ]]; then
  source "$PLUGINS_DIR"/fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh
fi

# 👇 mysql
if command -v brew >/dev/null 2>&1; then
  export PKG_CONFIG_PATH="/opt/homebrew/opt/mysql-client/lib/pkgconfig:$PKG_CONFIG_PATH"
fi

# 👇 try-rs
if [[ -f "$HOME/Library/Application Support/try-rs/try-rs.zsh" ]]; then
  source "$HOME/Library/Application Support/try-rs/try-rs.zsh"
fi

# 👇 mise (will cost 40ms)
if command -v mise >/dev/null 2>&1; then
  source "$GENERATED_FUNCTIONS_DIR/_mise.zsh"
fi

# 👇 atuin (need below mise)
if command -v atuin >/dev/null 2>&1; then
  source "$GENERATED_FUNCTIONS_DIR/_atuin.zsh"
fi

# 👇 Optional local bins (shared across machines)
# Add only if directory exists, and append to avoid shadowing system/core tools.
for optional_bin in "$HOME/.opencode/bin" "$HOME/.modular/bin"; do
  # normalize: remove inherited/prepended copies first, then append only if present
  path=(${path:#$optional_bin})
  path=(${path:#$optional_bin/})
  [[ -d "$optional_bin" ]] && path+=("$optional_bin")
done

# 👇 ugit disabled (plugin adds its repo root to PATH, including generic names like `install`)
# Remove stale ugit PATH entries inherited from older shells/sessions.
path=(${path:#$PLUGINS_DIR/ugit})
path=(${path:#$PLUGINS_DIR/ugit/})
# if [[ -f "$PLUGINS_DIR"/ugit/ugit.plugin.zsh ]]; then
#   source "$PLUGINS_DIR"/ugit/ugit.plugin.zsh
# fi

# 👇 OpenClaw Completion
if [[ -f "$HOME/.openclaw/completions/openclaw.zsh" ]]; then
  source "$HOME/.openclaw/completions/openclaw.zsh"
fi
