llm() {
  ai "$@"
}

prompt() {
  local added_prompt=$(printf "%s " "$@")
  while IFS= read -r line; do
    echo "$line"
  done
  echo "$added_prompt"
}
