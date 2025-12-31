# Startup profiling (triggered by ZSH_TRACE_STARTUP=1)
if [[ -n $ZSH_TRACE_STARTUP ]]; then
  zmodload zsh/datetime
  exec 2>"${ZSH_TRACE_FILE:-/tmp/zsh_profile_$$.log}"
  setopt xtrace prompt_subst
  PS4='+$EPOCHREALTIME> '
fi

typeset -U path
typeset -U fpath

if [[ $OSTYPE == darwin* ]]; then
  export HOMEBREW_PREFIX="/opt/homebrew";
  export HOMEBREW_CELLAR="/opt/homebrew/Cellar";
  export HOMEBREW_REPOSITORY="/opt/homebrew";
  fpath[1,0]="/opt/homebrew/share/zsh/site-functions";
  eval "$(/usr/bin/env PATH_HELPER_ROOT="/opt/homebrew" /usr/libexec/path_helper -s)"
  [ -z "${MANPATH-}" ] || export MANPATH=":${MANPATH#:}";
  export INFOPATH="/opt/homebrew/share/info:${INFOPATH:-}";
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
