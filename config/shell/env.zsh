# 👇 plugins
ZSH_PLUGINS_DIR="$HOME/dotfiles/config/shell/plugins"

# 👇 fast-syntax-highlighting
source "$ZSH_PLUGINS_DIR"/fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh

# 👇 zsh-autosuggestions
# source "$ZSH_PLUGINS_DIR"/zsh-autosuggestions/zsh-autosuggestions.plugin.zsh

# 👇 zsh-autocomplete
# source "$ZSH_PLUGINS_DIR"/zsh-autocomplete/zsh-autocomplete.plugin.zsh
# zstyle ':autocomplete:*' add-space \
#     executables aliases functions builtins reserved-words commands
# bindkey -M emacs '^Y' .complete-word
# bindkey -M menuselect '^Y' .complete-word

# 👇 fzf
# shellcheck disable=SC1090
# FZF_CTRL_R_OPTS="" FZF_CTRL_T_COMMAND="" FZF_ALT_C_COMMAND="" source <(fzf --zsh)
# export FZF_COMPLETION_TRIGGER="jk"
# export FZF_DEFAULT_COMMAND="fd --type file \
# --strip-cwd-prefix \
# --follow"
# export FZF_DEFAULT_OPTS=" \
# --bind 'ctrl-y:accept' \
# --color=bg+:#313244,bg:#1e1e2e,spinner:#f5e0dc,hl:#f38ba8 \
# --color=fg:#cdd6f4,header:#f38ba8,info:#cba6f7,pointer:#f5e0dc \
# --color=marker:#b4befe,fg+:#cdd6f4,prompt:#cba6f7,hl+:#f38ba8 \
# --color=selected-bg:#45475a \
# --multi"
# _fzf_comprun() {
#   local command=$1
#   shift

#   case "$command" in
#     export|unset) fzf --preview-window=noborder --preview "eval 'echo \$'{}" "$@" ;;
#     ssh)          fzf --preview-window=noborder --preview 'dig {}' "$@" ;;
#     *)            fzf --preview-window=noborder --preview '' "$@" ;;
#   esac
# }
# _fzf_compgen_path() {
#   fd --type file \
#   --hidden \
#   --follow \
#   --exclude .git \
#   --exclude .venv \
#   --exclude .DS_Store \
#   . "$1"
# }
# _fzf_compgen_dir() {
#   fd --type directory \
#   --hidden \
#   --follow \
#   --exclude .git \
#   --exclude .venv \
#   --exclude .DS_Store \
#   . "$1"
# }
# _fzf_complete_j() {
#   _fzf_complete --reverse --prompt="fd> " -- "$@" < <(
#     fd --type directory \
#     --hidden \
#     --follow \
#     --exclude .git \
#     --exclude .venv \
#     --exclude .DS_Store \
#     .
#   )
# }

# 👇 fzf-tab
# source "$ZSH_PLUGINS_DIR"/fzf-tab/fzf-tab.plugin.zsh
# zstyle ':fzf-tab:*' fzf-bindings 'ctrl-y:accept'
# zstyle ':fzf-tab:*' accept-line enter

# 👇 zsh Theme
# eval "$(starship init zsh)"

# 👇 zsh options
# setopt NO_NOMATCH
# setopt NO_NULL_GLOB
setopt interactivecomments
zstyle ":completion:*" matcher-list "m:{a-z}={A-Za-z}"

# 👇 My preferred editor for local and remote sessions
export EDITOR="zed --wait"
export VISUAL="zed --wait"

# 👇 My keybindings
bindkey "^[f" forward-word
bindkey "^[b" backward-word
bindkey "^A" beginning-of-line
bindkey "^B" backward-char
bindkey "^D" delete-word
bindkey "^E" end-of-line
bindkey "^F" forward-char

# 👇 Edit command line
autoload -U edit-command-line
zle -N edit-command-line
bindkey "^v" edit-command-line

# 👇 Custom paths
export PATH="$HOME/dotfiles/bin:$PATH"
export PATH="$HOME/developer/localhost/prototypes/utils/bin:$PATH"
export PATH="$HOME/developer/localhost/prototypes/utils/shell-scripts:$PATH"

# 👇 LM Studio CLI tool
export PATH="$HOME/.cache/lm-studio/bin:$PATH"

# 👇 Mojo
export PATH="$HOME/.modular/bin:$PATH"

# 👇 Java
export PATH="/opt/homebrew/opt/openjdk/bin:$PATH"

# 👇 OrbStack
source "$HOME/.orbstack/shell/init.zsh" 2>/dev/null || :

# 👇 zoxide
eval "$(zoxide init zsh --cmd j)"

# 👇 mise
eval "$(mise activate zsh)"

# 👇 tv
eval "$(tv init zsh)"

# 👇 atuin
eval "$(atuin init zsh)"

# 👇 session utils
# https://github.com/zellij-org/zellij/issues/2744
# https://github.com/zellij-org/zellij/issues/3081#issuecomment-1904349853
function jump_to_repo() {
  local repo_path

  repo_path=$(tv git-repos)
  [[ -z "$repo_path" ]] && return
  cd "${repo_path}"

  local repo_name=$(basename "${repo_path}")

  # if [[ -n "$ZELLIJ" ]]; then
  #   zellij action rename-session "${repo_name}"
  # fi
}

function jump_to_repo_with_zellij_session() {
  if [[ -n "$ZELLIJ" ]]; then
  else
    local repo_path
    repo_path=$(tv git-repos)
    [[ -z "$repo_path" ]] && return
    cd "${repo_path}"
    local repo_name=$(basename "${repo_path}")
    zellij attach "${repo_name}" 2>/dev/null || zellij --session "${repo_name}"
  fi
}

function jump_to_zellij_session() {
  if [[ -n "$ZELLIJ" ]]; then
  else
    if [[ "$TERM" == "xterm-ghostty" ]]; then
      zj_sessions=$(zellij list-sessions --no-formatting --short)

      case $(echo "$zj_sessions" | grep -c '^.') in
        0)
          zellij
          ;;
        1)
          zellij attach "$zj_sessions"
          ;;
        *)
          selected_session=$(echo "$zj_sessions" | tv --no-preview) &&
          [[ -n "$selected_session" ]] && zellij attach "$selected_session"
          ;;
      esac
    fi
  fi
}
