if [[ -n ${DOTFILES_ROOT:-} ]]; then
  if [[ ! -d $DOTFILES_ROOT || ! -r $DOTFILES_ROOT/modules/zsh/env.zsh ]]; then
    print -u2 -- "DOTFILES_ROOT is invalid: $DOTFILES_ROOT (expected modules/zsh/env.zsh)"
    return 1
  fi
  DOTFILES_ROOT=${DOTFILES_ROOT:A}
else
  DOTFILES_ROOT=${${(%):-%N}:A:h:h:h}
fi
typeset -gx DOTFILES_ROOT

GENERATED_COMPLETIONS_DIR="$DOTFILES_ROOT/generated/completions"
GENERATED_FUNCTIONS_DIR="$DOTFILES_ROOT/generated/functions"
PLUGINS_DIR="$DOTFILES_ROOT/generated/plugins"

# 👇 XDG Config Home
export XDG_CONFIG_HOME="$HOME/.config"

# 👇 Emacs Mode
bindkey -e

# 👇 zsh Theme
if command -v starship >/dev/null 2>&1 && [[ -f "$GENERATED_FUNCTIONS_DIR/_starship.zsh" ]]; then
  source "$GENERATED_FUNCTIONS_DIR/_starship.zsh"
fi

# 👇 zsh options
setopt interactivecomments

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
WORDCHARS=${WORDCHARS//&}

autoload -Uz backward-word-match forward-word-match
zstyle ':zle:*' word-style normal
zstyle ':zle:*' word-chars "$WORDCHARS"

zle_shell_word_boundaries=(
  '\|' shell-token \
  '\|\|' shell-token \
  '\|&' shell-token \
  '\&' shell-token \
  '&&' shell-token \
  '\;' shell-token \
  '\(' shell-token \
  '\)' shell-token \
  '<' shell-token \
  '<<' shell-token \
  '<<<' shell-token \
  '<&' shell-token \
  '<>' shell-token \
  '>' shell-token \
  '>>' shell-token \
  '>&' shell-token \
  '[0-9]##<' shell-token \
  '[0-9]##>' shell-token \
  '[0-9]##>>' shell-token \
  '[0-9]##<&' shell-token \
  '[0-9]##>&' shell-token \
)
zstyle ':zle:backward-word' word-context "${zle_shell_word_boundaries[@]}"
zstyle ':zle:forward-word' word-context "${zle_shell_word_boundaries[@]}"
unset zle_shell_word_boundaries
zstyle ':zle:*:shell-token' word-style shell

_dotfiles_zle_shell_boundary_token() {
  emulate -L zsh
  setopt extendedglob

  case "$1" in
    ('|'|'||'|'|&'|'&'|'&&'|';'|'('|')'|'<'|'<<'|'<<<'|'<&'|'<>'|'>'|'>>'|'>&')
      return 0
      ;;
    (<->'<'|<->'>'|<->'>>'|<->'<&'|<->'>&')
      return 0
      ;;
  esac

  return 1
}

_dotfiles_zle_shell_boundary_prefix_length() {
  emulate -L zsh
  setopt extendedglob

  REPLY=0
  local text=$1

  if [[ $text = (#b)([0-9]##)(*) ]]; then
    local fd_length=${#match[1]}
    local after_fd=$match[2]
    local redirect
    for redirect in '>>' '>&' '<&' '>' '<'; do
      if [[ $after_fd[1,${#redirect}] == "$redirect" ]]; then
        REPLY=$(( fd_length + ${#redirect} ))
        return 0
      fi
    done
  fi

  local token
  for token in '<<<' '||' '|&' '&&' '>>' '<<' '<&' '<>' '>&' '|' '&' ';' '(' ')' '<' '>'; do
    if [[ $text[1,${#token}] == "$token" ]]; then
      REPLY=${#token}
      return 0
    fi
  done

  return 1
}

_dotfiles_zle_shell_boundary_suffix_length() {
  emulate -L zsh
  setopt extendedglob

  REPLY=0
  local text=$1
  local token

  for token in '||' '|&' '&&' '|' '&' ';' '(' ')'; do
    if [[ $text[-${#token},-1] == "$token" ]]; then
      REPLY=${#token}
      return 0
    fi
  done

  return 1
}

_dotfiles_zle_quoted_shell_token() {
  emulate -L zsh

  local token=$1
  (( ${#token} >= 2 )) || return 1

  if [[ $token[1] == "'" && $token[-1] == "'" ]]; then
    return 0
  fi

  if [[ $token[1] == '"' && $token[-1] == '"' ]]; then
    return 0
  fi

  if (( ${#token} >= 3 )) && [[ $token[1,2] == "\$'" && $token[-1] == "'" ]]; then
    return 0
  fi

  return 1
}

_dotfiles_zle_backward_word() {
  emulate -L zsh
  setopt extendedglob

  local without_trailing_space=${LBUFFER%%[[:space:]]##}
  local trailing_space_count=$(( ${#LBUFFER} - ${#without_trailing_space} ))

  local -a words
  words=(${(z)LBUFFER})
  local token=$words[-1]

  if [[ -n $token ]] && _dotfiles_zle_shell_boundary_token "$token"; then
    (( CURSOR -= ${#token} + trailing_space_count ))
    return
  fi

  if [[ -n $token ]] && _dotfiles_zle_quoted_shell_token "$token"; then
    (( CURSOR -= ${#token} + trailing_space_count ))
    return
  fi

  if _dotfiles_zle_shell_boundary_suffix_length "$without_trailing_space"; then
    (( CURSOR -= REPLY + trailing_space_count ))
    return
  fi

  zle dotfiles-backward-word-match
}

_dotfiles_zle_forward_word() {
  emulate -L zsh
  setopt extendedglob

  if _dotfiles_zle_shell_boundary_prefix_length "$RBUFFER"; then
    local token_length=$REPLY
    local after_token=${RBUFFER[token_length + 1,-1]}
    local following_space_count=0
    if [[ $after_token = (#b)([[:space:]]##)* ]]; then
      following_space_count=${#match[1]}
    fi
    (( CURSOR += token_length + following_space_count ))
    return
  fi

  local -a words
  words=(${(z)RBUFFER})
  local token=$words[1]

  if [[ -n $token ]] && _dotfiles_zle_quoted_shell_token "$token"; then
    local after_token=${RBUFFER[${#token} + 1,-1]}
    local following_space_count=0
    if [[ $after_token = (#b)([[:space:]]##)* ]]; then
      following_space_count=${#match[1]}
    fi
    (( CURSOR += ${#token} + following_space_count ))
    return
  fi

  zle dotfiles-forward-word-match
}

zle -N dotfiles-backward-word-match backward-word-match
zle -N dotfiles-forward-word-match forward-word-match
zle -N backward-word _dotfiles_zle_backward_word
zle -N forward-word _dotfiles_zle_forward_word

# 👇 Keybindings
bindkey '\e[1;5C' forward-word
bindkey '\e[1;5D' backward-word
bindkey "^A" beginning-of-line
bindkey "^B" backward-char
bindkey "^D" delete-word
bindkey "^E" end-of-line
bindkey "^F" forward-char

# 👇 Editor
if [[ "$TERM_PROGRAM" == "vscode" && -n ${commands[cursor]:-} ]]; then
  export EDITOR="${commands[cursor]} --wait"
  export VISUAL="$EDITOR"
fi

if [[ ( "$TERM_PROGRAM" == "zed" || "$TERM_PROGRAM" == "ghostty" ) && -n ${commands[zed]:-} ]]; then
  export EDITOR="${commands[zed]} --wait"
  export VISUAL="$EDITOR"
fi

# 👇 Functions
if [[ "$OSTYPE" == darwin* ]]; then
  source "$DOTFILES_ROOT/modules/zsh/macos.zsh"
  source "$DOTFILES_ROOT/modules/zsh/surge.zsh"
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

# 👇 Prek
export PREK_COLOR="never"

# 👇 tailspin
if command -v tailspin >/dev/null 2>&1; then
  if command -v ov >/dev/null 2>&1; then
    export TAILSPIN_PAGER="ov -f [FILE]"
  fi
fi

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
--color=bg+:#313244,bg:#1e1e2e,spinner:#f5e0dc,hl:#f38ba8 \
--color=fg:#cdd6f4,header:#f38ba8,info:#cba6f7,pointer:#f5e0dc \
--color=marker:#b4befe,fg+:#cdd6f4,prompt:#cba6f7,hl+:#f38ba8 \
--color=selected-bg:#45475a"

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

# 👇 mise (will cost 40ms)
if [[ -x "$HOME/.local/bin/mise" && ! -L "$HOME/.local/bin/mise" && -f "$GENERATED_FUNCTIONS_DIR/_mise.zsh" ]]; then
  # `.zshenv` exposes shims to non-interactive shells. Full activation owns the
  # interactive PATH, and auto-install is disabled, so remove that fallback.
  path=("${(@)path:#$HOME/.local/share/mise/shims}")
  source "$GENERATED_FUNCTIONS_DIR/_mise.zsh"
fi

# 👇 atuin
if command -v atuin >/dev/null 2>&1 && [[ -f "$GENERATED_FUNCTIONS_DIR/_atuin.zsh" ]]; then
  source "$GENERATED_FUNCTIONS_DIR/_atuin.zsh"
fi

# 👇 OpenClaw Completion
if [[ -f "$HOME/.openclaw/completions/openclaw.zsh" ]]; then
  source "$HOME/.openclaw/completions/openclaw.zsh"
fi

# 👇 broot
if [[ -f "$HOME/.config/broot/launcher/bash/br" ]]; then
  source "$HOME/.config/broot/launcher/bash/br"
fi
