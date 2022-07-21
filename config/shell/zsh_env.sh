#===============================================================================
# 👇 Fig pre block. Keep at the top of this file.
#===============================================================================
# eval "$(fig init zsh pre)"

#===============================================================================
# 👇 direnv
#===============================================================================
eval "$(direnv hook bash)"

#===============================================================================
# 👇 GPG Signing
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
# 👇 Standard plugins can be found in $ZSH/plugins/
# 👇 Custom plugins may be added to $ZSH_CUSTOM/plugins/
#===============================================================================
export plugins=(
  asdf
  colored-man-pages
  extract # x <file>
  fd
  gh
  macos # showfiles hidefiles
  magic-enter
  systemadmin
  ripgrep
  zbell
  autoupdate              # https://github.com/TamCore/autoupdate-oh-my-zsh-plugins
  cheat                   # https://github.com/cheat/cheat/issues/616
  forgit                  # https://github.com/wfxr/forgit
  fzf-tab                 # https://github.com/Aloxaf/fzf-tab
  git-open                # https://github.com/paulirish/git-open
  zsh-autosuggestions     # https://github.com/zsh-users/zsh-autosuggestions
  zsh-completions         # https://github.com/zsh-users/zsh-completions
  zsh-syntax-highlighting # https://github.com/zsh-users/zsh-syntax-highlighting
  zsh-vi-mode             # https://github.com/jeffreytse/zsh-vi-mode
  # Archive
  # zsh-osx-autoproxy       # export https_proxy=http://127.0.0.1:7890 http_proxy=http://127.0.0.1:7890 all_proxy=socks5://127.0.0.1:7890
)

#===============================================================================
# 👇 zsh-completions
#===============================================================================
# fpath+=${ZSH_CUSTOM:-${ZSH:-~/.oh-my-zsh}/custom}/plugins/zsh-completions/src

#===============================================================================
# 👇 Language environment
#===============================================================================
export LANG=en_US.UTF-8

#===============================================================================
# 👇 History
#===============================================================================
export HIST_STAMPS="yyyy-mm-dd"
export HISTFILE="$HOME/.zsh_history"
export HISTSIZE=1000000
export SAVEHIST=$HISTSIZE
setopt EXTENDED_HISTORY
setopt INC_APPEND_HISTORY # Write to the history file immediately, not when the shell exits.

#===============================================================================
# 👇 oh-my-zsh autoupdate-zsh-plugin
#===============================================================================
export UPDATE_ZSH_DAYS=42

#===============================================================================
# 👇 oh-my-zsh init
#===============================================================================
source "$ZSH"/oh-my-zsh.sh

#===============================================================================
# 👇 custom binary
#===============================================================================
export PATH="${HOME}/dotfiles/bin:$PATH"

#===============================================================================
# 👇 zsh-vi-mode https://github.com/jeffreytse/zsh-vi-mode/issues/24
# 👇 custom keybindings
#===============================================================================
case $SYSTEM_TYPE in
mac*)
  zvm_after_init() {
    # 👇 fzf
    # [ -f ~/.fzf.zsh ] && source ~/.fzf.zsh
    case $SYSTEM_TYPE in
    mac_arm64)
      source "/opt/homebrew/opt/fzf/shell/completion.zsh"
      source "/opt/homebrew/opt/fzf/shell/key-bindings.zsh"
      ;;
    mac_x86_64)
      source "$(brew --prefix fzf)/shell/completion.zsh"
      source "$(brew --prefix fzf)/shell/key-bindings.zsh"
      ;;
    esac
    # 👇 Option-S
    bindkey '^S' sudo-command-line
    # 👇 Option-C
    bindkey 'ç' fzf-cd-widget
    # 👇 Option-X
    bindkey '≈' fzf-dirs-widget
    # 👇 Ctrl-L accept zsh-autosuggestions https://github.com/zsh-users/zsh-autosuggestions#key-bindings
    bindkey '^L' autosuggest-accept
  }
  ;;
linux*)
  zvm_after_init() {
    bindkey '\ex' fzf-dirs-widget
  }
  ;;
esac

#===============================================================================
# 👇 forgit
#===============================================================================
forgit_log=glo
forgit_diff=gd
forgit_add=ga
forgit_reset_head=grh
forgit_ignore=gi
forgit_checkout_file=gcf
forgit_checkout_branch=gcb
forgit_branch_delet=gbd
forgit_checkout_tag=gct
forgit_checkout_commit=gco
forgit_revert_commit=grc
forgit_clean=gclean
forgit_stash_show=gss
forgit_cherry_pick=gcp
forgit_rebase=grb
forgit_fixup=gfu
export PATH="$PATH:$FORGIT_INSTALL_DIR/bin"

#===============================================================================
# 👇 fzf
#===============================================================================
case $SYSTEM_TYPE in
mac*)
  export FZF_DEFAULT_OPTS="--height=100% --layout=reverse --info=inline --border --margin=1 --padding=1"
  # export FZF_DEFAULT_COMMAND="fd --ignore-file ~/.rgignore --hidden --follow --ignore-case . /etc $HOME"
  export FZF_DEFAULT_COMMAND="fd --ignore-file ~/.rgignore --hidden --follow --ignore-case ."
  ;;
linux*) ;;
esac

#===============================================================================
# 👇 fzf Ctrl-T to fuzzily search for a file or directory in your home directory then insert its path at the cursor
#===============================================================================
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"

#===============================================================================
# 👇 fzf Option-C 快速查找目录 fuzzily search for a directory in your home directory then cd into it
#===============================================================================
export FZF_ALT_C_COMMAND="fd --ignore-file ~/.rgignore --hidden --follow --ignore-case --type d"

#===============================================================================
# 👇 doom-emacs binary
#===============================================================================
export PATH="${HOME}/.emacs.d/bin:$PATH"

#===============================================================================
# 👇 Preferred editor for local and remote sessions
#===============================================================================
if [[ -n $SSH_CONNECTION ]]; then
  export EDITOR='nvim'
else
  export EDITOR='nvim'
  # export EDITOR="emacsclient -t -a=\"\""
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
# 👇 thefuck
#===============================================================================
eval "$(thefuck --alias)"

#===============================================================================
# 👇 Sourcegraph
#===============================================================================
# export SRC_ACCESS_TOKEN=my-token
# export SRC_ENDPOINT=https://sourcegraph.example.com

#===============================================================================
# 👇 broot
#===============================================================================
source "${HOME}/.config/broot/launcher/bash/br"

#===============================================================================
# 👇 puppeteer
#===============================================================================
export PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
export PUPPETEER_EXECUTABLE_PATH=$(brew --prefix)/bin/chromium

#===============================================================================
# 👇 tumxp
#===============================================================================
export DISABLE_AUTO_TITLE='true'

#===============================================================================
# 👇 bat
#===============================================================================
export BAT_THEME="OneHalfDark"

#===============================================================================
# 👇 LLVM
#===============================================================================
export PATH="$(brew --prefix llvm)/bin:${PATH}"
export LDFLAGS="-L$(brew --prefix llvm)/lib"
export CPPFLAGS="-I$(brew --prefix llvm)/include"

#===============================================================================
# 👇 Autodetect architecture (and set `brew` path) (and set `python` path)
#===============================================================================
case $SYSTEM_TYPE in
mac_arm64)
  # Python
  # alias 'cvenv'='python3 -m venv .venv && source .venv/bin/activate && python3 -m pip install --upgrade -r $HOME/.requirements.txt'
  alias 'cvenv'='$(brew --prefix python@3.10)/bin/python3 -m venv .venv && source .venv/bin/activate && python3 -m pip install --upgrade -r $HOME/.requirements.txt'
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
mac_x86_64)
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
esac

#===============================================================================
# 👇 Fig post block. Keep at the bottom of this file.
#===============================================================================
# eval "$(fig init zsh post)"
