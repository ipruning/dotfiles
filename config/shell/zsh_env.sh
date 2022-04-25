#!/usr/bin/env bash

#===============================================================================
# 👇 direnv
#===============================================================================
eval "$(direnv hook bash)"

#===============================================================================
# 👇 Fig pre block. Keep at the top of this file.
#===============================================================================
# eval "$(fig init zsh pre)"

#===============================================================================
# 👇 GPG 签名
#===============================================================================
# if [ -r ~/.zshrc ]; then echo 'export GPG_TTY=$(tty)' >> ~/.zshrc; \
#   else echo 'export GPG_TTY=$(tty)' >> ~/.zprofile; fi

#===============================================================================
# 👇 oh-my-zsh init
#===============================================================================
export ZSH="${HOME}/.oh-my-zsh"

#===============================================================================
# 👇 ZSH Theme
#===============================================================================
if [[ -n $SSH_CONNECTION ]]; then
  eval "$(starship init zsh)"
else
  eval "$(starship init zsh)"
fi

#===============================================================================
# 👇 History Stamps
#===============================================================================
export HIST_STAMPS="yyyy-mm-dd"

#===============================================================================
# 👇 Standard plugins can be found in $ZSH/plugins/
# 👇 Custom plugins may be added to $ZSH_CUSTOM/plugins/
#===============================================================================
export plugins=(
  asdf
  colored-man-pages
  thefuck
  fd
  fzf-tab
  docker
  docker-compose
  gh
  git-open
  catimg
  zsh-autosuggestions
  zsh-completions
  zsh-interactive-cd
  zsh-osx-autoproxy # export https_proxy=http://127.0.0.1:7890 http_proxy=http://127.0.0.1:7890 all_proxy=socks5://127.0.0.1:7890
  zsh-syntax-highlighting
  macos # showfiles hidefiles
  # npm
  # yarn
  poetry
  ripgrep
  # magic-enter # tmuxp bug
  zbell
  command-not-found
  systemadmin
)

#===============================================================================
# 👇 ZSH Source
#===============================================================================
source "$ZSH"/oh-my-zsh.sh

#===============================================================================
# 👇 Custom Binary
#===============================================================================
export PATH="${HOME}/dotfiles/bin:$PATH"

#===============================================================================
# 👇 Language environment
#===============================================================================
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8

#===============================================================================
# 👇 Preferred editor for local and remote sessions
#===============================================================================
if [[ -n $SSH_CONNECTION ]]; then
  export EDITOR='vim'
else
  export EDITOR='vim'
  # export EDITOR='code'
fi

#===============================================================================
# 👇 iTerm2 https://iterm2.com/documentation-shell-integration.html
#===============================================================================
test -e "${HOME}/.iterm2_shell_integration.zsh" && source "${HOME}/.iterm2_shell_integration.zsh"

#===============================================================================
# 👇 qt5
#===============================================================================
# export PATH="$(brew --prefix qt@5)/bin:$PATH"
# export LDFLAGS="-L$(brew --prefix qt@5)/lib"
# export CPPFLAGS="-I$(brew --prefix qt@5)/include"
# export PKG_CONFIG_PATH="$(brew --prefix qt@5)/lib/pkgconfig"

#===============================================================================
# 👇 broot
#===============================================================================
source "${HOME}/.config/broot/launcher/bash/br"

#===============================================================================
# 👇 puppeteer
#===============================================================================
export PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
PUPPETEER_EXECUTABLE_PATH=$(brew --prefix)/bin/chromium
export PUPPETEER_EXECUTABLE_PATH

#===============================================================================
# 👇 tumxp
#===============================================================================
export DISABLE_AUTO_TITLE='true'

#===============================================================================
# 👇 bat
#===============================================================================
export BAT_THEME="OneHalfDark"

#===============================================================================
# 👇 fzf
#===============================================================================
case $SYSTEM_TYPE in
mac_arm64 | mac_x86_64*)
  # source "$(brew --prefix fzf)/shell/completion.zsh"
  # source "$(brew --prefix fzf)/shell/key-bindings.zsh"
  source "/opt/homebrew/opt/fzf/shell/completion.zsh"
  source "/opt/homebrew/opt/fzf/shell/key-bindings.zsh"
  ;;

raspberry) ;;

esac

#===============================================================================
# 👇 fzf CTRL-T to fuzzily search for a file or directory in your home directory then insert its path at the cursor
#===============================================================================
export FZF_DEFAULT_OPTS="--height=100% --layout=reverse --info=inline --border --margin=1 --padding=1"
export FZF_DEFAULT_COMMAND="fd --ignore-file ~/.rgignore --hidden --follow --ignore-case . /etc $HOME"
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"

#===============================================================================
# 👇 Autodetect architecture (and set `brew` path) (and set `python` path)
#===============================================================================
case $SYSTEM_ARCH in
arm64)
  # Python
  alias 'cvenv'='python3 -m venv .venv && source .venv/bin/activate && python3 -m pip install --upgrade -r $HOME/.requirements.txt'
  alias 'svenv'='source .venv/bin/activate'
  alias 'cenv'='conda create --prefix ./.env && conda activate ./.env'
  alias 'senv'='conda activate ./.env'
  # Python Miniforge
  # >>> conda initialize >>>
  # !! Contents within this block are managed by 'conda init' !!
  if ! __conda_setup="$('/opt/homebrew/Caskroom/miniforge/base/bin/conda' 'shell.zsh' 'hook' 2>/dev/null)"; then
    eval "$__conda_setup"
  else
    if [ -f "/opt/homebrew/Caskroom/miniforge/base/etc/profile.d/conda.sh" ]; then
      . "/opt/homebrew/Caskroom/miniforge/base/etc/profile.d/conda.sh"
    else
      export PATH="/opt/homebrew/Caskroom/miniforge/base/bin:$PATH"
    fi
  fi
  unset __conda_setup
  # <<< conda initialize <<<
  # Java
  export JAVA_HOME=/Library/Java/JavaVirtualMachines/zulu-17.jdk/Contents/Home
  ;;
x86_64 | i386)
  # Brew
  if [[ -f /usr/local/homebrew/bin/brew ]]; then
    eval "$(/usr/local/homebrew/bin/brew shellenv)" # homebrew intel shell env
  fi
  # Python
  eval "$(pyenv init --path)" # pyenv intel shell env
  eval "$(pyenv init -)"      # pyenv intel shell env
  alias 'cvenv'='python3 -m venv .venv && source .venv/bin/activate && python3 -m pip install --upgrade -r $HOME/.requirements.txt'
  alias 'svenv'='source .venv/bin/activate'
  ;;
*)
  echo "System architecture: $SYSTEM_ARCH"
  ;;
esac

#===============================================================================
# 👇 Fig post block. Keep at the bottom of this file.
#===============================================================================
# eval "$(fig init zsh post)"
