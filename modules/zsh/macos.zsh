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
  local zellij_path="/opt/homebrew/bin/zellij"

  if [[ -n "$ZELLIJ" ]]; then
    :
  else
    zj_sessions=$($zellij_path list-sessions --no-formatting --short)
    case $(echo "$zj_sessions" | grep -c '^.') in
    0)
      $zellij_path
      ;;
    *)
      if local selected_session; selected_session=$(echo "$zj_sessions" | tv --no-preview); then
        if [[ -n "$selected_session" ]]; then
          $zellij_path attach "$selected_session"
        fi
      else
        :
      fi
      ;;
    esac
  fi
}

function jump-to-repo() {
  local repo_path
  repo_path=$(tv git-repos)
  local zellij_path="/opt/homebrew/bin/zellij"

  [[ -z "$repo_path" ]] && return
  if [[ -n "$ZELLIJ" ]]; then
    cd "${repo_path}"
  else
    cd "${repo_path}"
    local repo_name=$(basename "${repo_path}")
    $zellij_path attach "${repo_name}" 2>/dev/null || $zellij_path --session "${repo_name}" --new-session-with-layout dev
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

function mkdircd() {
  mkdir -p "$@" && cd "$1"
}

function serve() {
  local port=${1:-8000}
  local ip=$(ipconfig getifaddr en0)

  echo "Serving on ${ip}:${port} ..."
  uv run python -m http.server ${port}
}
