#!/usr/bin/env bash

echo "${BLUE}Installing oh-my-zsh${NORMAL}"
export CHSH=no
export RUNZSH=no
export KEEP_ZSHRC=yes
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" --unattended --keep-zshrc

echo "${BLUE}Installing zsh dotiles${NORMAL}"
grep --fixed-strings "dotfiles/config/shell/init.sh" "$HOME"/.zshrc || mv "$HOME"/.zshrc "$HOME"/.zshrc.bak && cp "$HOME"/dotfiles/config/shell/mac/zshrc.sh "$HOME"/.zshrc
mv "$HOME"/.zprofile "$HOME"/.zprofile.bak && cp "$HOME"/dotfiles/config/shell/mac/zprofile.sh "$HOME"/.zprofile

echo "${BLUE}Installing Homebrew${NORMAL}"
which brew || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

echo "${BLUE}Installing Homebrew packages${NORMAL}"
case $SYSTEM_ARCH in
arm64*)
  eval "$(/opt/homebrew/bin/brew shellenv)"
  ;;
x86_64*)
  eval "$(/usr/local/homebrew/bin/brew shellenv)"
  ;;
*)
  echo "unknown: $SYSTEM_ARCH"
  ;;
esac
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

echo "${BLUE}Installing asdf${NORMAL}"
asdf plugin-add python
asdf install python 3.10.2
