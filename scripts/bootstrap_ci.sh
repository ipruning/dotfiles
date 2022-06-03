#!/usr/bin/env bash

#===============================================================================
# 👇 csys
#===============================================================================
SYSTEM_ARCH=$(uname -m)

case "$OSTYPE" in
darwin*)
  case $SYSTEM_ARCH in
  arm64*)
    SYSTEM_TYPE="mac_arm64"
    ;;
  x86_64*)
    SYSTEM_TYPE="mac_x86_64"
    ;;
  *)
    SYSTEM_TYPE="unknown"
    ;;
  esac
  ;;
linux*)
  case $SYSTEM_ARCH in
  x86_64*)
    SYSTEM_TYPE="linux_x86_64"
    ;;
  *armv7l*)
    SYSTEM_TYPE="raspberry"
    ;;
  *)
    SYSTEM_TYPE="unknown"
    ;;
  esac
  ;;
msys*)
  SYSTEM_TYPE="unknown"
  ;;
*)
  SYSTEM_TYPE="unknown"
  ;;
esac

case $SYSTEM_TYPE in
mac_x86_64)
  which brew || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  eval "$(/usr/local/homebrew/bin/brew shellenv)"
  ;;
linux_x86_64)
  which brew || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  test -d ~/.linuxbrew && eval "$(~/.linuxbrew/bin/brew shellenv)"
  test -d /home/linuxbrew/.linuxbrew && eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
  test -r ~/.bash_profile && echo "eval \"\$($(brew --prefix)/bin/brew shellenv)\"" >>~/.bash_profile
  echo "eval \"\$($(brew --prefix)/bin/brew shellenv)\"" >>~/.profile
  ;;
unknown)
  echo "${RED}Unsupported system architecture.${NORMAL}"
  ;;
esac

echo "Installing zsh"
brew install zsh
ZSH_PATH="$(brew --prefix)/bin/zsh"
sudo sh -c "echo $ZSH_PATH >> /etc/shells"
sudo chsh -s "$ZSH_PATH"

echo "${BLUE}Installing oh-my-zsh${NORMAL}"
export CHSH=no
export RUNZSH=no
export KEEP_ZSHRC=yes
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" --unattended --keep-zshrc

echo "${BLUE}Installing zsh dotiles${NORMAL}"
grep --fixed-strings "dotfiles/config/shell/init.sh" "$HOME"/.zshrc || mv "$HOME"/.zshrc "$HOME"/.zshrc.bak && cp "$HOME"/dotfiles/config/shell/mac/zshrc.sh "$HOME"/.zshrc
if [ -e "$HOME"/.zprofile ]; then
  mv "$HOME"/.zprofile "$HOME"/.zprofile.bak && cp "$HOME"/dotfiles/config/shell/mac/zprofile.sh "$HOME"/.zprofile
else
  cp "$HOME"/dotfiles/config/shell/mac/zprofile.sh "$HOME"/.zprofile
fi

brew install mackup

echo "${BLUE}Installing mackup${NORMAL}"
ln -sf "$HOME"/dotfiles/config/mackup/.mackup.cfg "$HOME"/.mackup.cfg
ln -sf "$HOME"/dotfiles/config/mackup/.mackup "$HOME"/.mackup

echo "${BLUE}Restoring dotfiles${NORMAL}"
if [ "$MODE" == "--force" ]; then
  mackup --force restore
else
  mackup restore
fi

case $SYSTEM_TYPE in
mac_x86_64)
  brew install python@3.9
  ;;
linux_x86_64)
  brew install asdf

  echo "${BLUE}Installing asdf${NORMAL}"
  asdf plugin-add python
  asdf install python 3.9.13
  asdf global python 3.9.13

  echo "${BLUE}Reshiming asdf${NORMAL}"
  asdf reshim

  ;;
unknown)
  echo "${RED}Unsupported system architecture.${NORMAL}"
  ;;
esac
