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
  uv run --no-project python -m http.server "${port}"
}
