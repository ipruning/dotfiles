#!/usr/bin/env bash

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
  if [ -e "$HOME"/.zshrc ]; then
    # #TODO # grep --fixed-strings "dotfiles/config/shell/init.sh" "$HOME"/.zshrc || mv "$HOME"/.zshrc "$HOME"/.zshrc.bak && cp "$HOME"/dotfiles/config/shell/mac/zshrc.sh "$HOME"/.zshrc
    mv "$HOME"/.zshrc "$HOME"/.zshrc.bak && cp "$HOME"/dotfiles/config/shell/mac/zshrc.sh "$HOME"/.zshrc
    # #TODO # touch "$HOME"/.zshrc
  else
    cp "$HOME"/dotfiles/config/shell/mac/zshrc.sh "$HOME"/.zshrc
  fi
  if [ -e "$HOME"/.zprofile ]; then
    mv "$HOME"/.zprofile "$HOME"/.zprofile.bak && cp "$HOME"/dotfiles/config/shell/mac/zprofile.sh "$HOME"/.zprofile
    # #TODO # touch "$HOME"/.zprofile
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
  brew bundle --file="$HOME"/dotfiles/assets/others/packages/Brewfile_dev

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
  asdf reshim

  echo "${BLUE}Installing cargo packages${NORMAL}"
  xargs <"$HOME"/dotfiles/assets/others/packages/cargo_dev.txt -n 1 cargo install

  echo "${BLUE}Installing npm packages${NORMAL}"
  xargs npm install --location=global <"$HOME"/dotfiles/assets/others/packages/npm_dev.txt

  echo "${BLUE}Installing pipx packages${NORMAL}"
  xargs <"$HOME"/dotfiles/assets/others/packages/pipx_dev.txt -n 1 pipx install

  echo "${BLUE}Installing other packages${NORMAL}"

  echo "${BLUE}Installing tmux configuration (oh-my-tmux)${NORMAL}"
  git clone https://github.com/gpakosz/.tmux.git "$HOME"/.tmux
  ln -sf "$HOME"/.tmux/.tmux.conf "$HOME"/.tmux.conf

  echo "${BLUE}Installing emacs configuration (Doom Emacs)${NORMAL}"
  git clone --depth 1 https://github.com/doomemacs/doomemacs ~/.emacs.d
  ~/.emacs.d/bin/doom install
}

main

case $SYSTEM_ARCH in
arm64*)
  echo ""
  ;;
x86_64*)
  echo ""
  echo "${YELLOW}Please check the path to miniforge in init.sh${NORMAL}"
  ;;
*)
  echo ""
  echo "${RED}unknown: $(uname -m)${NORMAL}"
  ;;
esac

echo "${GREEN}Done${NORMAL}"
echo "${GREEN}You can install the VS Code plugin by running the following command.${NORMAL}"
echo "${GREEN}xargs <""$HOME""/dotfiles/assets/others/packages/vscode_extensions.txt -n 1 code --install-extension${NORMAL}"
