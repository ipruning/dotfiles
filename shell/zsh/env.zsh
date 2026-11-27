if [[ -n ${DOTFILES_ROOT:-} ]]; then
  if [[ ! -d $DOTFILES_ROOT || ! -r $DOTFILES_ROOT/shell/zsh/env.zsh ]]; then
    print -u2 -- "DOTFILES_ROOT is invalid: $DOTFILES_ROOT (expected shell/zsh/env.zsh)"
    return 1
  fi
  DOTFILES_ROOT=${DOTFILES_ROOT:A}
else
  DOTFILES_ROOT=${${(%):-%N}:A:h:h:h}
fi
typeset -gx DOTFILES_ROOT

GENERATED_FUNCTIONS_DIR="$DOTFILES_ROOT/generated/functions"
PLUGINS_DIR="$DOTFILES_ROOT/generated/plugins"

# 👇 XDG Config Home
export XDG_CONFIG_HOME="$HOME/.config"

# 👇 zsh Theme
if command -v starship >/dev/null 2>&1 && [[ -f "$GENERATED_FUNCTIONS_DIR/_starship.zsh" ]]; then
  source "$GENERATED_FUNCTIONS_DIR/_starship.zsh" || eval "$(starship init zsh)"
fi

# 👇 zsh options
setopt interactivecomments

# 👇 Editor
if [[ "$TERM_PROGRAM" == "vscode" && -n ${commands[cursor]:-} ]]; then
  export EDITOR="${commands[cursor]} --wait"
  export VISUAL="$EDITOR"
elif [[ ( "$TERM_PROGRAM" == "zed" || "$TERM_PROGRAM" == "ghostty" ) && -n ${commands[zed]:-} ]]; then
  export EDITOR="${commands[zed]} --wait"
  export VISUAL="$EDITOR"
elif [[ -z ${EDITOR:-} ]]; then
  for _editor in nvim vim vi; do
    if [[ -n ${commands[$_editor]:-} ]]; then
      export EDITOR="${commands[$_editor]}"
      export VISUAL="${VISUAL:-$EDITOR}"
      break
    fi
  done
  unset _editor
fi

# Assigning a vi-like EDITOR/VISUAL switches Zsh to viins unless emacs mode is
# re-asserted before plugins and tools bind keys on the main keymap.
bindkey -e

# 👇 Functions
if [[ "$OSTYPE" == darwin* ]]; then
  source "$DOTFILES_ROOT/shell/zsh/macos.zsh"
  source "$DOTFILES_ROOT/shell/zsh/surge.zsh"
fi

# 👇 1Password Environment Loader
_openv_resolve_op_env_bin() {
  local override="${OPENV_OP_ENV_BIN:-}"
  if [[ -n "$override" ]]; then
    if [[ ! -x "$override" ]]; then
      echo "OPENV_OP_ENV_BIN is not executable: $override" >&2
      return 1
    fi
    echo "$override"
    return
  fi

  if command -v op >/dev/null 2>&1; then
    command -v op
    return
  fi

  echo "op CLI not found in PATH" >&2
  return 1
}

openv() {
  local id="${1:-}"
  local op_env_bin output

  if [[ -z "$id" ]]; then
    echo "Usage: openv <1password-environment-id>" >&2
    return 2
  fi

  if ! op_env_bin="$(_openv_resolve_op_env_bin)"; then
    return 1
  fi

  if output="$("$op_env_bin" environment read "$id" 2>&1)"; then
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

# 👇 OrbStack
if [[ -f "$HOME/.orbstack/shell/init.zsh" ]]; then
  source "$HOME/.orbstack/shell/init.zsh"
  # OrbStack appends with scalar PATH/fpath assignments, so reassign the tied
  # unique arrays once to collapse entries inherited from the parent process.
  path=("${path[@]}")
  fpath=("${fpath[@]}")
fi

# 👇 zoxide
if command -v zoxide >/dev/null 2>&1 && [[ -f "$GENERATED_FUNCTIONS_DIR/_zoxide.zsh" ]]; then
  source "$GENERATED_FUNCTIONS_DIR/_zoxide.zsh"
fi

# 👇 tv
if command -v tv >/dev/null 2>&1 && [[ -f "$GENERATED_FUNCTIONS_DIR/_tv.zsh" ]]; then
  source "$GENERATED_FUNCTIONS_DIR/_tv.zsh"
fi

# 👇 fzf
if command -v fd >/dev/null 2>&1; then
  export FZF_DEFAULT_COMMAND="fd"
else
  unset FZF_DEFAULT_COMMAND
fi

export FZF_DEFAULT_OPTS=" \
--multi \
--style minimal \
--bind 'ctrl-y:accept' \
--color=base16,fg:-1,bg:-1,fg+:-1,bg+:0,selected-bg:8 \
--color=hl:1,hl+:1,header:1,info:5,prompt:5,spinner:5,pointer:5,marker:4"

# 👇 fzf-tab
if [[ -f "$PLUGINS_DIR"/fzf-tab/fzf-tab.plugin.zsh ]]; then
  source "$PLUGINS_DIR"/fzf-tab/fzf-tab.plugin.zsh
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
if [[ -n ${HOMEBREW_PREFIX:-} && -d "$HOMEBREW_PREFIX/opt/mysql-client/lib/pkgconfig" ]]; then
  export PKG_CONFIG_PATH="$HOMEBREW_PREFIX/opt/mysql-client/lib/pkgconfig:$PKG_CONFIG_PATH"
fi

# 👇 try-rs
if command -v try-rs >/dev/null 2>&1 && [[ -f "$GENERATED_FUNCTIONS_DIR/_try-rs.zsh" ]]; then
  source "$GENERATED_FUNCTIONS_DIR/_try-rs.zsh"
fi

# 👇 Herdr (temporarily disabled for terminal launch debugging)
# TODO: Re-enable this block after debugging no longer requires a raw Ghostty
# shell. HERDR_ENV remains the recursion boundary when restored.
# if [[ "$TERM_PROGRAM" == "ghostty" && -z ${SSH_TTY:-} && -z ${HERDR_ENV:-} && \
#   ${HERDR_GHOSTTY_AUTOSTART:-1} != 0 ]] && \
#   herdr --version >/dev/null 2>&1; then
#   exec herdr
# fi

# 👇 atuin
if command -v atuin >/dev/null 2>&1 && [[ -f "$GENERATED_FUNCTIONS_DIR/_atuin.zsh" ]]; then
  if [[ -z ${ATUIN_SESSION:-} || ${ATUIN_SHLVL:-} != "$SHLVL" ]]; then
    () {
      local random_hex
      zmodload zsh/datetime 2>/dev/null || return 0
      random_hex=$(command -p openssl rand -hex 10 2>/dev/null) || return 0
      [[ ${#random_hex} == 20 && $random_hex != *[^0-9a-f]* ]] || return 0
      # UUIDv7 uses 48 bits of Unix milliseconds, followed by random bits
      # with the version and variant set. Atuin reads the session timestamp.
      local -i unix_ms=$(( EPOCHREALTIME * 1000 ))
      printf -v ATUIN_SESSION '%012x7%s%x%s' "$unix_ms" "$random_hex[1,3]" \
        "$(( (16#${random_hex[4]} & 3) | 8 ))" "$random_hex[5,19]"
      export ATUIN_SESSION ATUIN_SHLVL="$SHLVL"
    }
  fi
  source "$GENERATED_FUNCTIONS_DIR/_atuin.zsh"
fi

unset GENERATED_FUNCTIONS_DIR PLUGINS_DIR
