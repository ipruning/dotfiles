# 👇 Linux
alias ...="cd ../.."

alias ..="cd .."

alias df="df -h"

alias du="du -h"

# macOS has no free(1).
[[ $OSTYPE == darwin* ]] || alias free="free -h"

alias grep="grep --color=auto"

alias ls="ls --color=auto"

alias q="exit"

alias rsyncssh="rsync -Pr"

alias cdr='cd "$(git rev-parse --show-toplevel)"'

# 👇 macOS
if [[ $OSTYPE == darwin* ]]; then
  alias surge="/Applications/Surge.app/Contents/Applications/surge-cli"
fi

jt () {
  local d saved_umask
  d="$(mktemp -d -t tempe.XXXXXXXX)" || return
  saved_umask=$(umask)
  umask 077
  builtin cd "$d" || { umask "$saved_umask"; return; }
  if [[ $# -eq 1 ]]; then
    mkdir -m 700 -p -- "$1" && builtin cd -- "$1"
  fi
  umask "$saved_umask"
  pwd
}

mcd () {
  [[ -z "${1:-}" ]] && return 2
  mkdir -p -- "$1" && cd -- "$1"
}

y () {
  local tmp cwd
  tmp="$(mktemp -t "yazi-cwd.XXXXXX")" || return
  command yazi "$@" --cwd-file="$tmp"
  IFS= read -r -d '' cwd < "$tmp" || true
  [ "$cwd" != "$PWD" ] && [ -d "$cwd" ] && builtin cd -- "$cwd"
  command rm -f -- "$tmp"
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
