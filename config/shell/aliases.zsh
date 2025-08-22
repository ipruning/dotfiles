alias df="df -h"
alias du="du -h"
alias free="free -h"
alias grep="grep --color=auto"

# alias cp="cp -i"
# alias mkdir="mkdir -p"
# alias mv="mv -i"
# alias rm="rm -i"

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

if [[ $OSTYPE == linux* ]]; then
  alias ports="ss -tulpn"

  if type wl-copy &> /dev/null; then
    alias c="wl-copy"
    alias o="xdg-open ."
    alias p="wl-paste"
  fi
fi

if [[ $OSTYPE == darwin* ]]; then
  alias c="pbcopy"
  alias jr="jump-to-repo"
  alias js="jump-to-session"
  alias keyboardmaestro="/Applications/Keyboard\ Maestro.app/Contents/MacOS/keyboardmaestro"
  alias o="open ."
  alias p="pbpaste"
  alias ports="viddy --interval 1s 'lsof -i @127.0.0.1 | grep LISTEN'"
  alias surge="/Applications/Surge.app/Contents/Applications/surge-cli"

  function code() {
    open "$@" -a "Visual Studio Code"
  }

  function cursor() {
    open "$@" -a "Cursor"
  }

  function repoprompt() {
    open "repoprompt://open/$(pwd)"
  }
fi
