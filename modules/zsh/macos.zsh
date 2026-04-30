function repo-fork-sync() {
  gh repo list --fork --visibility public --json owner,name | jq -r 'map(.owner.login + "/" + .name) | .[]' | xargs -t -L1 gh repo sync
}

function x86_64-zsh-login() {
  arch -x86_64 zsh --login
}

function x86_64-zsh-run() {
  arch -x86_64 zsh -c "$@"
}

function jump-to-session() {
  local zellij_path
  zellij_path="$(command -v zellij)" || { print -u2 "zellij not found"; return 1; }

  if [[ -n "$ZELLIJ" ]]; then
    return 0
  fi

  local zj_sessions
  zj_sessions=$("$zellij_path" list-sessions --no-formatting --short)
  if [[ -z "$zj_sessions" ]]; then
    "$zellij_path"
    return
  fi

  local selected_session
  selected_session=$(echo "$zj_sessions" | tv --no-preview) || return
  [[ -n "$selected_session" ]] && "$zellij_path" attach "$selected_session"
}

function jump-to-repo() {
  local repo_path zellij_path
  repo_path=$(tv git-repos)
  [[ -z "$repo_path" ]] && return

  cd "${repo_path}"
  if [[ -n "$ZELLIJ" ]]; then
    return 0
  fi

  zellij_path="$(command -v zellij)" || { print -u2 "zellij not found"; return 1; }
  local repo_name
  repo_name=$(basename "${repo_path}")
  "$zellij_path" attach "${repo_name}" 2>/dev/null \
    || "$zellij_path" --session "${repo_name}" --new-session-with-layout dev
}

function pf() {
  emulate -L zsh
  setopt local_options noglob

  local PUEUE_TASKS=$(cat <<'EOF'
pueue status --json | jq -c '.tasks' | jq -r '
  .[] |
  ( .id | tostring | (" " * (2 - length)) + . ) as $id_padded | # Left-pad ID to 2 chars
  ( .created_at | split("T")[1] | split(".")[0] ) as $created_time | # Extract HH:MM:SS from string
  ( .status | keys[0] ) as $status_raw | ($status_raw + (" " * (8 - ($status_raw | length)))) as $status_padded | # Right-pad Status to 8 chars
  .command as $command |
  "\($id_padded) | \($created_time) | \($status_padded) | \($command)"
'
EOF
)
  local header=" ctrl-[p]ause [s]tart [r]estart [k]ill [l]og [f]ilter"

  local bind="\
ctrl-p:execute-silent(echo {} | cut -d'|' -f1 | xargs pueue pause > /dev/null)+reload^$PUEUE_TASKS^,\
ctrl-s:execute-silent(echo {} | cut -d'|' -f1 | xargs pueue start > /dev/null)+reload^$PUEUE_TASKS^,\
ctrl-r:execute-silent(echo {} | cut -d'|' -f1 | xargs pueue restart -ik > /dev/null)+reload^$PUEUE_TASKS^,\
ctrl-k:execute-silent(echo {} | cut -d'|' -f1 | xargs pueue kill > /dev/null)+reload^$PUEUE_TASKS^,\
ctrl-l:execute-silent(echo {} | cut -d'|' -f1 | xargs pueue log | less > /dev/tty),\
ctrl-f:reload^$PUEUE_TASKS^\
"

  fzf --header "${header}" -m \
    --preview="echo {} | cut -d'|' -f1 | xargs pueue log | bat -l log --style=rule,numbers --color=always -r ':200'" \
    --bind="$bind" \
    < <(eval "$PUEUE_TASKS")
}

function serve() {
  local port=${1:-8000}
  local ip
  for iface in en0 en1 en2; do
    ip=$(ipconfig getifaddr "$iface" 2>/dev/null) && [[ -n "$ip" ]] && break
  done
  ip="${ip:-127.0.0.1}"

  echo "Serving on ${ip}:${port} ..."
  uv run python -m http.server "${port}"
}
