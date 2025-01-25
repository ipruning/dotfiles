function readit() {
  if [ $# -eq 0 ]; then
    echo "Error: No URL provided" >&2
    echo "Usage: readit <URL>" >&2
    exit 1
  fi

  url="$1"

  if [[ ! "$url" =~ ^[a-zA-Z0-9._/:%-]+$ ]]; then
    echo "Error: Invalid URL format" >&2
    exit 1
  fi

  if ! curl -fSL "https://r.jina.ai/$url" 2>/dev/null; then
    echo "Error: Failed to fetch https://r.jina.ai/$url" >&2
    exit 1
  fi
}

function buffit() {
  if [ -t 0 ]; then
    if [ -n "$my_buff" ]; then
      echo "$my_buff"
    else
      echo "Error: No data piped and 'my_buff' is empty."
    fi
  else
    read -r -d '' my_buff
    echo "Buffer updated."
  fi
}

function prompt() {
  local input=""
  local prompt_text=$(printf "%s " "$@")

  if ! [ -t 0 ]; then
    while IFS= read -r line; do
      input+="${line}"$'\n'
    done
    input=${input%$'\n'}
  fi

  if [[ -z "$input" ]]; then
    echo "$prompt_text"
  else
    echo "<context>"
    echo -e "$input"
    echo "</context>"
    echo
    echo "<prompt>"
    echo "$prompt_text"
    echo "</prompt>"
  fi
}

function catfiles() {
  local file_count=0
  for file in "$@"; do
    if [ -d "$file" ]; then
      echo "Skipping directory: $file" >&2
      continue
    fi
    if [[ -r "$file" ]]; then
      echo "File Name: $(basename "$file")"
      echo "File Content:"
      cat "$file"
      echo ""
      ((file_count++))
    else
      echo "Error: Cannot read $file" >&2
    fi
  done
  echo "Total files processed: $file_count"
}

function catscreen() {
  if [[ -z "$ZELLIJ" ]]; then
    echo "Not running inside a Zellij session."
    return 1
  fi

  zellij action dump-screen /tmp/screen-dump.txt
  sed '/^>.*catscreen/,$d' /tmp/screen-dump.txt
  rm /tmp/screen-dump.txt
}

function wtf() {
  local input=""
  local prompt_text=$(printf "%s " "$@")
  local screen_content=""

  if [[ -n "$ZELLIJ" ]]; then
    screen_content=$(catscreen)
  else
    echo "Not running inside a Zellij session."
    return 1
  fi

  if ! [ -t 0 ]; then
    while IFS= read -r line; do
      input+="${line}"$'\n'
    done
    input=${input%$'\n'}
  fi

  {
    if [[ -n "$screen_content" ]]; then
      echo "<terminal_context>"
      echo "$screen_content"
      echo "</terminal_context>"
      echo
    fi

    if [[ -n "$input" ]]; then
      echo "<context>"
      echo -e "$input"
      echo "</context>"
      echo
    fi

    echo "<prompt>"
    echo "$prompt_text"
    echo "</prompt>"
  } | llm | glow -
}

function repo-fork-sync() {
  gh repo list --fork --visibility public --json owner,name | jq -r 'map(.owner.login + "/" + .name) | .[]' | xargs -t -L1 gh repo sync
}

function set-ssh-auth-sock() {
  export SSH_AUTH_SOCK="$HOME/.1password/agent.sock"
  ssh-add -L
}

function unset-ssh-auth-sock() {
  unset SSH_AUTH_SOCK
}

function set-surge-proxy() {
  export https_proxy=http://127.0.0.1:6152
  export http_proxy=http://127.0.0.1:6152
  export all_proxy=socks5://127.0.0.1:6153
}

function unset-surge-proxy() {
  unset https_proxy http_proxy all_proxy
}
