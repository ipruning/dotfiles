# 👇 case-insensitive matching
zstyle ":completion:*" matcher-list "m:{a-z}={A-Za-z}"

# 👇 fzf-tab
zstyle ':completion:*:descriptions' format '[%d]'
zstyle ':completion:*' menu no
zstyle ':fzf-tab:*' use-fzf-default-opts yes

# 👇 exe.dev hosts (cached: ssh round-trip would block tab completion otherwise)
_exe_hosts() {
  local cache="$HOME/.cache/exe-hosts"
  local ttl=300  # seconds
  local age=999999
  if [[ -f "$cache" ]]; then
    age=$(( $(date +%s) - $(stat -f %m "$cache" 2>/dev/null || echo 0) ))
  fi
  if (( age > ttl )); then
    mkdir -p "$HOME/.cache"
    ssh exe.dev ls --json 2>/dev/null | jq -r '.vms[].ssh_dest' > "$cache" 2>/dev/null
  fi
  [[ -s "$cache" ]] && reply=(${(f)"$(<"$cache")"})
}
zstyle -e ':completion:*:(ssh|scp|rsync):*' hosts '_exe_hosts'
