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

# function set-smart-proxy() {
#   local x_key=$(cat "$HOME/Library/Application Support/Surge/Profiles/default.conf" | perl -ne 'print $1 if /http-api = (.*?)@/')
#   xh --quiet POST https://localhost:6171/v1/policy_groups/select X-Key:$x_key group_name='Automatic' policy='VPS_SMART'
#   echo "Policy Group Status: $(xh --body GET "https://localhost:6171/v1/policy_groups/select?group_name=VPS_SMART" X-Key:$x_key | jq -r '.policy')"
#   xh --quiet POST https://localhost:6171/v1/features/system_proxy X-Key:$x_key enabled:=false
#   xh --quiet POST https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key enabled:=true
#   sleep 1
#   echo "System Proxy Status: $(xh --body GET https://localhost:6171/v1/features/system_proxy X-Key:$x_key | jq -r '.enabled')"
#   echo "Enhanced Mode Status: $(xh --body GET https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key | jq -r '.enabled')"
# }

# function set-jp-proxy() {
#   local x_key=$(cat "$HOME/Library/Application Support/Surge/Profiles/default.conf" | perl -ne 'print $1 if /http-api = (.*?)@/')
#   xh --quiet POST https://localhost:6171/v1/policy_groups/select X-Key:$x_key group_name='VPS' policy='V1-DEV-JP1-BWH-001'
#   xh --quiet POST https://localhost:6171/v1/policy_groups/select X-Key:$x_key group_name='Automatic' policy='VPS'
#   echo "Policy Group Status: $(xh --body GET "https://localhost:6171/v1/policy_groups/select?group_name=VPS" X-Key:$x_key | jq -r '.policy')"
#   xh --quiet POST https://localhost:6171/v1/features/system_proxy X-Key:$x_key enabled:=false
#   xh --quiet POST https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key enabled:=true
#   sleep 1
#   echo "System Proxy Status: $(xh --body GET https://localhost:6171/v1/features/system_proxy X-Key:$x_key | jq -r '.enabled')"
#   echo "Enhanced Mode Status: $(xh --body GET https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key | jq -r '.enabled')"
# }

# function set-us-proxy() {
#   local x_key=$(cat "$HOME/Library/Application Support/Surge/Profiles/default.conf" | perl -ne 'print $1 if /http-api = (.*?)@/')
#   xh --quiet POST https://localhost:6171/v1/policy_groups/select X-Key:$x_key group_name='VPS' policy='V1-DEV-US1-BWH-001'
#   xh --quiet POST https://localhost:6171/v1/policy_groups/select X-Key:$x_key group_name='Automatic' policy='VPS'
#   echo "Policy Group Status: $(xh --body GET "https://localhost:6171/v1/policy_groups/select?group_name=VPS" X-Key:$x_key | jq -r '.policy')"
#   xh --quiet POST https://localhost:6171/v1/features/system_proxy X-Key:$x_key enabled:=false
#   xh --quiet POST https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key enabled:=true
#   sleep 1
#   echo "System Proxy Status: $(xh --body GET https://localhost:6171/v1/features/system_proxy X-Key:$x_key | jq -r '.enabled')"
#   echo "Enhanced Mode Status: $(xh --body GET https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key | jq -r '.enabled')"
# }

function toggle-outbound-mode() {
  local x_key=$(cat "$HOME/Library/Application Support/Surge/Profiles/default.conf" | perl -ne 'print $1 if /http-api = (.*?)@/')
  local current_status=$(xh --body GET https://localhost:6171/v1/outbound X-Key:$x_key | jq -r '.mode')
  if [[ "$current_status" == "rule" ]]; then
    xh --quiet POST https://localhost:6171/v1/outbound X-Key:$x_key mode=direct
  else
    xh --quiet POST https://localhost:6171/v1/outbound X-Key:$x_key mode=rule
  fi
  echo "Outbound Mode Status: $(xh --body GET https://localhost:6171/v1/outbound X-Key:$x_key | jq -r '.mode')"
}

function toggle-enhanced-mode() {
  local x_key=$(cat "$HOME/Library/Application Support/Surge/Profiles/default.conf" | perl -ne 'print $1 if /http-api = (.*?)@/')
  local current_status=$(xh --body GET https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key | jq -r '.enabled')

  if [[ "$current_status" == "false" ]]; then
    xh --quiet POST https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key enabled:=true
  else
    xh --quiet POST https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key enabled:=false
  fi

  sleep 1
  echo "Enhanced Mode Status: $(xh --body GET https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key | jq -r '.enabled')"
}
