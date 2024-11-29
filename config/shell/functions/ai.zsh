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
      input+="$line"
    done
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
