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
  if [[ -n "$ZELLIJ" ]]; then
  else
    if [[ "$TERM_PROGRAM" == "ghostty" ]]; then
      zj_sessions=$(/opt/homebrew/bin/zellij list-sessions --no-formatting --short)
      case $(echo "$zj_sessions" | grep -c '^.') in
      0)
        /opt/homebrew/bin/zellij
        ;;
      *)
        selected_session=$(echo "$zj_sessions" | /opt/homebrew/bin/tv --no-preview) &&
          [[ -n "$selected_session" ]] && /opt/homebrew/bin/zellij attach "$selected_session"
        ;;
      esac
    fi
  fi
}

function jump-to-repo() {
  local repo_path
  repo_path=$(tv git-repos)
  [[ -z "$repo_path" ]] && return
  if [[ -n "$ZELLIJ" ]]; then
    cd "${repo_path}"
  else
    cd "${repo_path}"
    local repo_name=$(basename "${repo_path}")
    zellij attach "${repo_name}" 2>/dev/null || zellij --session "${repo_name}"
  fi
}


function pf() {
  set -f
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

  echo $PUEUE_TASKS | sh | fzf --header "${header}" -m \
    --preview="echo {} | cut -d'|' -f1 | xargs pueue log | bat -l log --style=rule,numbers --color=always -r ':200'" \
    --bind="$bind"
  set +f
}
