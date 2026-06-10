if [[ -n $ZSH_TRACE_STARTUP ]]; then
  zmodload zsh/datetime
  exec 2>"${ZSH_TRACE_FILE:-/tmp/zsh_profile_$$.log}"
  setopt xtrace prompt_subst
  PS4='+$EPOCHREALTIME> '
fi

typeset -U path
typeset -U fpath

# .zshrc is interactive-only. Base PATH belongs in `.zshenv`; do not call
# path_helper here because it can reorder PATH after our non-interactive-safe
# setup. Keep Homebrew metadata and completion paths here for interactive use.
if [[ ${OSTYPE:-} == darwin* ]]; then
  if [[ -d /opt/homebrew ]]; then
    export HOMEBREW_PREFIX="/opt/homebrew"
    export HOMEBREW_CELLAR="/opt/homebrew/Cellar"
    export HOMEBREW_REPOSITORY="/opt/homebrew"

    [[ -d /opt/homebrew/share/zsh/site-functions ]] && \
      fpath=(/opt/homebrew/share/zsh/site-functions $fpath)
    export INFOPATH="/opt/homebrew/share/info:${INFOPATH:-}"
  elif [[ -d /usr/local/Homebrew ]]; then
    export HOMEBREW_PREFIX="/usr/local"
    export HOMEBREW_CELLAR="/usr/local/Cellar"
    export HOMEBREW_REPOSITORY="/usr/local/Homebrew"

    [[ -d /usr/local/share/zsh/site-functions ]] && \
      fpath=(/usr/local/share/zsh/site-functions $fpath)
    export INFOPATH="/usr/local/share/info:${INFOPATH:-}"
  fi
fi

if [[ $OSTYPE == linux* ]]; then
  if [[ -r /opt/clash/script/common.sh && -r /opt/clash/script/clashctl.sh ]]; then
    builtin source /opt/clash/script/common.sh
    builtin source /opt/clash/script/clashctl.sh
    watch_proxy
  fi
fi

GENERATED_COMPLETIONS_DIR="$HOME/dotfiles/generated/completions"

completion_paths=()
[[ -d "$GENERATED_COMPLETIONS_DIR" ]] && completion_paths+=("$GENERATED_COMPLETIONS_DIR")
completion_paths+=("${fpath[@]}")
fpath=("${completion_paths[@]}")
autoload -Uz compinit
for dump in ~/.zcompdump(N.mh+24); do
  compinit -i
done
compinit -i -C

ZSH_MODULES_DIR="$HOME/dotfiles/modules/zsh"

[[ -d "$ZSH_MODULES_DIR" ]] && {
  config_files=(
    "$ZSH_MODULES_DIR/aliases.zsh"
    "$ZSH_MODULES_DIR/env.zsh"
    "$ZSH_MODULES_DIR/env.private.zsh"
    "$ZSH_MODULES_DIR/completions.zsh"  # after env.zsh so fzf-tab plugin is loaded first
  )
  for file in "${config_files[@]}"; do
    [[ -e "$file" ]] && builtin source "$file"
  done
}

:
