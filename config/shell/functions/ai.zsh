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
