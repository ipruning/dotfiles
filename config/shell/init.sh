#!/bin/bash

#===============================================================================
# 👇 zprof
#===============================================================================
# zmodload zsh/zprof # 在 ~/.zshrc 的头部加上这个，加载 profile 模块

#===============================================================================
# 👇 _INIT_SH_LOADED
#===============================================================================
if [ -z "$_INIT_SH_LOADED" ]; then
    _INIT_SH_LOADED=1
else
    return
fi

#===============================================================================
# 👇 Powerlevel10k
# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
#===============================================================================
# if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
#   source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
# fi

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
  # ZSH_THEME="powerlevel10k/powerlevel10k"
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
  zsh-osx-autoproxy
  zsh-syntax-highlighting
  macos
  yarn
  poetry
  ripgrep 
  magic-enter
  zbell
  command-not-found
  systemadmin
)

#===============================================================================
# 👇 ZSH Source
#===============================================================================
source $ZSH/oh-my-zsh.sh

#===============================================================================
# 👇 Powerlevel10k
# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
#===============================================================================
# [[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

#===============================================================================
# 👇 GFW Proxy
#===============================================================================
# export https_proxy=http://127.0.0.1:7890 http_proxy=http://127.0.0.1:7890 all_proxy=socks5://127.0.0.1:7890

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
  export EDITOR='code'
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
# 👇 fzf
#===============================================================================
source "$(brew --prefix fzf)/shell/completion.zsh"
source "$(brew --prefix fzf)/shell/key-bindings.zsh"
#===============================================================================
# 👇 fzf CTRL-T to fuzzily search for a file or directory in your home directory then insert its path at the cursor
#===============================================================================
export FZF_DEFAULT_OPTS="--height=80% --layout=reverse --info=inline --border --margin=1 --padding=1"
export FZF_DEFAULT_COMMAND="fd --ignore-file ~/.rgignore --hidden --follow --ignore-case . /etc $HOME"
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"

#===============================================================================
# 👇 conda
#===============================================================================
# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="$('/opt/homebrew/Caskroom/miniforge/base/bin/conda' 'shell.zsh' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
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

#===============================================================================
# 👇 Autodetect architecture (and set `brew` path) (and set `python` path)
#===============================================================================
if [[ "$(sysctl -a | grep machdep.cpu.brand_string)" == *Apple* ]]; then
  arch_check=$(/usr/bin/arch)
  # arch_name=$(uname -m)
  typeset -g arch_check
  case $arch_check in
    arm64)
      # arch_name=' '
      # arch_name+=$(uname -m)
      # Python
      alias 'cvenv'='python3 -m venv .venv && source .venv/bin/activate && pip install --upgrade pip setuptools wheel'
      alias 'svenv'='source .venv/bin/activate'
      alias 'cenv'='conda create --prefix ./.env && conda activate ./.env'
      alias 'senv'='conda activate ./.env'
      # Java
      export JAVA_HOME=/Library/Java/JavaVirtualMachines/zulu-17.jdk/Contents/Home
    ;;
    i386|x86_64)
      # arch_name=' '
      # arch_name+=$(uname -m)
      if [[ -f /usr/local/homebrew/bin/brew ]]; then
        eval "$(/usr/local/homebrew/bin/brew shellenv)" # homebrew intel shell env
      fi
      # Python
      eval "$(pyenv init --path)" # pyenv intel shell env
      eval "$(pyenv init -)" # pyenv intel shell env
      alias 'cvenv'='python3 -m venv .venv && source .venv/bin/activate && pip install --upgrade pip setuptools wheel'
      alias 'svenv'='source .venv/bin/activate'
    ;;
    *)
      arch_check+=' (Unknown)'
    ;;
  esac
  # add arch to p10k
  # function prompt_my_arch() {
  #   p10k segment -f 250 -i '' -t "${arch_name//\%/%%}"
  # }
  # POWERLEVEL9K_RIGHT_PROMPT_ELEMENTS+=my_arch  # to specify location, modify ~/.p10k.zsh
fi

#===============================================================================
# 👇 functions
#===============================================================================
if [ -n "$BASH_VERSION" ] || [ -n "$ZSH_VERSION" ]; then
    # run script for interactive mode of bash/zsh
    if [[ $- == *i* ]] && [ -z "$_INIT_SH_NOFUN" ]; then
        if [ -f "$HOME/dotfiles/config/shell/functions.zsh" ]; then
            . "$HOME/dotfiles/config/shell/functions.zsh"
        fi
    fi
fi

#===============================================================================
# 👇 aliases
#===============================================================================
if [ -n "$BASH_VERSION" ] || [ -n "$ZSH_VERSION" ]; then
    # run script for interactive mode of bash/zsh
    if [[ $- == *i* ]] && [ -z "$_INIT_SH_NOFUN" ]; then
        if [ -f "$HOME/dotfiles/config/shell/aliases.zsh" ]; then
            . "$HOME/dotfiles/config/shell/aliases.zsh"
        fi
    fi
fi

#===============================================================================
# 👇 completion
#===============================================================================
if [ -n "$BASH_VERSION" ] || [ -n "$ZSH_VERSION" ]; then
    # run script for interactive mode of bash/zsh
    if [[ $- == *i* ]] && [ -z "$_INIT_SH_NOFUN" ]; then
        if [ -f "$HOME/dotfiles/config/shell/completion.zsh" ]; then
            . "$HOME/dotfiles/config/shell/completion.zsh"
        fi
    fi
fi

#===============================================================================
# 👇 zprof
#===============================================================================
# zprof
