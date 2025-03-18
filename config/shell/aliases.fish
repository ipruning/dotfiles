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
alias g="git"
alias keyboardmaestro="/Applications/Keyboard\ Maestro.app/Contents/MacOS/keyboardmaestro"
alias ll="eza --all --git --group-directories-first --header --long --time-style long-iso"
alias lt="eza --all --git --group-directories-first --header --long --time-style long-iso --tree"
alias lzd="lazydocker"
alias lzg="lazygit"
alias o="open ."
alias p="pbpaste"
alias ports="viddy --interval 1s 'lsof -i @127.0.0.1 | grep LISTEN'"
alias surge="/Applications/Surge.app/Contents/Applications/surge-cli"

function cursor
  open $argv -a "Cursor"
end

function code
  open $argv -a "Visual Studio Code"
end
