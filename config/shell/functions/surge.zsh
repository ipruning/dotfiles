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

function toggle-enhanced-mode() {
  local x_key=$(cat "$HOME/Library/Application Support/Surge/Profiles/default.conf" | perl -ne 'print $1 if /http-api = (.*?)@/')
  local current_status=$(xh --body GET https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key | jq | jq -r '.enabled')
  
  if [[ "$current_status" == "false" ]]; then
    xh --quiet POST https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key enabled:=true
  else
    xh --quiet POST https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key enabled:=false
  fi
  
  sleep 0.5
  xh --body GET https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key | jq
}

function set-jp-proxy() {
  local x_key=$(cat "$HOME/Library/Application Support/Surge/Profiles/default.conf" | perl -ne 'print $1 if /http-api = (.*?)@/')
  xh --quiet POST https://localhost:6171/v1/policy_groups/select X-Key:$x_key group_name='VPS' policy='V1-DEV-JP1-BWH-001'
  xh --body GET "https://localhost:6171/v1/policy_groups/select?group_name=VPS" X-Key:$x_key | jq

  xh --body POST https://localhost:6171/v1/features/system_proxy X-Key:$x_key enabled:=false
  xh --body GET https://localhost:6171/v1/features/system_proxy X-Key:$x_key | jq
  
  xh --quiet POST https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key enabled:=true
  sleep 0.5
  xh --body GET https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key | jq
}

function set-us-proxy() {
  local x_key=$(cat "$HOME/Library/Application Support/Surge/Profiles/default.conf" | perl -ne 'print $1 if /http-api = (.*?)@/')
  xh --quiet POST https://localhost:6171/v1/policy_groups/select X-Key:$x_key group_name='VPS' policy='V1-DEV-US1-BWH-001'
  xh --body GET "https://localhost:6171/v1/policy_groups/select?group_name=VPS" X-Key:$x_key | jq

  xh --body POST https://localhost:6171/v1/features/system_proxy X-Key:$x_key enabled:=false
  xh --body GET https://localhost:6171/v1/features/system_proxy X-Key:$x_key | jq

  xh --quiet POST https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key enabled:=true 
  sleep 0.5
  xh --body GET https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key | jq
}
