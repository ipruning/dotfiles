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
