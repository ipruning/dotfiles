#!/usr/bin/env bash

function main {
  echo "${BLUE}Installing essential${NORMAL}"
  sudo apt-get install -y build-essential

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
  echo '# Set PATH, MANPATH, etc., for Homebrew.' >>/root/.profile
  echo 'eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"' >>/root/.profile
  eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
  brew install asdf
  brew install gcc
  brew install pipx

  echo "${BLUE}Installing mackup${NORMAL}"
  ln -sf "$HOME"/dotfiles/config/mackup/.mackup.cfg "$HOME"/.mackup.cfg
  ln -sf "$HOME"/dotfiles/config/mackup/.mackup "$HOME"/.mackup

  echo "${BLUE}Restoring dotfiles${NORMAL}"
  if [ "$MODE" == "force" ]; then
    mackup --force restore
  else
    mackup restore
  fi

  echo "${BLUE}Installing asdf${NORMAL}"
  asdf plugin-add clojure https://github.com/asdf-community/asdf-clojure.git
  asdf plugin-add crystal https://github.com/asdf-community/asdf-crystal.git
  asdf plugin-add elixir https://github.com/asdf-vm/asdf-elixir.git
  asdf plugin-add golang https://github.com/kennyp/asdf-golang.git
  asdf plugin-add java https://github.com/halcyon/asdf-java.git
  asdf plugin-add lua https://github.com/Stratus3D/asdf-lua.git
  asdf plugin-add nodejs https://github.com/asdf-vm/asdf-nodejs.git
  asdf plugin-add python
  asdf plugin-add ruby https://github.com/asdf-vm/asdf-ruby.git
  asdf plugin-add rust https://github.com/asdf-community/asdf-rust.git
  asdf install

  echo "${BLUE}Reshiming asdf${NORMAL}"
  # asdf reshim

  echo "${BLUE}Installing cargo packages${NORMAL}"
  # xargs <"$HOME"/dotfiles/assets/others/packages/cargo_dev.txt -n 1 cargo install

  echo "${BLUE}Installing npm packages${NORMAL}"
  # xargs npm install --location=global <"$HOME"/dotfiles/assets/others/packages/npm_dev.txt

  echo "${BLUE}Installing pipx packages${NORMAL}"
  # xargs <"$HOME"/dotfiles/assets/others/packages/pipx_dev.txt -n 1 pipx install

  echo "${BLUE}Installing other packages${NORMAL}"
  cargo install rm-improved

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

# echo "${BLUE}Installing mackup${NORMAL}"
# python3 -m pipx install mackup
# ln -sf "$HOME"/dotfiles/config/mackup/.mackup.cfg "$HOME"/.mackup.cfg
# ln -sf "$HOME"/dotfiles/config/mackup/.mackup "$HOME"/.mackup
# mackup restore

# echo "${BLUE}Installing packages${NORMAL}"
# sudo apt-get install -y htop
# sudo apt-get install -y neovim

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
