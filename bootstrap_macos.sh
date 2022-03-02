#!/bin/bash

# main_arm64
function main_arm64 {
  echo "Installing dotfiles for arm64"
  # install oh-my-zsh
  sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"

  # install Homebrew
  which brew || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

  # install Homebrew packages
  brew bundle --file="$HOME"/dotfiles/config/brew/Brewfile

  # install npm packages
  asdf install nodejs lts
  asdf global nodejs lts
  xargs npm install --global < "$HOME"/dotfiles/assets/npm/npm.txt

  # install pipx packages
  xargs pipx install < "$HOME"/dotfiles/assets/pipx/npm.txt

  # install other packages
  curl -sSL https://git.io/JcGER | bash # AutoCorrect

  # install zsh
  grep --fixed-strings "dotfiles/config/shell/init.sh" ~/.zshrc || echo "source $HOME/dotfiles/config/shell/init.sh" >> "$HOME"/.zshrc
  
  # install zsh plugins

  # install mackup
  ln -sf "$HOME"/dotfiles/config/mackup/.mackup.cfg "$HOME"/.mackup.cfg
  ln -sf "$HOME"/dotfiles/config/mackup/.mackup "$HOME"/.mackup
  mackup restore

  # install oh-my-tmux
  git clone https://github.com/gpakosz/.tmux.git "$HOME"/.tmux
  ln -sf "$HOME"/.tmux/.tmux.conf "$HOME"/.tmux.conf
}

# init
arch_check=$(/usr/bin/arch)
case $arch_check in
  arm64*)
    main_arm64
    echo "Done"
  ;;
  i386*)
    echo "Please check the path to miniforge in init.sh"
  ;;
  *)
    echo "unknown: $arch_check"
  ;;
esac
