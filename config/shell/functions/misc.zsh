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

function _self_completion() {
  echo -e "\033[33mGenerating completions...\033[0m"
  rm -f ~/.zcompdump
  compinit
}

function _self_update() {
  echo -e "\033[33mUpdating Homebrew...\033[0m"
  brew update

  echo -e "\033[33mUpdating tldr pages...\033[0m"
  tldr --update
}

function _self_upgrade() {
  echo -e "\033[33mUpgrading Homebrew formulas...\033[0m"
  brew upgrade

  echo -e "\033[33mCleaning up Homebrew...\033[0m"
  brew cleanup && brew autoremove

  echo -e "\033[33mUpgrading GitHub CLI extensions...\033[0m"
  gh extension upgrade --all

  echo -e "\033[33mUpdating mise...\033[0m"
  mise upgrade --bump
}

function _self_backup() {
  echo -e "\033[33mBacking up all packages...\033[0m"
  brew bundle dump --file="$HOME"/dotfiles/config/packages/Brewfile --force
  brew leaves >"$HOME"/dotfiles/config/packages/Brewfile.txt
  gh extension list | awk '{print $3}' >"$HOME"/dotfiles/config/packages/gh_extensions.txt
  find /Applications -maxdepth 1 -name "*.app" -exec basename {} .app \; | sort >"$HOME"/dotfiles/config/packages/macos_applications.txt
  find /Applications/Setapp -maxdepth 1 -name "*.app" -exec basename {} .app \; | sort >"$HOME"/dotfiles/config/packages/macos_setapp.txt
}
