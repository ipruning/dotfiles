# Linux Aliases Part 1
alias cp="cp -i"
alias df="df -h"
alias du="du -h"
alias egrep="egrep --color=auto"
alias fgrep="fgrep --color=auto"
alias free="free -h"
alias grep="grep --color=auto"
alias ls="ls --color=auto"
alias mkdir="mkdir -p"
alias mv="mv -i"
alias rm="rm -i"

# Linux Aliases Part 2
alias ...="cd ../.."
alias ..="cd .."
alias hg="history | grep"
alias ll="ls -lAh"
alias ports="ss -tulpn"

# macOS Aliases Part 1
alias c="pbcopy"
alias d="lazydocker"
alias g="lazygit"
alias keyboardmaestro="/Applications/Keyboard\ Maestro.app/Contents/MacOS/keyboardmaestro"
alias ll="eza --all --git --group-directories-first --header --long --time-style long-iso"
alias lt="eza --all --git --group-directories-first --header --long --time-style long-iso --tree"
alias o="open ."
alias p="pbpaste"
alias ports="viddy --interval 1s 'lsof -i @127.0.0.1 | grep LISTEN'"
alias surge="/Applications/Surge.app/Contents/Applications/surge-cli"

alias gaa="git add --all --verbose"
alias gac="codegpt commit --no_confirm"
alias gb="git browse"
alias gc="koji"
alias gco="git checkout" 
alias gd="git diff"
alias gdc="git diff --cached"
alias gj="jump-to-repo"
alias gl="git log"
alias go="open ."
alias gs="git status"
alias gtidy="gh tidy"

function code() {
  open "$@" -a "Visual Studio Code"
}

function cursor() {
  open "$@" -a "Cursor"
}

function repo() {
  open "repoprompt://open/$(pwd)"
}
