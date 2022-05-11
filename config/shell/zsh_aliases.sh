#!/usr/bin/env bash

#===============================================================================
# 👇 Aliases
# 👇 For a full list of active aliases, run `alias`.
#===============================================================================

case $SYSTEM_ARCH in
arm64*)
  alias x86_64='arch -x86_64 zsh --login'
  alias x86_64_run='arch -x86_64 zsh -c'
  alias brow='/usr/local/homebrew/bin/brew'
  ;;
x86_64*) ;;
esac

if [[ -n $SSH_CONNECTION ]]; then
  alias l='lsd -l --icon never'
  alias la='lsd -a --icon never'
  alias lla='lsd -la --icon never'
  alias lt='lsd --tree --icon never'
  alias ls='lsd --icon never'
else
  alias l='lsd -l'
  alias la='lsd -a'
  alias lla='lsd -la'
  alias lt='lsd --tree'
  alias jupyter='jupyter-notebook'
  alias jupyter-lab='${HOME}/.conda/envs/python3.10/bin/jupyter-lab'
  alias r-unm='node ${HOME}/Stacks/Utilities/UnblockNeteaseMusic/app.js -p 80:443 -f 103.126.92.132'
  alias r-fava='fava ${HOME}/Database/Ledger/main.bean -p 4000'
  alias r-citespace='cd ${HOME}/Database/CiteSpace/5.8.R3/ && ./StartCiteSpace_M1_Pro.sh'
  # alias r-archivebox='cd ${HOME}/Database/ArchiveBox/ && archivebox server'
  alias r-archivebox='cd /Volumes/Workspace/Database/ArchiveBox && archivebox server'
  alias r-update='brew update'
  alias r-upgrade='brew upgrade && brew cu && pipx upgrade-all && npx npm-check --global --update-all && cargo install-update -a && gh extension upgrade --all'
fi

alias rip='rip -i'                          # A safe and ergonomic alternative to rm
alias cwd='printf "%q\n" "$(pwd)" | pbcopy' # Copy current working directory to clipboard

alias rmi='rm -i'
alias cpi='cp -i'
alias mvi='mv -i'
alias ehost='${=EDITOR} /etc/hosts'
alias eohmyzsh='${=EDITOR} ~/.oh-my-zsh'
alias ezshrc='${=EDITOR} ~/.zshrc'
alias szshrc='source ~/.zshrc'
alias ip='curl -4 ip.sb'
alias ipv6='curl -6 ip.sb'

# alias cat='bat'
# alias cp='fcp'
# alias df='duf'
# alias dig='dog'
# alias du='dust'
# alias find='fd'
# alias grep='rg'
# alias ping='gping'
# alias ps='procs'
# alias sed="sd"
# alias top='htop'
alias vi='nvim'
alias vim='nvim'
