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
_openv_resolve_op_env_bin() {
  local override="${OPENV_OP_ENV_BIN:-}"
  if [[ -n "$override" && -x "$override" ]]; then
    echo "$override"
    return 0
  fi

  local preferred="/usr/local/bin/op"
  if [[ -x "$preferred" ]] && "$preferred" environment read --help >/dev/null 2>&1; then
    echo "$preferred"
    return 0
  fi

  if command -v op >/dev/null 2>&1; then
    local current
    current="$(command -v op)"
    if "$current" environment read --help >/dev/null 2>&1; then
      echo "$current"
      return 0
    fi
  fi

  local generated="$HOME/dotfiles/generated/bin/op"
  if [[ -x "$generated" ]] && "$generated" environment read --help >/dev/null 2>&1; then
    echo "$generated"
    return 0
  fi

  return 1
}

openv() {
  local id="${1:-}"
  local op_env_bin op_auth_bin op_account output session

  if [[ -z "$id" ]]; then
    echo "Usage: openv <1password-environment-id>" >&2
    return 2
  fi

  if ! op_env_bin="$(_openv_resolve_op_env_bin)"; then
    echo "No op CLI with 'environment' command found (need op >= 2.33)." >&2
    return 1
  fi

  if output="$("$op_env_bin" environment read "$id" 2>&1)"; then
    while IFS= read -r line; do
      [[ -n "$line" ]] && export "$line"
    done <<< "$output"
    return 0
  fi

  if [[ "$output" == *"connecting to desktop app"* || "$output" == *"connection reset"* || "$output" == *"PipeAuthError"* ]]; then
    op_auth_bin="${OPENV_OP_AUTH_BIN:-/usr/bin/op}"
    op_account="${OPENV_OP_ACCOUNT:-}"

    if [[ ! -x "$op_auth_bin" ]]; then
      echo "$output" >&2
      echo "Fallback auth op not found: $op_auth_bin" >&2
      return 1
    fi

    if [[ -n "$op_account" ]]; then
      session="$("$op_auth_bin" signin --raw --account "$op_account" 2>/dev/null)" || {
        echo "Failed to get session token from $op_auth_bin (approve the 1Password sign-in prompt and retry)." >&2
        return 1
      }
    else
      session="$("$op_auth_bin" signin --raw 2>/dev/null)" || {
        echo "Failed to get session token from $op_auth_bin (approve the 1Password sign-in prompt and retry)." >&2
        return 1
      }
    fi

    if [[ -z "$session" ]]; then
      echo "Could not obtain a session token from $op_auth_bin (empty output)." >&2
      echo "Install op >= 2.33 to /usr/local/bin with group 'onepassword-cli' and mode 2755, then retry." >&2
      return 1
    fi

    if ! output="$(OP_LOAD_DESKTOP_APP_SETTINGS=false "$op_env_bin" --session "$session" environment read "$id" 2>&1)"; then
      if [[ "$output" == *"No accounts configured"* ]]; then
        echo "No CLI account is configured for $op_env_bin." >&2
        echo "Install a properly privileged op >= 2.33 (root:onepassword-cli, mode 2755) and retry." >&2
      else
        echo "$output" >&2
      fi
      return 1
    fi

    while IFS= read -r line; do
      [[ -n "$line" ]] && export "$line"
    done <<< "$output"
    return 0
  fi

  echo "$output" >&2
  return 1
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
if [[ -f "$HOME/.config/try-rs/try-rs.zsh" ]]; then
  source "$HOME/.config/try-rs/try-rs.zsh"
fi

# 👇 nanobrew
export PATH="/opt/nanobrew/prefix/bin:$PATH"

# 👇 mise (will cost 40ms)
if command -v mise >/dev/null 2>&1; then
  source "$GENERATED_FUNCTIONS_DIR/_mise.zsh"
fi

# 👇 sanitize ugit plugin path (avoid shadowing system commands like `install`)
# path=(${path:#$PLUGINS_DIR/ugit})
# path=(${path:#$PLUGINS_DIR/ugit/})

# 👇 opencode & modular
# for optional_bin in "$HOME/.opencode/bin" "$HOME/.modular/bin"; do
#   path=(${path:#$optional_bin})
#   path=(${path:#$optional_bin/})
#   [[ -d "$optional_bin" ]] && path+=("$optional_bin")
# done

# 👇 atuin
if command -v atuin >/dev/null 2>&1; then
  source "$GENERATED_FUNCTIONS_DIR/_atuin.zsh"
fi

# 👇 OpenClaw Completion
if [[ -f "$HOME/.openclaw/completions/openclaw.zsh" ]]; then
  source "$HOME/.openclaw/completions/openclaw.zsh"
fi
