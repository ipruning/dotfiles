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
alias cpi='cp -i'
alias mvi='mv -i'

#===============================================================================
# 👇
#===============================================================================
alias cat='bat --paging=never'
# alias cp='fcp'
# alias cut='choose'
# alias df='duf'
# alias dig='dog'
# alias du='dust'
# alias find='fd'
# alias grep='rg'
# alias br='br -s'
alias l='lsd'
alias la='lsd -a'
alias ll='lsd -lh'
alias lla='lsd -la'
alias lt='lsd --tree'
if [[ -n $SSH_CONNECTION ]]; then
  alias lsd='lsd --icon never'
fi
# alias ping='gping'
# alias ps='procs'
# alias rip='rip -i'
alias rmi='rm -i'
# alias sed="sd"
# alias sort="huniq"
# alias top='htop'
# alias vim='nvim'
alias v='nvim'
# alias gptcommit='gptcommit'

#===============================================================================
# 👇
#===============================================================================
alias cwd='printf "%q\n" "$(pwd)" | pbcopy'
alias ehost='${=EDITOR} /etc/hosts'
alias eohmyzsh='${=EDITOR} ~/.oh-my-zsh'
alias ezshrc='${=EDITOR} ~/.zshrc'
alias szshrc='source ~/.zshrc'
alias gii='git init && git commit --allow-empty -m "init"'
alias ip='curl -4 ip.sb'
alias ipv6='curl -6 ip.sb'

g-i() {
  git init
  git commit --allow-empty -m "init"
}

g-sync() {
  gh repo list --fork --visibility public --json owner,name | jq -r 'map(.owner.login + "/" + .name) | .[]' | xargs -t -L1 gh repo sync
}

alias r-archivebox='cd /Volumes/Workspace/Databases/ArchiveBox && archivebox server'
alias r-bb='/Applications/OpenBB\ Terminal/OpenBB\ Terminal'
alias r-citespace='cd ${HOME}/Databases/CiteSpace/5.8.R3/ && ./StartCiteSpace_M1_Pro.sh'
alias r-deepl='colima start && docker run -itd -p 8080:80 zu1k/deepl'
alias r-fava='fava ${HOME}/Databases/Ledger/main.bean -p 4000'
alias r-jupyter-lab='${HOME}/.conda/envs/LearningAI/bin/jupyter-lab'
alias r-jupyter='${HOME}/.conda/envs/LearningAI/bin/jupyter-notebook'
alias r-lol='open /Applications/League\ of\ Legends.app/ --args --locale=zh_CN'
alias r-p2t='${HOME}/Databases/Stacks/Utilities/Pix2Text/.venv/bin/python ${HOME}/Databases/Stacks/Utilities/Pix2Text/scripts/screenshot_daemon.py'
alias r-unm='node ${HOME}/Databases/Stacks/Utilities/UnblockNeteaseMusic/app.js -p 80:443 -f 103.126.92.132'

r-update() {
  asdf latest --all
  brew cu
  brew update
  tldr --update
}

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
  wget https://raw.githubusercontent.com/reorx/ai.py/master/ai.py -O "${HOME}"/Dotfiles/bin/ai && chmod +x "${HOME}"/Dotfiles/bin/ai
}

r-backup() {
  brew update
  brew bundle dump --file="$HOME"/dotfiles/assets/others/packages/Brewfile --force
  brew leaves >"$HOME"/dotfiles/assets/others/packages/Brewfile.txt
  cargo install --list | grep -v '^[[:blank:]]' | awk '{print $1}' >"$HOME"/dotfiles/assets/others/packages/cargo.txt
  ls /Applications | rg '\.app' | sed 's/\.app//g' >"$HOME"/dotfiles/assets/others/packages/macos_applications.txt
  ls /Applications/Setapp | rg '\.app' | sed 's/\.app//g' >"$HOME"/dotfiles/assets/others/packages/macos_setapp.txt
  npm list --location=global --json | jq ".dependencies | keys[]" -r >"$HOME"/dotfiles/assets/others/packages/npm.txt
  pipx list --json | jq ".venvs | .[] | .metadata.main_package.package" -r >"$HOME"/dotfiles/assets/others/packages/pipx.txt
  code --list-extensions >"$HOME"/dotfiles/assets/others/packages/vscode_extensions.txt
  cp "$HOME"/.zsh_history "$HOME"/Databases/Backup/CLI/zsh_history_$(date +\%Y_\%m_\%d_\%H_\%M_\%S).bak
}
