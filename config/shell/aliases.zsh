# Linux Aliases Part 1
alias cp="cp -i"
alias df="df -h"
alias du="du -h"
alias free="free -h"
alias grep="grep --color=auto"
alias history="history 1"
alias mkdir="mkdir -p"
alias mv="mv -i"
alias rm="rm -i"

if type eza &> /dev/null; then
  alias ll="eza --all --git --group-directories-first --header --long --time-style long-iso"
  alias ls="eza"
  alias lt="eza --all --git --group-directories-first --header --long --time-style long-iso --tree"
else
  alias ll="ls -lAh"
  alias ls="ls --color=auto"
fi

# Linux Aliases Part 2
alias ...="cd ../.."
alias ..="cd .."
alias cdr='cd $(git rev-parse --show-toplevel)'
alias d="lazydocker"
alias dateutc="date -u +%Y-%m-%dT%H:%M:%SZ"
alias g="lazygit"
alias ports="ss -tulpn"

# macOS Aliases
alias c="pbcopy"
alias cat="bat"
alias history="atuin history list --format '{time} - [{duration}] - {command}'"
alias jr="jump-to-repo"
alias js="jump-to-session"
alias keyboardmaestro="/Applications/Keyboard\ Maestro.app/Contents/MacOS/keyboardmaestro"
alias o="open ."
alias p="pbpaste"
alias ports="viddy --interval 1s 'lsof -i @127.0.0.1 | grep LISTEN'"
alias surge="/Applications/Surge.app/Contents/Applications/surge-cli"
alias z="zed ."

function code() {
  open "$@" -a "Visual Studio Code"
}

function cursor() {
  open "$@" -a "Cursor"
}

function repoprompt() {
  open "repoprompt://open/$(pwd)"
}
