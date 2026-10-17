function set-all-proxy() {
  export https_proxy=http://127.0.0.1:6152
  export http_proxy=http://127.0.0.1:6152
  export all_proxy=socks5://127.0.0.1:6153
}

function unset-all-proxy() {
  unset https_proxy
  unset http_proxy
  unset all_proxy
}

function _surge-cli() {
  /Applications/Surge.app/Contents/Applications/surge-cli "$@"
}

function toggle-enhanced-mode() {
  local enabled
  enabled=$(_surge-cli --raw feature get enhanced-mode | jq -r '.enabled') || return
  if [[ "$enabled" == "true" ]]; then
    _surge-cli feature set enhanced-mode off >/dev/null
  else
    _surge-cli feature set enhanced-mode on >/dev/null
  fi
  echo "Enhanced Mode: $(_surge-cli --raw feature get enhanced-mode | jq -r '.enabled')"
}

function toggle-outbound-mode() {
  local mode
  mode=$(_surge-cli --raw mode get | jq -r '.mode') || return
  if [[ "$mode" == "rule" ]]; then
    _surge-cli mode set direct >/dev/null
  else
    _surge-cli mode set rule >/dev/null
  fi
  echo "Outbound Mode: $(_surge-cli --raw mode get | jq -r '.mode')"
}
