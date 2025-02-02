# 👇 zsh Theme
eval "$(starship init zsh)"

# 👇 plugins
ZSH_PLUGINS_DIR="$HOME/dotfiles/config/shell/plugins"

# 👇 fzf
# The user interface of fzf is fully customizable with a large number of configuration options.
# For a quick setup, you can start with one of the style presets — default, full, or minimal — using the --style option.
export FZF_DEFAULT_OPTS=" \
--style minimal \
--reverse \
--multi \
--bind 'ctrl-y:accept' \
--color=bg+:#313244,bg:#1e1e2e,spinner:#f5e0dc,hl:#f38ba8 \
--color=fg:#cdd6f4,header:#f38ba8,info:#cba6f7,pointer:#f5e0dc \
--color=marker:#b4befe,fg+:#cdd6f4,prompt:#cba6f7,hl+:#f38ba8 \
--color=selected-bg:#45475a"

# 👇 fzf-tab
source "$ZSH_PLUGINS_DIR"/fzf-tab/fzf-tab.plugin.zsh

zstyle ':completion:*:descriptions' format '[%d]'
zstyle ':completion:*' menu no
zstyle ':fzf-tab:*' use-fzf-default-opts yes

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

        # zle accept-line
    fi
}

zle -N tv-search _tv_search

bindkey '^T' tv-search

# 👇 fast-syntax-highlighting
source "$ZSH_PLUGINS_DIR"/fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh

# 👇 zsh options
setopt interactivecomments
zstyle ":completion:*" matcher-list "m:{a-z}={A-Za-z}"

autoload -U edit-command-line
zle -N edit-command-line
bindkey "^v" edit-command-line

# 👇 My preferred editor for local and remote sessions
# export EDITOR="zed --wait"
# export VISUAL="zed --wait"
export EDITOR="nvim"
export VISUAL="nvim"

# 👇 My keybindings
bindkey "^[f" forward-word
bindkey "^[b" backward-word
bindkey "^A" beginning-of-line
bindkey "^B" backward-char
bindkey "^D" delete-word
bindkey "^E" end-of-line
bindkey "^F" forward-char

# 👇 Custom paths
export PATH="$HOME/dotfiles/bin:$PATH"
source "$HOME/dotfiles/config/shell/functions/misc.zsh"
source "$HOME/dotfiles/config/shell/functions/db.zsh"
source "$HOME/dotfiles/config/shell/functions/g.zsh"
source "$HOME/dotfiles/config/shell/functions/surge.zsh"
export PATH="$HOME/developer/localhost/prototypes/utils/bin:$PATH"
export PATH="$HOME/developer/localhost/prototypes/utils/bash-scripts:$PATH"

# 👇 Mojo
export PATH="$HOME/.modular/bin:$PATH"

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
eval "$(atuin init zsh --disable-up-arrow)"

# 👇 mise
eval "$(mise activate zsh)"
