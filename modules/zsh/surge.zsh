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

function _surge-api-key() {
  perl -ne 'print $1 if /http-api = (.*?)@/' "$HOME/Library/Application Support/Surge/Profiles/default.conf"
}

function toggle-enhanced-mode() {
  local x_key=$(_surge-api-key)
  local current=$(xh --body GET https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key | jq -r '.enabled')
  if [[ "$current" == "false" ]]; then
    xh --quiet POST https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key enabled:=true
  else
    xh --quiet POST https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key enabled:=false
  fi
  sleep 1
  echo "Enhanced Mode: $(xh --body GET https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key | jq -r '.enabled')"
}

function toggle-outbound-mode() {
  local x_key=$(_surge-api-key)
  local current=$(xh --body GET https://localhost:6171/v1/outbound X-Key:$x_key | jq -r '.mode')
  if [[ "$current" == "rule" ]]; then
    xh --quiet POST https://localhost:6171/v1/outbound X-Key:$x_key mode=direct
  else
    xh --quiet POST https://localhost:6171/v1/outbound X-Key:$x_key mode=rule
  fi
  echo "Outbound Mode: $(xh --body GET https://localhost:6171/v1/outbound X-Key:$x_key | jq -r '.mode')"
}

function surge-status() {
  surge diagnostics
}

function surge-flush-dns() {
  surge flush dns
}

function surge-reload() {
  surge reload
}
