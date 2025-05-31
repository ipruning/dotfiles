# Linux Aliases Part 1
alias cp="cp -i"
alias df="df -h"
alias du="du -h"
alias egrep="egrep --color=auto"
alias fgrep="fgrep --color=auto"
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
alias d="lazydocker"
alias g="lazygit"
alias hg="history | grep"
alias ports="ss -tulpn"
alias rsyncssh="rsync -Pr --rsh=ssh"

# macOS Aliases
alias c="pbcopy"
alias cdr='cd $(git rev-parse --show-toplevel)'
alias gb="git browse"
alias gtidy="gh tidy"
alias history="atuin history list --format '{time} - [{duration}] - {command}'"
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

function repo() {
  open "repoprompt://open/$(pwd)"
}

# Git Aliases
alias gaa="git add --all --verbose"
alias gac="codegpt commit --no_confirm"
alias gc="git commit"
alias gd="git diff"
alias gdc="git diff --cached"
alias gs="git switch"
alias gst="git status"
alias pr="gh pr view -w"
