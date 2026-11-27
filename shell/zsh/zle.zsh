# ZLE line-editing mode, custom shell-boundary word motion, and keybindings.

# 👇 Emacs Mode
bindkey -e

# 👇 Editing widgets
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

# 👇 Wordchars & shell-boundary motion
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
