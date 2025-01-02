# 👇 completions
fpath=("$HOME/dotfiles/config/shell/completions" $fpath)

autoload -Uz compinit

if [[ -n ~/.zcompdump(#qN.mh+24) ]]; then
  compinit
else
  compinit -C
fi

# 👇 zsh Theme
eval "$(starship init zsh)"

# 👇 zsh options
setopt NO_NOMATCH
setopt NO_NULL_GLOB
setopt interactivecomments

# 👇 fast-syntax-highlighting https://github.com/catppuccin/zsh-fsh
ZSH_PLUGINS_DIR="$HOME/dotfiles/config/shell/plugins"
source "$ZSH_PLUGINS_DIR"/fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh

# 👇 fzf
source <(fzf --zsh)
export FZF_ALT_C_COMMAND=""
export FZF_CTRL_T_COMMAND=""
export FZF_COMPLETION_TRIGGER='jk'
export FZF_DEFAULT_COMMAND="fd --type file --strip-cwd-prefix --ignore-file ~/.gitignore"
export FZF_DEFAULT_OPTS=" \
--color=bg+:#313244,bg:#1e1e2e,spinner:#f5e0dc,hl:#f38ba8 \
--color=fg:#cdd6f4,header:#f38ba8,info:#cba6f7,pointer:#f5e0dc \
--color=marker:#b4befe,fg+:#cdd6f4,prompt:#cba6f7,hl+:#f38ba8 \
--color=selected-bg:#45475a \
--multi"

# 👇 fzf-tab
source "$ZSH_PLUGINS_DIR"/fzf-tab/fzf-tab.plugin.zsh
zstyle ':completion:*' matcher-list 'm:{a-z}={A-Za-z}'

# 👇 My preferred editor for local and remote sessions
if [[ -n $SSH_CONNECTION || "$TERM_PROGRAM" != "zed" ]]; then
  export EDITOR='nvim'
  export VISUAL='nvim'
else
  export EDITOR='zed --wait'
  export VISUAL='zed --wait'
fi

# 👇 My keybindings
bindkey "^A" beginning-of-line
bindkey "^E" end-of-line
bindkey "^[[1;3C" forward-word
bindkey "^[[1;3D" backward-word


# 👇 My binaries
export PATH="$HOME/dotfiles/bin:$PATH"

# 👇 LM Studio CLI tool
export PATH="$HOME/.cache/lm-studio/bin:$PATH"

# 👇 PostgreSQL
export LDFLAGS="-L/opt/homebrew/opt/postgresql@17/lib"
export CPPFLAGS="-I/opt/homebrew/opt/postgresql@17/include"
export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"

# 👇 OrbStack
source ~/.orbstack/shell/init.zsh 2>/dev/null || :

# 👇 atuin
eval "$(atuin init zsh)"

# 👇 zoxide
# z foo<tab> # shows the same completions as cd
# z foo<space><tab> # shows interactive completions via zoxide
eval "$(zoxide init zsh)"

# 👇 mise
eval "$(mise activate zsh)"
