#===============================================================================
# 👇 Setup System Type
#===============================================================================
detect_system() {
  SYSTEM_ARCH=$(uname -m)
  SYSTEM_TYPE="unknown"

  case "$OSTYPE" in
  darwin*)
    case $SYSTEM_ARCH in
    arm64*) SYSTEM_TYPE="mac_arm64" ;;
    x86_64*) SYSTEM_TYPE="mac_x86_64" ;;
    *) SYSTEM_TYPE="unknown" ;;
    esac
    ;;
  linux*)
    case $SYSTEM_ARCH in
    x86_64*) SYSTEM_TYPE="linux_x86_64" ;;
    *armv7l*) SYSTEM_TYPE="raspberry" ;;
    *) SYSTEM_TYPE="unknown" ;;
    esac
    ;;
  *)
    SYSTEM_TYPE="unknown"
    ;;
  esac

  export SYSTEM_TYPE
}

detect_system

#===============================================================================
# 👇 Eval Homebrew Shellenv
#===============================================================================
case $SYSTEM_TYPE in
mac_arm64)
  eval "$(/opt/homebrew/bin/brew shellenv)"
  ;;
mac_x86_64)
  eval "$(/usr/local/homebrew/bin/brew shellenv)"
  ;;
linux_x86_64)
  eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
  ;;
unknown)
  echo "${RED}Unsupported system architecture.${NORMAL}"
  ;;
esac

#===============================================================================
# 👇 export homebrew & pipx & other binaries
#===============================================================================
export PATH="$HOME/.local/bin:$PATH"
export PATH="$HOME/.modular/bin:$PATH"
export PATH="$HOME/dotfiles/bin:$PATH"
