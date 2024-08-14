#===============================================================================
# 👇 Proxy Configuration
#===============================================================================
set_proxy() {
  export https_proxy=http://127.0.0.1:6152
  export http_proxy=http://127.0.0.1:6152
  export all_proxy=socks5://127.0.0.1:6153
  echo "Proxy set."
}

unset_proxy() {
  unset https_proxy http_proxy all_proxy
  echo "Proxy unset."
}

set_proxy

#===============================================================================
# 👇 Aliases and Environment Setup
#===============================================================================
r-lmql() {
  emulate bash -c '. ~/Coding/LangMax/.venv/bin/activate'
  ~/Coding/LangMax/.venv/bin/lmql "$@"
}

r-chainforge() {
  emulate bash -c '. ~/Coding/ChainForge/.venv/bin/activate'
  ~/Coding/ChainForge/.venv/bin/chainforge "$@"
}

alias code='cursor'

#===============================================================================
# 👇 Init
#===============================================================================
BOOTSTRAP_FILE="$HOME/dotfiles/config/shell/zsh_bootstrap.sh"
if [[ -f "$BOOTSTRAP_FILE" ]]; then
  source "$BOOTSTRAP_FILE"
else
  echo "Warning: $BOOTSTRAP_FILE not found."
fi
