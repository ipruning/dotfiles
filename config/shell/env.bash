# 👇 completions
fpath=("$HOME/dotfiles/config/shell/completions" "${fpath[@]}")
autoload -Uz compinit
compinit -d ~/.zcompdump-"$ZSH_VERSION"

# 👇 zsh Theme
eval "$(starship init zsh)"

# 👇 zsh options
setopt NO_NOMATCH
setopt NO_NULL_GLOB
setopt interactivecomments
zstyle ":completion:*" matcher-list "m:{a-z}={A-Za-z}"

# 👇 My preferred editor for local and remote sessions
export EDITOR="zed --wait"
export VISUAL="zed --wait"

# 👇 My keybindings
bindkey "^[f" forward-word
bindkey "^[b" backward-word
bindkey "^A" beginning-of-line
bindkey "^E" end-of-line
bindkey "^D" delete-word

# 👇 My binaries
export PATH="$HOME/dotfiles/bin:$PATH"

# 👇 LM Studio CLI tool
export PATH="$HOME/.cache/lm-studio/bin:$PATH"

# 👇 PostgreSQL
export LDFLAGS="-L/opt/homebrew/opt/postgresql@17/lib"
export CPPFLAGS="-I/opt/homebrew/opt/postgresql@17/include"
export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"

# 👇 OrbStack
source "$HOME/.orbstack/shell/init.zsh" 2>/dev/null || :

# 👇 zoxide
# z foo<tab> # shows the same completions as cd
# z foo<space><tab> # shows interactive completions via zoxide
eval "$(zoxide init zsh)"

# 👇 mise
eval "$(mise activate zsh)"

# 👇 fzf
# shellcheck disable=SC1090
source <(fzf --zsh)
export FZF_COMPLETION_TRIGGER="jk"
export FZF_DEFAULT_COMMAND="fd --type file --strip-cwd-prefix --hidden --follow --exclude .venv --exclude .git --exclude .DS_Store"
export FZF_DEFAULT_OPTS=" \
--color=bg+:#313244,bg:#1e1e2e,spinner:#f5e0dc,hl:#f38ba8 \
--color=fg:#cdd6f4,header:#f38ba8,info:#cba6f7,pointer:#f5e0dc \
--color=marker:#b4befe,fg+:#cdd6f4,prompt:#cba6f7,hl+:#f38ba8 \
--color=selected-bg:#45475a \
--multi"

# 👇 plugins
ZSH_PLUGINS_DIR="$HOME/dotfiles/config/shell/plugins"

# 👇 fzf-tab
source "$ZSH_PLUGINS_DIR"/fzf-tab/fzf-tab.plugin.zsh
# zstyle ":fzf-tab:*" continuous-trigger "ctrl-y"

# 👇 fast-syntax-highlighting https://github.com/catppuccin/zsh-fsh
source "$ZSH_PLUGINS_DIR"/fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh

# 👇 atuin
eval "$(atuin init zsh)"
