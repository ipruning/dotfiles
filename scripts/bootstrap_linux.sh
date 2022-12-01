#!/usr/bin/env bash

echo "${BLUE}Installing dotfiles for Debian / Debian Like${NORMAL}"
# RED="$(tput setaf 1)"
# GREEN="$(tput setaf 2)"
# YELLOW="$(tput setaf 3)"
BLUE="$(tput setaf 4)"
NORMAL="$(tput sgr0)"

echo "${BLUE}Installing essential${NORMAL}"
sudo apt-get install -y build-essential

echo "${BLUE}Installing packages${NORMAL}"
sudo apt-get install -y htop
sudo apt-get install -y neovim
sudo apt-get install -y zsh

git clone --depth 1 https://github.com/junegunn/fzf.git ~/.fzf
~/.fzf/install --all

curl -LO https://github.com/BurntSushi/ripgrep/releases/download/13.0.0/ripgrep_13.0.0_amd64.deb
sudo dpkg -i ripgrep_13.0.0_amd64.deb

echo "${BLUE}Installing rust${NORMAL}"
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME"/.cargo/env

echo "${BLUE}Installing pipx${NORMAL}"
python3 -m pip install --user pipx
python3 -m pipx ensurepath

echo "${BLUE}Installing mackup${NORMAL}"
python3 -m pipx install mackup
ln -sf "$HOME"/dotfiles/config/mackup/.mackup.cfg "$HOME"/.mackup.cfg
ln -sf "$HOME"/dotfiles/config/mackup/.mackup "$HOME"/.mackup
mackup restore

echo "${BLUE}Installing oh-my-zsh${NORMAL}"
export CHSH=no
export RUNZSH=no
export KEEP_ZSHRC=yes
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" --unattended --keep-zshrc

echo "${BLUE}Installing oh-my-tmux${NORMAL}"
git clone https://github.com/gpakosz/.tmux.git
ln -sf "$HOME"/.tmux/.tmux.conf "$HOME"/.tmux.conf

echo "${BLUE}Installing other packages${NORMAL}"
cargo install rm-improved

echo "${BLUE}Initialising the key${NORMAL}"
ssh-keygen -t ed25519 -f "$HOME"/.ssh/id_ed25519 -N ""

echo "${BLUE}Finishing${NORMAL}"
source "$HOME"/.bash_profile
source "$HOME"/.bashrc
exec bash
