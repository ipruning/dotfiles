# echo ">>> .zshrc is loaded. Shell: $SHELL, Options: $-"

typeset -U path
typeset -U fpath

if [[ $OSTYPE == darwin* ]]; then
  if [[ -x /opt/homebrew/bin/brew ]]; then
    _brew=/opt/homebrew/bin/brew
  elif [[ -x /usr/local/bin/brew ]]; then
    _brew=/usr/local/bin/brew
  elif [[ -x /home/linuxbrew/.linuxbrew/bin/brew ]]; then
    _brew=/home/linuxbrew/.linuxbrew/bin/brew
  fi

  if [[ -n "${_brew:-}" ]]; then
    _cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/homebrew"
    _cache_file="${_cache_dir}/shellenv.zsh"
    mkdir -p "$_cache_dir"

    # Regenerate cache if missing or older than the brew executable.
    if [[ ! -s "$_cache_file" || "$_cache_file" -ot "$_brew" ]]; then
      "$_brew" shellenv >| "$_cache_file" 2>/dev/null
    fi

    source "$_cache_file"
    unset _brew _cache_dir _cache_file
  fi
fi

if [[ $OSTYPE == linux* ]]; then
  if [[ -r /opt/clash/script/common.sh && -r /opt/clash/script/clashctl.sh ]]; then
    builtin source /opt/clash/script/common.sh
    builtin source /opt/clash/script/clashctl.sh
    watch_proxy
  fi
fi

completion_paths=()
[[ -d "$HOME/dotfiles/config/shell/completions" ]] && completion_paths+=("$HOME/dotfiles/config/shell/completions")
completion_paths+=("${fpath[@]}")
fpath=("${completion_paths[@]}")
autoload -Uz compinit
for dump in ~/.zcompdump(N.mh+24); do
  compinit
done
compinit -C

[[ -d "$HOME/dotfiles" ]] && {
  config_files=(
    "$HOME/dotfiles/config/shell/aliases.zsh"
    "$HOME/dotfiles/config/shell/env.zsh"
    "$HOME/dotfiles/config/shell/env.private.zsh"
  )
  for file in "${config_files[@]}"; do
    [[ -e "$file" ]] && builtin source "$file"
  done
}
