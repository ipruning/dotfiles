alias ..='cd ..'
alias ...='cd ../..'

alias x86_64='arch -x86_64 zsh --login'
alias x86_64_run='arch -x86_64 zsh -c'
alias brow='/usr/local/homebrew/bin/brew'

alias l='eza --icons --oneline'
alias la='eza --icons --all --oneline'
alias ll='eza --icons --long --git --time-style=long-iso'
alias lla='eza --icons --long --all --git --time-style=long-iso'
alias lt='eza --icons --long --all --git --time-style=long-iso --tree --level=3'

alias ip='curl -4 ip.sb'
alias ipv6='curl -6 ip.sb'

alias vim='nvim'

alias cp='cp -i'
alias df='df -h'
alias du='du -h'
alias mkdir='mkdir -p'
alias mv='mv -i'
alias rm='rm -i'

function r-completion() {
  echo -e "\033[33mGenerating completions...\033[0m"
  rm -f ~/.zcompdump
  compinit
}

function r-update() {
  echo -e "\033[33mUpdating Homebrew...\033[0m"
  brew update

  echo -e "\033[33mUpdating tldr pages...\033[0m"
  tldr --update
}

function r-upgrade() {
  echo -e "\033[33mUpgrading Homebrew formulas...\033[0m"
  brew upgrade

  echo -e "\033[33mCleaning up Homebrew...\033[0m"
  brew cleanup && brew autoremove

  echo -e "\033[33mUpgrading GitHub CLI extensions...\033[0m"
  gh extension upgrade --all

  echo -e "\033[33mUpdating mise...\033[0m"
  mise upgrade --bump
}

function r-backup() {
  echo -e "\033[33mBacking up all packages...\033[0m"
  brew bundle dump --file="$HOME"/dotfiles/config/packages/Brewfile --force
  brew leaves >"$HOME"/dotfiles/config/packages/Brewfile.txt
  gh extension list | awk '{print $3}' >"$HOME"/dotfiles/config/packages/gh_extensions.txt
  find /Applications -maxdepth 1 -name "*.app" -exec basename {} .app \; | sort >"$HOME"/dotfiles/config/packages/macos_applications.txt
  find /Applications/Setapp -maxdepth 1 -name "*.app" -exec basename {} .app \; | sort >"$HOME"/dotfiles/config/packages/macos_setapp.txt
}
