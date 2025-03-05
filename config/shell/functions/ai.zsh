function readit() {
  if [ $# -eq 0 ]; then
    logger "No URL provided" "ERROR"
  fi

  local url="$1"

  if [[ ! "$url" =~ ^[a-zA-Z0-9._/:%-]+$ ]]; then
    logger "Invalid URL format" "ERROR"
    exit 1
  fi

  if ! curl -fSL "https://r.jina.ai/$url" 2>/dev/null; then
    logger "Failed to fetch https://r.jina.ai/$url" "ERROR"
    exit 1
  fi
}

function buffit() {
  if [ -t 0 ]; then
    if [ -n "$my_buff" ]; then
      echo "$my_buff"
    else
      logger "No data piped and 'my_buff' is empty." "WARN"
    fi
  else
    read -r -d '' my_buff
    logger "Buffer updated."
  fi
}

function catscreen() {
  if [[ -z "$ZELLIJ" ]]; then
    logger "Not running inside a Zellij session." "WARN"
    return 1
  fi

  local temp_file
  temp_file=$(mktemp) || return 1

  zellij action dump-screen "$temp_file"
  rg --invert-match --no-line-number '^\s*$' "$temp_file"
  rip "$temp_file"
}

function prompt() {
  local args=("$@")
  local terminal_context=""
  local other_context=""

  if ! [ -t 0 ]; then
    while IFS= read -r line; do
      other_context+="${line}"$'\n'
    done
    other_context=${other_context%$'\n'}
  fi

  local prompt
  if [[ -n "$ZELLIJ" ]]; then
    terminal_context=$(catscreen | sed '$d')

    prompt=$(
      if [[ -n "$terminal_context" ]]; then
        echo "<terminal_context>"
        echo "$terminal_context"
        echo "</terminal_context>"
        echo
      fi

      if [[ -n "$other_context" ]]; then
        echo "<other_context>"
        echo -e "$other_context"
        echo "</other_context>"
        echo
      fi

      if ((${#args[@]} > 0)); then
        echo "<user_instructions>"
        printf "%s " "${args[@]}"
        echo
        echo "</user_instructions>"
      fi
    )
  else
    prompt=$(
      if [[ -n "$other_context" ]]; then
        echo "<other_context>"
        echo -e "$other_context"
        echo "</other_context>"
        echo
      fi

      if ((${#args[@]} > 0)); then
        echo "<user_instructions>"
        printf "%s " "${args[@]}"
        echo
        echo "</user_instructions>"
      fi
    )
  fi

  echo "$prompt"
}

function aid() {
  local other_context=""
  if ! [ -t 0 ]; then
    while IFS= read -r line; do
      other_context+="${line}"$'\n'
    done
    other_context=${other_context%$'\n'}
  fi
  echo "$other_context" | llm | richify.py
}

function aid-chatgpt() {
  local other_context=""
  if ! [ -t 0 ]; then
    while IFS= read -r line; do
      other_context+="${line}"$'\n'
    done
    other_context=${other_context%$'\n'}
  fi
  echo "$other_context" | chatgpt-cli.py
}

function aid-chatgpt-pro() {
  local other_context=""
  if ! [ -t 0 ]; then
    while IFS= read -r line; do
      other_context+="${line}"$'\n'
    done
    other_context=${other_context%$'\n'}
  fi
  echo "$other_context" | chatgpt-cli.py --pro
}
