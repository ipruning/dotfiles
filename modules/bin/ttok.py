#!/bin/zsh -f

setopt no_unset pipe_fail
export LC_ALL=C

usage() {
  cat <<'EOF' >&2
Count tokens in text using tiktoken (o200k_base encoding).

Usage:
  echo "hello world" | ttok.py
  p | ttok.py                # clipboard text, or copied file paths
  ttok.py "hello world"
  ttok.py file.txt
  ttok.py < file.txt
EOF
}

if (( $# == 0 )) && [[ -t 0 ]]; then
  usage
  exit 1
fi

zmodload zsh/net/socket
zmodload zsh/system

script_dir=${0:A:h}
repo_root=${script_dir:h:h}
daemon_script="$repo_root/modules/libexec/ttok-daemon.py"
state_dir="$HOME/Library/Application Support/ttok"
log_dir="$HOME/Library/Logs/ttok"
socket_path="$state_dir/ttok-o200k-base-v3.sock"
log_file="$log_dir/ttok-daemon.log"

input_text=""
if (( $# == 0 )); then
  chunk_text=""
  while sysread -i 0 -s 1048576 chunk_text; do
    input_text+="$chunk_text"
  done
  if [[ -n "$chunk_text" ]]; then
    input_text+="$chunk_text"
  fi
fi

read_response() {
  local response_fd=$1
  local response_text=""
  local response_chunk=""
  while sysread -i "$response_fd" response_chunk; do
    response_text+="$response_chunk"
  done
  if [[ -n "$response_chunk" ]]; then
    response_text+="$response_chunk"
  fi
  print -rn -- "$response_text"
}

ping_daemon() {
  local ping_fd
  local ping_response

  zsocket "$socket_path" 2>/dev/null || return 1
  ping_fd=$REPLY
  syswrite -o "$ping_fd" $'PING\0' || {
    exec {ping_fd}>&-
    return 1
  }
  ping_response="$(read_response "$ping_fd")"
  exec {ping_fd}>&-

  [[ "$ping_response" == "OK" ]]
}

wait_for_daemon() {
  local attempt
  for attempt in {1..200}; do
    if ping_daemon; then
      return 0
    fi
    sleep 0.05
  done
  return 1
}

start_daemon() {
  if [[ -S "$socket_path" ]]; then
    return 0
  fi

  mkdir -p -- "$state_dir" "$log_dir"

  local lock_dir="$state_dir/start.lock"
  if mkdir -- "$lock_dir" 2>/dev/null; then
    if [[ ! -S "$socket_path" ]]; then
      rm -f -- "$socket_path"
      if [[ -x "$repo_root/.venv/bin/python" ]]; then
        nohup "$repo_root/.venv/bin/python" "$daemon_script" "$socket_path" >>"$log_file" 2>&1 &
      elif command -v uv >/dev/null 2>&1; then
        nohup uv run --project "$repo_root" python "$daemon_script" "$socket_path" >>"$log_file" 2>&1 &
      else
        rmdir -- "$lock_dir" 2>/dev/null || true
        print -ru2 -- "ttok.py: uv not found and $repo_root/.venv/bin/python is missing"
        return 1
      fi
    fi
    rmdir -- "$lock_dir" 2>/dev/null || true
  fi

  if ! wait_for_daemon; then
    print -ru2 -- "ttok.py: token daemon did not start"
    if [[ -f "$log_file" ]]; then
      tail -20 "$log_file" >&2 || true
    fi
    return 1
  fi
}

send_request() {
  local caller_dir="$(pwd -P)"
  local request_fd
  local arg_text

  zsocket "$socket_path"
  request_fd=$REPLY

  write_all() {
    local data_text="$1"
    local written_count
    while [[ -n "$data_text" ]]; do
      syswrite -c written_count -o "$request_fd" -- "$data_text"
      if (( written_count <= 0 )); then
        return 1
      fi
      data_text="${data_text[$(( written_count + 1 )),-1]}"
    done
  }

  write_all $'TTOK3\0'
  write_all "$caller_dir"
  write_all $'\0'
  write_all "$#"
  write_all $'\0'
  for arg_text in "$@"; do
    write_all "$arg_text"
    write_all $'\0'
  done
  write_all "${#input_text}"
  write_all $'\0'
  if (( $# == 0 )); then
    write_all "$input_text"
  fi

  read_response "$request_fd"
  exec {request_fd}>&-
}

start_daemon

if ! response="$(send_request "$@")"; then
  rm -f -- "$socket_path"
  start_daemon
  response="$(send_request "$@")" || {
    print -ru2 -- "ttok.py: token daemon request failed"
    exit 1
  }
fi

ok_prefix=$'OK\t'
err_prefix=$'ERR\t'

case "$response" in
  "$ok_prefix"*)
    print -r -- "${response#"$ok_prefix"}"
    ;;
  "$err_prefix"*)
    print -ru2 -- "${response#"$err_prefix"}"
    exit 1
    ;;
  *)
    print -ru2 -- "ttok.py: unexpected token daemon response"
    print -ru2 -- "$response"
    exit 1
    ;;
esac
