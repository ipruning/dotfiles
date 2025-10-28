alias df="df -h"
alias du="du -h"
alias free="free -h"
alias grep="grep --color=auto"

alias ...="cd ../.."
alias ..="cd .."

if type atuin &> /dev/null; then
  alias history="atuin history list --format '{time} - [{duration}] - {command}'"
else
  alias history="history 1"
fi

if type eza &> /dev/null; then
  alias ll="eza --all --git --group-directories-first --header --long --time-style long-iso"
  alias ls="eza"
  alias lt="eza --all --git --group-directories-first --header --long --time-style long-iso --tree"
else
  alias ll="ls -lAh"
  alias ls="ls --color=auto"
fi

if type bat &> /dev/null; then
  alias cat="bat"
fi

alias cdr='cd $(git rev-parse --show-toplevel)'
alias d="lazydocker"
alias dateutc="date -u +%Y-%m-%dT%H:%M:%SZ"
alias g="lazygit"
alias q="exit"
alias rsyncssh="rsync -Pr --rsh=ssh"

if [[ $OSTYPE == linux* ]]; then
  alias ports="ss -tulpn"
fi

if [[ $OSTYPE == darwin* ]]; then
  alias jr="jump-to-repo"
  alias js="jump-to-session"
  alias keyboardmaestro="/Applications/Keyboard\ Maestro.app/Contents/MacOS/keyboardmaestro"
  alias ports="viddy --interval 1s 'lsof -i @127.0.0.1 | grep LISTEN'"
  alias surge="/Applications/Surge.app/Contents/Applications/surge-cli"

  function repoprompt() {
    open "repoprompt://open/$(pwd)"
  }
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
