#===============================================================================
# 👇 Proxy Configuration
#===============================================================================
set_proxy() {
  export https_proxy=http://127.0.0.1:6152
  export http_proxy=http://127.0.0.1:6152
  export all_proxy=socks5://127.0.0.1:6153
}

unset_proxy() {
  unset https_proxy http_proxy all_proxy
}

set_proxy

#===============================================================================
# 👇 Init
#===============================================================================
BOOTSTRAP_FILE="$HOME/dotfiles/config/shell/bootstrap.zsh"
if [[ -f "$BOOTSTRAP_FILE" ]]; then
  source "$BOOTSTRAP_FILE"
else
  echo "Warning: $BOOTSTRAP_FILE not found."
fi
