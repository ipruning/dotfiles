#!/usr/bin/env bash

function main {
  echo "${BLUE}Installing essential${NORMAL}"
  sudo apt-get install -y -q build-essential
  sudo locale-gen en_US.UTF-8

  echo "${BLUE}Installing zsh${NORMAL}"
  sudo apt-get install -y zsh
  chsh -s "$(which zsh)"

  echo "${BLUE}Installing oh-my-zsh${NORMAL}"
  export CHSH=no
  export RUNZSH=no
  export KEEP_ZSHRC=yes
  sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" --unattended --keep-zshrc

  echo "${BLUE}Installing zsh dotiles${NORMAL}"
  if [ -e "$HOME"/.zshrc ]; then
    mv "$HOME"/.zshrc "$HOME"/.zshrc.bak
    cp "$HOME"/dotfiles/config/shell/mac/zshrc.sh "$HOME"/.zshrc
  else
    cp "$HOME"/dotfiles/config/shell/mac/zshrc.sh "$HOME"/.zshrc
  fi
  if [ -e "$HOME"/.zprofile ]; then
    mv "$HOME"/.zprofile "$HOME"/.zprofile.bak
    cp "$HOME"/dotfiles/config/shell/mac/zprofile.sh "$HOME"/.zprofile
  else
    cp "$HOME"/dotfiles/config/shell/mac/zprofile.sh "$HOME"/.zprofile
  fi

  echo "${BLUE}Installing zsh plugins${NORMAL}"
  ZSH_CUSTOM=${ZSH_CUSTOM:-~/.oh-my-zsh/custom}
  git clone https://github.com/TamCore/autoupdate-oh-my-zsh-plugins "$ZSH_CUSTOM"/plugins/autoupdate
  git clone https://github.com/wfxr/forgit "$ZSH_CUSTOM"/plugins/forgit
  git clone https://github.com/Aloxaf/fzf-tab "$ZSH_CUSTOM"/plugins/fzf-tab
  git clone https://github.com/paulirish/git-open.git "$ZSH_CUSTOM"/plugins/git-open
  git clone https://github.com/zsh-users/zsh-autosuggestions "$ZSH_CUSTOM"/plugins/zsh-autosuggestions
  git clone https://github.com/zsh-users/zsh-completions "$ZSH_CUSTOM"/plugins/zsh-completions
  git clone https://github.com/sukkaw/zsh-osx-autoproxy "$ZSH_CUSTOM"/plugins/zsh-osx-autoproxy
  git clone https://github.com/zsh-users/zsh-syntax-highlighting.git "$ZSH_CUSTOM"/plugins/zsh-syntax-highlighting
  git clone https://github.com/jeffreytse/zsh-vi-mode "$ZSH_CUSTOM"/plugins/zsh-vi-mode

  echo "${BLUE}Installing Homebrew${NORMAL}"
  which brew || NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

  echo "${BLUE}Installing Homebrew packages${NORMAL}"
  echo 'eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"' >>/root/.profile
  eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
  brew install gcc

  echo "${BLUE}Installing Homebrew packages${NORMAL}"
  brew bundle --file="$HOME"/dotfiles/assets/others/packages/Brewfile_dev

  echo "${BLUE}Installing mackup${NORMAL}"
  ln -sf "$HOME"/dotfiles/config/mackup/.mackup.cfg "$HOME"/.mackup.cfg
  ln -sf "$HOME"/dotfiles/config/mackup/.mackup "$HOME"/.mackup

  echo "${BLUE}Restoring dotfiles${NORMAL}"
  if [ "$MODE" == "force" ]; then
    mackup restore --root --force
  else
    mackup restore --root
  fi

  echo "${BLUE}Installing cargo packages${NORMAL}"

  echo "${BLUE}Installing npm packages${NORMAL}"

  echo "${BLUE}Installing pipx packages${NORMAL}"

  echo "${BLUE}Installing other packages${NORMAL}"
  brew install rm-improved
  brew install broot
  brew install direnv
  brew install thefuck

  echo "${BLUE}Installing tmux configuration (oh-my-tmux)${NORMAL}"
  git clone https://github.com/gpakosz/.tmux.git "$HOME"/.tmux
  ln -sf "$HOME"/.tmux/.tmux.conf "$HOME"/.tmux.conf

  echo "${BLUE}Initialising the key${NORMAL}"
  ssh-keygen -t ed25519 -f "$HOME"/.ssh/id_ed25519 -N ""

  echo "${BLUE}Finishing${NORMAL}"
  source "$HOME"/.bash_profile
  source "$HOME"/.bashrc
  exec bash
}

echo "${BLUE}Installing dotfiles for Debian / Debian Like${NORMAL}"
# RED="$(tput setaf 1)"
# GREEN="$(tput setaf 2)"
# YELLOW="$(tput setaf 3)"
BLUE="$(tput setaf 4)"
NORMAL="$(tput sgr0)"

main

# echo 'debconf debconf/frontend select Noninteractive' | sudo debconf-set-selections
# sudo apt-get install -y -q make
# sudo apt-get install -y -q libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev

# echo "${BLUE}Installing mackup${NORMAL}"
# python3 -m pipx install mackup
# ln -sf "$HOME"/dotfiles/config/mackup/.mackup.cfg "$HOME"/.mackup.cfg
# ln -sf "$HOME"/dotfiles/config/mackup/.mackup "$HOME"/.mackup
# mackup restore

# git clone --depth 1 https://github.com/junegunn/fzf.git ~/.fzf
# ~/.fzf/install --all

# curl -LO https://github.com/BurntSushi/ripgrep/releases/download/13.0.0/ripgrep_13.0.0_amd64.deb
# sudo dpkg -i ripgrep_13.0.0_amd64.deb

# echo "${BLUE}Installing rust${NORMAL}"
# curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
# source "$HOME"/.cargo/env

# echo "${BLUE}Installing pipx${NORMAL}"
# python3 -m pip3 install --user pipx
# python3 -m pipx ensurepath
