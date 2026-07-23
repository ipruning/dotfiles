# Keep directory-changing behavior in the current shell.
try-rs() {
  local arg
  for arg in "$@"; do
    case "$arg" in
      -h|--help|-V|--version|--setup|--setup=*|--setup-stdout|--setup-stdout=*|--setup-clear|--completions|--completions=*)
        command try-rs "$@"
        return
        ;;
    esac
  done

  local output exit_code
  output=$(command try-rs "$@")
  exit_code=$?
  if (( exit_code != 0 )); then
    [[ -n "$output" ]] && print -r -- "$output"
    return "$exit_code"
  fi

  if [[ -n "$output" ]]; then
    eval "$output"
  fi
}
alias try="try-rs"

_try_rs_get_tries_paths() {
  if [[ -n "${TRY_PATH}" ]]; then
    print -r -- "${TRY_PATH}" | tr ',' '\n'
    return
  fi

  local -a config_files=()
  [[ -n "${TRY_CONFIG_DIR:-}" ]] && config_files+=("$TRY_CONFIG_DIR/config.toml")
  if [[ -n "${XDG_CONFIG_HOME:-}" ]]; then
    config_files+=("$XDG_CONFIG_HOME/try-rs/config.toml")
  else
    config_files+=("$HOME/Library/Application Support/try-rs/config.toml")
  fi
  config_files+=("$HOME/.config/try-rs/config.toml" "$HOME/.try-rs/config.toml")

  local config_file try_paths
  for config_file in "${config_files[@]}"; do
    if [[ -f "$config_file" ]]; then
      try_paths=$(command mise config get -f "$config_file" tries_paths 2>/dev/null)
      if [[ -z "$try_paths" ]]; then
        try_paths=$(command mise config get -f "$config_file" tries_path 2>/dev/null)
      fi
      if [[ -n "$try_paths" ]]; then
        print -r -- "$try_paths" | tr ',' '\n'
        return
      fi
    fi
  done
}

_try_rs_complete() {
  local -a dirs=()
  local try_path
  while IFS= read -r try_path; do
    try_path="${try_path#"${try_path%%[![:space:]]*}"}"
    try_path="${try_path%"${try_path##*[![:space:]]}"}"
    if [[ "$try_path" == "~/"* ]]; then
      try_path="$HOME/${try_path#\~/}"
    fi
    [[ -d "$try_path" ]] && dirs+=("$try_path"/*(/N:t))
  done < <(_try_rs_get_tries_paths)
  compadd -a dirs
}
compdef _try_rs_complete try-rs
compdef _try_rs_complete try
