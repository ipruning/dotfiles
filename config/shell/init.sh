#===============================================================================
# 👇 INIT
#===============================================================================
RED="$(tput setaf 1)"

if [ -z "$_INIT_SH_LOADED" ]; then
  _INIT_SH_LOADED=1
else
  return
fi

#===============================================================================
# 👇 csys
#===============================================================================

# if [[ "$(sysctl -a | grep machdep.cpu.brand_string)" == *Apple* ]]; then
#   echo test
# fi

SYSTEM_ARCH=$(uname -m)

case "$OSTYPE" in
darwin*)
  case $SYSTEM_ARCH in
  arm64*)
    SYSTEM_TYPE="mac_arm64"
    ;;
  x86_64*)
    SYSTEM_TYPE="mac_x86_64"
    ;;
  *)
    SYSTEM_TYPE="unknown"
    ;;
  esac
  ;;
linux*)
  case $SYSTEM_ARCH in
  x86_64*)
    SYSTEM_TYPE="linux_x86_64"
    ;;
  *armv7l*)
    SYSTEM_TYPE="raspberry"
    ;;
  *)
    SYSTEM_TYPE="unknown"
    ;;
  esac
  ;;
msys*)
  SYSTEM_TYPE="unknown"
  ;;
*)

  SYSTEM_TYPE="unknown"
  ;;
esac

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
