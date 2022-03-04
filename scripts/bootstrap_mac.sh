#!/usr/bin/env bash

RED="$(tput setaf 1)"
GREEN="$(tput setaf 2)"
YELLOW="$(tput setaf 3)"
BLUE="$(tput setaf 4)"
NORMAL="$(tput sgr0)"

SYSTEM_ARCH=$(uname -m)

function main {
  case $SYSTEM_ARCH in
  arm64*)
    echo "${BLUE}Installing dotfiles for macOS (Apple chips)${NORMAL}"
    ;;
  x86_64*)
    echo "${BLUE}Installing dotfiles for macOS (Intel chips)${NORMAL}"
    ;;
  *)
    echo "unknown $SYSTEM_ARCH"
    ;;
  esac

  echo "${BLUE}Installing oh-my-zsh${NORMAL}"
  export CHSH=no
  export RUNZSH=no
  export KEEP_ZSHRC=yes
  sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" --unattended --keep-zshrc

  echo "${BLUE}Installing zsh dotiles${NORMAL}"
  grep --fixed-strings "dotfiles/config/shell/init.sh" "$HOME"/.zshrc || mv "$HOME"/.zshrc "$HOME"/.zshrc.bak && cp "$HOME"/dotfiles/config/shell/mac/zshrc.sh "$HOME"/.zshrc
  mv "$HOME"/.zprofile "$HOME"/.zprofile.bak && cp "$HOME"/dotfiles/config/shell/mac/zprofile.sh "$HOME"/.zprofile

  echo "${BLUE}Installing zsh plugins${NORMAL}"
  ZSH_CUSTOM=${ZSH_CUSTOM:-~/.oh-my-zsh/custom}
  git clone https://github.com/Aloxaf/fzf-tab "$ZSH_CUSTOM"/plugins/fzf-tab
  git clone https://github.com/paulirish/git-open.git "$ZSH_CUSTOM"/plugins/git-open
  git clone https://github.com/zsh-users/zsh-autosuggestions "$ZSH_CUSTOM"/plugins/zsh-autosuggestions
  git clone https://github.com/zsh-users/zsh-completions "$ZSH_CUSTOM"/plugins/zsh-completions
  git clone https://github.com/sukkaw/zsh-osx-autoproxy "$ZSH_CUSTOM"/plugins/zsh-osx-autoproxy
  git clone https://github.com/zsh-users/zsh-syntax-highlighting.git "$ZSH_CUSTOM"/plugins/zsh-syntax-highlighting

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
  brew bundle --file="$HOME"/dotfiles/assets/brew/brew_dev.txt

  echo "${BLUE}Installing mackup${NORMAL}"
  ln -sf "$HOME"/dotfiles/config/mackup/.mackup.cfg "$HOME"/.mackup.cfg
  ln -sf "$HOME"/dotfiles/config/mackup/.mackup "$HOME"/.mackup

  echo "${BLUE}Restoring dotfiles${NORMAL}"
  mackup restore

  echo "${BLUE}Installing asdf${NORMAL}"
  asdf plugin-add clojure https://github.com/asdf-community/asdf-clojure.git
  asdf plugin-add golang https://github.com/kennyp/asdf-golang.git
  asdf plugin-add nodejs https://github.com/asdf-vm/asdf-nodejs.git
  asdf plugin-add php https://github.com/asdf-community/asdf-php.git
  asdf plugin-add python
  asdf plugin-add ruby https://github.com/asdf-vm/asdf-ruby.git
  asdf plugin-add rust https://github.com/asdf-community/asdf-rust.git
  asdf install

  echo "${BLUE}Installing npm packages${NORMAL}"
  xargs npm install --global <"$HOME"/dotfiles/assets/npm/npm_dev.txt

  echo "${BLUE}Installing pipx packages${NORMAL}"
  xargs <"$HOME"/dotfiles/assets/pipx/pipx_dev.txt -n 1 pipx install

  echo "${BLUE}Installing other packages${NORMAL}"
  where autocorrect || curl -sSL https://git.io/JcGER | bash # AutoCorrect

  echo "${BLUE}Installing VS Code extenstions${NORMAL}"
  xargs <"$HOME"/dotfiles/assets/vscode/vscode.txt -n 1 code --install-extension

  echo "${BLUE}Installing oh-my-tmux${NORMAL}"
  git clone https://github.com/gpakosz/.tmux.git "$HOME"/.tmux
  ln -sf "$HOME"/.tmux/.tmux.conf "$HOME"/.tmux.conf

  echo "${BLUE}Installing SpaceVim${NORMAL}"
  curl -sLf https://spacevim.org/install.sh | bash

  # echo "${BLUE}Installing doom-emacs${NORMAL}"
  # git clone --depth 1 https://github.com/hlissner/doom-emacs "$HOME"/.emacs.d
  # "$HOME"/.emacs.d/bin/doom install
}

# init
case $(uname -m) in
arm64*)
  main
  echo "${GREEN}Done${NORMAL}"
  ;;
x86_64*)
  main
  echo "${GREEN}Done${NORMAL}"
  echo "${YELLOW}Please check the path to miniforge in init.sh${NORMAL}"
  ;;
*)
  echo "${RED}unknown: $(uname -m)${NORMAL}"
  ;;
esac
