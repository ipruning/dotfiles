#!/usr/bin/env bash

RED="$(tput setaf 1)"
GREEN="$(tput setaf 2)"
YELLOW="$(tput setaf 3)"
BLUE="$(tput setaf 4)"
NORMAL="$(tput sgr0)"

echo "${BLUE}Installing dotfiles for arm64${NORMAL}"

echo "${BLUE}Installing mackup${NORMAL}"
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install mackup
ln -sf "$HOME"/dotfiles/config/mackup/.mackup.cfg "$HOME"/.mackup.cfg
ln -sf "$HOME"/dotfiles/config/mackup/.mackup "$HOME"/.mackup
mackup restore

echo "${BLUE}Installing rust${NORMAL}"
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME"/.cargo/env

echo "${BLUE}Installing oh-my-zsh${NORMAL}"
export CHSH=no
export RUNZSH=no
export KEEP_ZSHRC=yes
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" --unattended --keep-zshrc

echo "${BLUE}Installing zsh${NORMAL}"
grep --fixed-strings "dotfiles/config/shell/init.sh" ~/.zshrc || mv "$HOME"/.zshrc "$HOME"/.zshrc.bak
touch "$HOME"/.zshrc && echo "source $HOME/dotfiles/config/shell/init.sh" >>"$HOME"/.zshrc

echo "${BLUE}Installing zsh plugins${NORMAL}"
ZSH_CUSTOM=${ZSH_CUSTOM:-~/.oh-my-zsh/custom}
git clone https://github.com/Aloxaf/fzf-tab "$ZSH_CUSTOM"/plugins/fzf-tab
git clone https://github.com/paulirish/git-open.git "$ZSH_CUSTOM"/plugins/git-open
git clone https://github.com/zsh-users/zsh-autosuggestions "$ZSH_CUSTOM"/plugins/zsh-autosuggestions
git clone https://github.com/zsh-users/zsh-completions "$ZSH_CUSTOM"/plugins/zsh-completions
git clone https://github.com/sukkaw/zsh-osx-autoproxy "$ZSH_CUSTOM"/plugins/zsh-osx-autoproxy
git clone https://github.com/zsh-users/zsh-syntax-highlighting.git "$ZSH_CUSTOM"/plugins/zsh-syntax-highlighting

echo "${BLUE}Installing packages${NORMAL}"
pipx install commitizen
sudo apt-get install -y software-properties-common && sudo add-apt-repository ppa:aos1/diff-so-fancy && sudo apt-get update && sudo apt-get install -y diff-so-fancy
sudo apt-get install -y fzf
sudo apt-get install -y git-extras
sudo apt-get install -y git-lfs && git lfs install
cargo install gitui
sudo apt-get install -y htop
sudo apt-get install -y jq
go install github.com/jesseduffield/lazydocker@latest
cargo install lsd
sudo apt-get install -y neovim
sudo apt-get install -y ripgrep
cargo install rm-improved
sh -c "$(curl -fsSL https://starship.rs/install.sh)"
cargo install tealdeer
pipx install thefuck
sudo apt-get install -y tmux
pipx install tmuxp
cargo install zoxide

echo "${BLUE}Installing npm packages${NORMAL}"
xargs npm install --global <"$HOME"/dotfiles/assets/npm/npm_dev.txt

echo "${BLUE}Installing pipx packages${NORMAL}"
xargs <"$HOME"/dotfiles/assets/pipx/pipx_dev.txt -n 1 pipx install

echo "${BLUE}Installing other packages${NORMAL}"
which autocorrect || curl -sSL https://git.io/JcGER | bash # AutoCorrect

echo "${BLUE}Installing oh-my-tmux${NORMAL}"
git clone https://github.com/gpakosz/.tmux.git "$HOME"/.tmux
ln -sf "$HOME"/.tmux/.tmux.conf "$HOME"/.tmux.conf

echo "${BLUE}Installing SpaceVim${NORMAL}"
curl -sLf https://spacevim.org/install.sh | bash
