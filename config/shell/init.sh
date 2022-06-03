#===============================================================================
# 👇 init
#===============================================================================
RED="$(tput setaf 1)"

if [ -z "$_INIT_SH_LOADED" ]; then
  _INIT_SH_LOADED=1
else
  return
fi

#===============================================================================
# 👇 zprof
#===============================================================================
# zmodload zsh/zprof # 在 ~/.zshrc 的头部加上这个，加载 profile 模块

#===============================================================================
# 👇 env
#===============================================================================

case $SYSTEM_TYPE in
mac_arm64 | mac_x86_64 | linux_x86_64 | raspberry)
  if [ -n "$BASH_VERSION" ] || [ -n "$ZSH_VERSION" ]; then
    # run script for interactive mode of bash/zsh
    if [[ $- == *i* ]] && [ -z "$_INIT_SH_NOFUN" ]; then
      if [ -f "$HOME/dotfiles/config/shell/zsh_env.sh" ]; then
        . "$HOME/dotfiles/config/shell/zsh_env.sh"
      fi
      if [ -f "$HOME/dotfiles/config/shell/zsh_functions.sh" ]; then
        . "$HOME/dotfiles/config/shell/zsh_functions.sh"
      fi
      if [ -f "$HOME/dotfiles/config/shell/zsh_aliases.sh" ]; then
        . "$HOME/dotfiles/config/shell/zsh_aliases.sh"
      fi
      if [ -f "$HOME/dotfiles/config/shell/zsh_completion.sh" ]; then
        . "$HOME/dotfiles/config/shell/zsh_completion.sh"
      fi
    fi
  fi
  ;;
unknown)
  echo "${RED}Unsupported system architecture.${NORMAL}"
  ;;
esac

#===============================================================================
# 👇 zprof
#===============================================================================
# zprof
