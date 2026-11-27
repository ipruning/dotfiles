# 👇 case-insensitive matching
zstyle ":completion:*" matcher-list "m:{a-z}={A-Za-z}"

# 👇 fzf-tab
zstyle ':completion:*:descriptions' format '[%d]'
zstyle ':completion:*' menu no
zstyle ':fzf-tab:*' use-fzf-default-opts yes

# 👇 exe.dev hosts (cached and refreshed asynchronously so tab completion never blocks)
_exe_hosts() {
  emulate -L zsh
  setopt extendedglob nullglob

  local cache="$HOME/.cache/exe-hosts"
  local ttl=300  # seconds
  local age=999999
  local mtime
  if [[ -f "$cache" ]] && zmodload -F zsh/stat b:zstat 2>/dev/null && zmodload zsh/datetime 2>/dev/null; then
    if zstat -A mtime +mtime -- "$cache" 2>/dev/null; then
      age=$(( EPOCHSECONDS - mtime[1] ))
    fi
  fi
  if (( age > ttl )) && command -v jq >/dev/null 2>&1; then
    (
      mkdir -p "$HOME/.cache"
      local tmp="${cache}.$$"
      if ssh -o BatchMode=yes -o ConnectTimeout=2 -o ServerAliveInterval=2 -o ServerAliveCountMax=1 \
        exe.dev ls --json 2>/dev/null | jq -r '.vms[].ssh_dest' > "$tmp" 2>/dev/null \
        && [[ -s "$tmp" ]]; then
        mv "$tmp" "$cache"
      else
        rm -f "$tmp"
      fi
    ) >/dev/null 2>&1 &!
  fi

  local -Ua hosts
  # Preserve standard SSH config aliases and known_hosts alongside exe.dev hosts.
  if [[ -r "$HOME/.ssh/config" ]]; then
    local line word
    while IFS= read -r line; do
      if [[ $line == (#i)[[:space:]]#host[[:space:]]##* ]]; then
        line=${line#(#i)[[:space:]]#host[[:space:]]##}
        line=${line%%\#*}
        for word in ${=line}; do
          [[ $word != *[*?!]* ]] && hosts+=("$word")
        done
      fi
    done < "$HOME/.ssh/config"
  fi
  if [[ -r "$HOME/.ssh/known_hosts" ]]; then
    local khost
    for khost in ${(s/,/)${(f)"$(<"$HOME/.ssh/known_hosts")"}%%[ |\#]*}; do
      [[ -z $khost || $khost == *[*?@]* || $khost == \|* ]] && continue
      if [[ $khost == (#b)\[(*)\]:[[:digit:]]## ]]; then
        hosts+=("${match[1]}")
      else
        hosts+=("$khost")
      fi
    done
  fi
  [[ -s "$cache" ]] && hosts+=(${(f)"$(<"$cache")"})
  reply=("${hosts[@]}")
}
zstyle -e ':completion:*:(ssh|scp|rsync):*' hosts '_exe_hosts'
