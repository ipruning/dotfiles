# 👇 completions
fpath=("$HOME/dotfiles/config/shell/completions" "${fpath[@]}")
autoload -Uz compinit
compinit -d ~/.zcompdump-"$ZSH_VERSION"

# 👇 plugins
ZSH_PLUGINS_DIR="$HOME/dotfiles/config/shell/plugins"

# 👇 fast-syntax-highlighting
source "$ZSH_PLUGINS_DIR"/fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh

# 👇 zsh-autosuggestions
# source "$ZSH_PLUGINS_DIR"/zsh-autosuggestions/zsh-autosuggestions.plugin.zsh
# bindkey '^Y' autosuggest-accept

# 👇 zsh-autocomplete
source "$ZSH_PLUGINS_DIR"/zsh-autocomplete/zsh-autocomplete.plugin.zsh
bindkey -M menuselect '^N' down-line-or-history
bindkey -M menuselect '^P' up-line-or-history

function accept-autocomplete-suggestion() {
  zle .complete-word

  if [[ "$LBUFFER" != *' ' ]]; then
    LBUFFER="$LBUFFER "
  fi

  zle -M "🔥 Let's go 🔥"
  return 0
}
zle -N accept-autocomplete-suggestion

bindkey -M emacs '^Y' accept-autocomplete-suggestion
bindkey -M menuselect '^Y' accept-autocomplete-suggestion

function remove-trailing-whitespace() {
  LBUFFER="${LBUFFER%"${LBUFFER##*[![:space:]]}"}"
}

function accept-line-without-trailing-whitespace() {
  remove-trailing-whitespace
  zle accept-line
}

zle -N accept-line-without-trailing-whitespace
bindkey '^M' accept-line-without-trailing-whitespace
# bindkey $'\r' accept-line-without-trailing-whitespace
# bindkey '^J' accept-line-without-trailing-whitespace


# 👇 fzf
# shellcheck disable=SC1090
FZF_CTRL_R_OPTS="" FZF_CTRL_T_COMMAND="" FZF_ALT_C_COMMAND="" source <(fzf --zsh)
export FZF_COMPLETION_TRIGGER="jk"
export FZF_DEFAULT_COMMAND="fd --type file \
--strip-cwd-prefix \
--follow"
# theme https://github.com/catppuccin/zsh-fsh
export FZF_DEFAULT_OPTS=" \
--color=bg+:#313244,bg:#1e1e2e,spinner:#f5e0dc,hl:#f38ba8 \
--color=fg:#cdd6f4,header:#f38ba8,info:#cba6f7,pointer:#f5e0dc \
--color=marker:#b4befe,fg+:#cdd6f4,prompt:#cba6f7,hl+:#f38ba8 \
--color=selected-bg:#45475a \
--multi"
_fzf_compgen_path() {
    fd --type f \
       --hidden \
       --follow \
       --exclude .git \
       --exclude .venv \
       --exclude .DS_Store \
       . "$1"
}
_fzf_compgen_dir() {
    fd --type d \
       --hidden \
       --follow \
       --exclude .git \
       --exclude .venv \
       --exclude .DS_Store \
       . "$1"
}

# 👇 fzf-tab
# source "$ZSH_PLUGINS_DIR"/fzf-tab/fzf-tab.plugin.zsh

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

# 👇 Mojo
export PATH="$HOME/.modular/bin:$PATH"

# 👇 PostgreSQL
export LDFLAGS="-L/opt/homebrew/opt/postgresql@17/lib"
export CPPFLAGS="-I/opt/homebrew/opt/postgresql@17/include"
export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"

# 👇 OrbStack
source "$HOME/.orbstack/shell/init.zsh" 2>/dev/null || :

# 👇 zoxide
eval "$(zoxide init zsh --cmd j)"

# 👇 mise
eval "$(mise activate zsh)"

# 👇 atuin
eval "$(atuin init zsh)"
