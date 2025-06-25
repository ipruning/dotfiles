# 👇 zsh Theme
eval "$(starship init zsh)"

# 👇 zsh options
setopt interactivecomments
zstyle ":completion:*" matcher-list "m:{a-z}={A-Za-z}"

# 👇 Tips
# edit-command-line: edit the command line in the editor
# fc: edit the command line in the editor
autoload -U edit-command-line
zle -N edit-command-line
bindkey "^v" edit-command-line

# 👇 Emacs Mode
bindkey -e

# 👇 My keybindings
bindkey "^[f" forward-word
bindkey "^[b" backward-word
bindkey "^A" beginning-of-line
bindkey "^B" backward-char
bindkey "^D" delete-word
bindkey "^E" end-of-line
bindkey "^F" forward-char

# 👇 Custom paths
export PATH="$HOME/dev/prototypes/utils/bin:$PATH"
export PATH="$HOME/dev/prototypes/utils/scripts:$PATH"

source "$HOME/dotfiles/config/shell/functions/macos.zsh"
source "$HOME/dotfiles/config/shell/functions/mkbir.zsh"
source "$HOME/dotfiles/config/shell/functions/surge.zsh"
source "$HOME/dotfiles/config/shell/functions/utils.zsh"

# 👇 Brew
export HOMEBREW_NO_ANALYTICS=1

# 👇 Mojo
export PATH="$HOME/.modular/bin:$PATH"

# 👇 tailspin
export TAILSPIN_PAGER="ov -f [FILE]"

# 👇 OrbStack
source "$HOME/.orbstack/shell/init.zsh" 2>/dev/null || :

# 👇 zoxide
eval "$(zoxide init zsh --cmd j)"

# 👇 yazi
function y() {
  local tmp="$(mktemp -t "yazi-cwd.XXXXXX")" cwd
  yazi "$@" --cwd-file="$tmp"
  if cwd="$(command cat -- "$tmp")" && [ -n "$cwd" ] && [ "$cwd" != "$PWD" ]; then
    builtin cd -- "$cwd"
  fi
  rm -f -- "$tmp"
}

# 👇 atuin
# eval "$(atuin init zsh --disable-up-arrow)"
# eval "$(atuin init zsh)"
source "$HOME/dotfiles/config/shell/functions/atuin.zsh"

# 👇 tv
_tv_search() {
  emulate -L zsh
  zle -I

  local current_prompt
  current_prompt=$LBUFFER

  local output

  output=$(tv --autocomplete-prompt "$current_prompt" $*)

  zle reset-prompt

  if [[ -n $output ]]; then
    RBUFFER=""
    LBUFFER=$current_prompt$output
  fi
}

zle -N tv-search _tv_search

bindkey '^T' tv-search

# 👇 plugins
ZSH_PLUGINS_DIR="$HOME/dotfiles/config/shell/plugins"

# 👇 ugit
if [[ -f "$ZSH_PLUGINS_DIR"/ugit/ugit.plugin.zsh ]]; then
  source "$ZSH_PLUGINS_DIR"/ugit/ugit.plugin.zsh
fi

# 👇 fzf
__TREE_IGNORE="-I '.git' -I '*.py[co]' -I '__pycache__' $__TREE_IGNORE"
__FD_COMMAND="-L -H --no-ignore-vcs ${__TREE_IGNORE//-I/-E} $__FD_COMMAND"

export FZF_DEFAULT_COMMAND="fd $__FD_COMMAND"

export FZF_DEFAULT_OPTS=" \
--multi \
--style minimal \
--bind 'ctrl-y:accept' \
--color=bg+:#313244,bg:#1e1e2e,spinner:#f5e0dc,hl:#f38ba8 \
--color=fg:#cdd6f4,header:#f38ba8,info:#cba6f7,pointer:#f5e0dc \
--color=marker:#b4befe,fg+:#cdd6f4,prompt:#cba6f7,hl+:#f38ba8 \
--color=selected-bg:#45475a"

if [[ -f "$ZSH_PLUGINS_DIR"/fzf-tab/fzf-tab.plugin.zsh ]]; then
  source "$ZSH_PLUGINS_DIR"/fzf-tab/fzf-tab.plugin.zsh
  zstyle ':completion:*:descriptions' format '[%d]'
  zstyle ':completion:*' menu no
  zstyle ':fzf-tab:*' use-fzf-default-opts yes
fi

unset __TREE_IGNORE
unset __FD_COMMAND

# 👇 zsh-autosuggestions
if [[ -f "$ZSH_PLUGINS_DIR"/zsh-autosuggestions/zsh-autosuggestions.zsh ]]; then
  source "$ZSH_PLUGINS_DIR"/zsh-autosuggestions/zsh-autosuggestions.zsh
fi

# 👇 fast-syntax-highlighting
if [[ -f "$ZSH_PLUGINS_DIR"/fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh ]]; then
  source "$ZSH_PLUGINS_DIR"/fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh
fi

# 👇 select-word-style
autoload -Uz select-word-style
select-word-style bash

# 👇 mise hook-env
eval "$(mise activate zsh)"
# eval "$(mise hook-env -s zsh)"

# 👇 mise shims
# eval "$(mise activate zsh --shims)"
# eval "$(mise activate zsh)"
