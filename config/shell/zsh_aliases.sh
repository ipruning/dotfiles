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

#===============================================================================
# 👇
#===============================================================================
alias cat='bat --paging=never'
# alias cp='fcp'
alias cpi='cp -i'
# alias cut='choose'
# alias df='duf'
# alias dig='dog'
# alias du='dust'
# alias find='fd'
# alias grep='rg'
alias l='lsd'
alias la='lsd -a'
alias ll='lsd -lh'
alias lla='lsd -la'
alias lt='lsd --tree'
if [[ -n $SSH_CONNECTION ]]; then
  alias lsd='lsd --icon never'
fi
alias mvi='mv -i'
# alias ping='gping'
# alias ps='procs'
# alias rip='rip -i'
alias rmi='rm -i'
# alias sed="sd"
# alias sort="huniq"
# alias top='htop'
alias v='nvim'
# alias ai='ai'
# alias chatgpt='chatgpt'
# alias copilot='copilot'
# alias gptcommit='gptcommit'

#===============================================================================
# 👇
#===============================================================================
alias cwd='printf "%q\n" "$(pwd)" | pbcopy' # Copy current working directory to clipboard
alias ehost='${=EDITOR} /etc/hosts'
alias eohmyzsh='${=EDITOR} ~/.oh-my-zsh'
alias ezshrc='${=EDITOR} ~/.zshrc'
alias szshrc='source ~/.zshrc'
alias gii='git init && git commit --allow-empty -m "init"' # Initialize a git repo and make an empty commit
alias ip='curl -4 ip.sb'
alias ipv6='curl -6 ip.sb'

#===============================================================================
# 👇 run
#===============================================================================
alias r-archivebox='cd /Volumes/Workspace/Databases/ArchiveBox && archivebox server'
alias r-bb='/Applications/OpenBB\ Terminal/OpenBB\ Terminal'
alias r-citespace='cd ${HOME}/Databases/CiteSpace/5.8.R3/ && ./StartCiteSpace_M1_Pro.sh'
alias r-deepl='colima start && docker run -itd -p 8080:80 zu1k/deepl'
alias r-fava='fava ${HOME}/Databases/Ledger/main.bean -p 4000'
alias r-jupyter-lab='${HOME}/.conda/envs/LearningAI/bin/jupyter-lab'
alias r-jupyter='${HOME}/.conda/envs/LearningAI/bin/jupyter-notebook'
alias r-lol='open /Applications/League\ of\ Legends.app/ --args --locale=zh_CN'
alias r-p2t='${HOME}/Stacks/Utilities/Pix2Text/.venv/bin/python ${HOME}/Stacks/Utilities/Pix2Text/scripts/screenshot_daemon.py'
alias r-unm='node ${HOME}/Stacks/Utilities/UnblockNeteaseMusic/app.js -p 80:443 -f 103.126.92.132'

#===============================================================================
# 👇 run update
#===============================================================================
r-update() {
  asdf latest --all
  brew cu
  brew update
  tldr --update
}

#===============================================================================
# 👇 run upgrade
#===============================================================================
r-upgrade() {
  asdf plugin update --all
  asdf update
  brew upgrade
  cargo install-update --all
  # conda update --all
  gh extension upgrade --all
  juliaup update
  # mas upgrade
  npx npm-check --global --update-all
  omz update
  python -m pip install --upgrade pip
  pipx upgrade-all
  rustup self update
  rustup update
  wget https://raw.githubusercontent.com/vast-ai/vast-python/master/vast.py -O "${HOME}"/Dotfiles/bin/vast
  chmod +x "${HOME}"/Dotfiles/bin/vast
  wget https://raw.githubusercontent.com/reorx/ai.py/master/ai.py -O "${HOME}"/Dotfiles/bin/ai
  chmod +x "${HOME}"/Dotfiles/bin/ai
}
