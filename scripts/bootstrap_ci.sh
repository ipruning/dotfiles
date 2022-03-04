#!/usr/bin/env bash

echo "${BLUE}Installing oh-my-zsh${NORMAL}"
export CHSH=no
export RUNZSH=no
export KEEP_ZSHRC=yes

echo "${BLUE}Installing Homebrew${NORMAL}"
which brew || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
eval "$(/usr/local/homebrew/bin/brew shellenv)"

echo "Installing Zsh"
brew install zsh
ZSH_PATH="$(brew --prefix)/bin/zsh"
sudo sh -c "echo $ZSH_PATH >> /etc/shells"
sudo chsh -s "$ZSH_PATH"

echo "${BLUE}Installing zsh dotiles${NORMAL}"
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" --unattended --keep-zshrc
grep --fixed-strings "dotfiles/config/shell/init.sh" "$HOME"/.zshrc || mv "$HOME"/.zshrc "$HOME"/.zshrc.bak && cp "$HOME"/dotfiles/config/shell/mac/zshrc.sh "$HOME"/.zshrc
mv "$HOME"/.zprofile "$HOME"/.zprofile.bak && cp "$HOME"/dotfiles/config/shell/mac/zprofile.sh "$HOME"/.zprofile

echo "${BLUE}Installing mackup${NORMAL}"
brew install mackup
ln -sf "$HOME"/dotfiles/config/mackup/.mackup.cfg "$HOME"/.mackup.cfg
ln -sf "$HOME"/dotfiles/config/mackup/.mackup "$HOME"/.mackup
mackup --force restore

echo "${BLUE}Installing asdf${NORMAL}"
brew install asdf
asdf plugin-add python
asdf install python 3.10.2
asdf global python 3.10.2
