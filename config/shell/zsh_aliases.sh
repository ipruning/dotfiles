#===============================================================================
# 👇 Aliases
# 👇 For a full list of active aliases, run `alias`.
#===============================================================================
case $SYSTEM_TYPE in
mac_arm64)
  alias x86_64='arch -x86_64 zsh --login'
  alias x86_64_run='arch -x86_64 zsh -c'
  alias brow='/usr/local/homebrew/bin/brew'
  ;;
esac

alias l='lsd'
alias la='lsd -a'
alias ll='lsd -lh'
alias lla='lsd -la'
alias lt='lsd --tree'
if [[ -n $SSH_CONNECTION ]]; then
  alias lsd='lsd --icon never'
fi

alias jupyter='jupyter-notebook'
alias jupyter-lab='${HOME}/.conda/envs/python3.10/bin/jupyter-lab'

alias r-archivebox='cd /Volumes/Workspace/Database/ArchiveBox && archivebox server'
alias r-citespace='cd ${HOME}/Database/CiteSpace/5.8.R3/ && ./StartCiteSpace_M1_Pro.sh'
alias r-deepl='colima start && docker run -itd -p 8080:80 zu1k/deepl'
alias r-fava='fava ${HOME}/Database/Ledger/main.bean -p 4000'
alias r-bb='/Applications/OpenBB\ Terminal/OpenBB\ Terminal'
alias r-unm='node ${HOME}/Stacks/Utilities/UnblockNeteaseMusic/app.js -p 80:443 -f 103.126.92.132'
alias r-lol='open /Applications/League\ of\ Legends.app/ --args --locale=zh_CN'

alias r-update='brew update && brew cu && asdf latest --all && tldr --update'
alias r-upgrade='brew upgrade && pipx upgrade-all && npx npm-check --global --update-all && cargo install-update --all && gh extension upgrade --all && conda update --all && asdf update && asdf plugin update --all'
# mas upgrade
# omz update
# pio update && pio upgrade
# rustup self update
# xcodes update

alias cpi='cp -i'
alias cwd='printf "%q\n" "$(pwd)" | pbcopy' # Copy current working directory to clipboard
alias ehost='${=EDITOR} /etc/hosts'
alias eohmyzsh='${=EDITOR} ~/.oh-my-zsh'
alias ezshrc='${=EDITOR} ~/.zshrc'
alias gii='git init && git commit --allow-empty -m "init"' # Initialize a git repo and make an empty commit
alias ip='curl -4 ip.sb'
alias ipv6='curl -6 ip.sb'
alias mvi='mv -i'
alias rmi='rm -i'
alias szshrc='source ~/.zshrc'

alias cat='bat --paging=never'
# alias cp='fcp'
# alias cut='choose'
# alias df='duf'
# alias dig='dog'
# alias du='dust'
# alias find='fd'
# alias grep='rg'
# alias ping='gping'
# alias ps='procs'
alias rip='rip -i' # A safe and ergonomic alternative to rm
# alias sed="sd"
# alias sort="huniq"
# alias top='htop'
alias v='nvim'
