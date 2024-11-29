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
alias ..='cd ..'
alias ...='cd ../..'

alias cpi='cp -i'
alias mvi='mv -i'
alias rmi='rm -i'

alias l='eza --icons --oneline'
alias la='eza --icons --all --oneline'
alias ll='eza --icons --long --git --time-style=long-iso'
alias lla='eza --icons --long --all --git --time-style=long-iso'
alias lt='eza --icons --long --all --git --time-style=long-iso --tree --level=3'

alias cpwd='printf "%q\n" "$(pwd)" | pbcopy'
alias ehost='${=EDITOR} /etc/hosts'
alias ezshrc='${=EDITOR} ~/.zshrc'
alias szshrc='source ~/.zshrc'
alias v='nvim'
alias ip='curl -4 ip.sb'
alias ipv6='curl -6 ip.sb'

#===============================================================================
# 👇
#===============================================================================
g-i() {
  git init
  git commit --allow-empty -m "init"
}

g-sync() {
  gh repo list --fork --visibility public --json owner,name | jq -r 'map(.owner.login + "/" + .name) | .[]' | xargs -t -L1 gh repo sync
}

r-fava() {
  fava ${HOME}/Databases/Ledger/main.bean -p 4000
}

r-update() {
  echo -e "\033[33mUpdating Homebrew...\033[0m"
  brew update

  echo -e "\033[33mUpdating tldr pages...\033[0m"
  tldr --update
}

r-upgrade() {
  echo -e "\033[33mUpgrading Homebrew formulas...\033[0m"
  brew upgrade

  echo -e "\033[33mCleaning up Homebrew...\033[0m"
  brew cleanup && brew autoremove

  echo -e "\033[33mUpgrading GitHub CLI extensions...\033[0m"
  gh extension upgrade --all

  echo -e "\033[33mUpgrading pipx packages...\033[0m"
  pipx upgrade-all

  echo -e "\033[33mUpdating mise...\033[0m"
  mise upgrade

  echo -e "\033[33mUpdating rust...\033[0m"
  rustup update && rustup self update
}

r-backup() {
  echo -e "\033[33mBacking up all packages...\033[0m"
  brew bundle dump --file="$HOME"/dotfiles/config/packages/Brewfile --force
  brew leaves >"$HOME"/dotfiles/config/packages/Brewfile.txt
  brew update
  cp "$HOME"/.zsh_history "$HOME"/Databases/Backup/CLI/zsh_history_$(date +\%Y_\%m_\%d_\%H_\%M_\%S).bak
  gh extension list | awk '{print $3}' >"$HOME"/dotfiles/config/packages/gh_extensions.txt
  ls /Applications | rg '\.app' | sed 's/\.app//g' >"$HOME"/dotfiles/config/packages/macos_applications.txt
  ls /Applications/Setapp | rg '\.app' | sed 's/\.app//g' >"$HOME"/dotfiles/config/packages/macos_setapp.txt
  pipx list --json | jq ".venvs | .[] | .metadata.main_package.package" -r >"$HOME"/dotfiles/config/packages/pipx.txt
}

r-completion() {
  echo -e "\033[33mGenerating completions...\033[0m"
  rm -f ~/.zcompdump
  compinit
}
