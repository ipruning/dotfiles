# 👇 Linux
alias ...="cd ../.."

alias ..="cd .."

alias df="df -h"

alias du="du -h"

alias free="free -h"

alias grep="grep --color=auto"

alias ls="ls --color=auto"

alias q="exit"

alias rsyncssh="rsync -Pr --rsh=ssh"

alias cdr='cd $(git rev-parse --show-toplevel)'

# 👇 macOS
if [[ $OSTYPE == darwin* ]]; then
  alias jr="jump-to-repo"

  alias js="jump-to-session"

  alias keyboardmaestro="/Applications/Keyboard\ Maestro.app/Contents/MacOS/keyboardmaestro"

  alias surge="/Applications/Surge.app/Contents/Applications/surge-cli"
fi

jt () {
  local d
  d="$(mktemp -d -t tempe.XXXXXXXX)" || return
  umask 077
  builtin cd "$d" || return
  if [[ $# -eq 1 ]]; then
    mkdir -m 700 -p -- "$1" && builtin cd -- "$1"
  fi
  pwd
}

mcd () {
  [[ -z "${1:-}" ]] && return 2
  mkdir -p -- "$1" && cd -- "$1"
}

y () {
  local tmp="$(mktemp -t "yazi-cwd.XXXXXX")" cwd
  yazi "$@" --cwd-file="$tmp"
  if cwd="$(command cat -- "$tmp")" && [ -n "$cwd" ] && [ "$cwd" != "$PWD" ]; then
    builtin cd -- "$cwd"
  fi
  rm -f -- "$tmp"
}

note() {
  if [[ $# -eq 0 ]]; then
    cat ~/.sticky_note 2>/dev/null || echo "No note set"
  elif [[ "$1" == "-c" ]]; then
    rm -f ~/.sticky_note
  else
    echo "$*" > ~/.sticky_note
  fi
}

alias -s md="bat"
alias -s txt="bat"

alias -g DN='> /dev/null'
alias -g NE='2>/dev/null'
alias -g NUL='>/dev/null 2>&1'

alias -g JQ='| jq'

alias -g C='| c'
alias -g P='p |'
