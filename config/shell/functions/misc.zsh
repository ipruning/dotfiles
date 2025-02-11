function my_logger() {
  local RED='\033[0;31m'
  local YELLOW='\033[1;33m'
  local GRAY='\033[0;90m'
  local NC='\033[0m'

  local message=$1
  local loglevel=${2:-"INFO"}
  local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  local color=$GRAY

  case "${loglevel:u}" in
  "ERROR")
    color=$RED
    ;;
  "WARN")
    color=$YELLOW
    ;;
  "INFO")
    if [ "$DRY_RUN" = true ]; then
      color=$YELLOW
    else
      color=$GRAY
    fi
    ;;
  *)
    loglevel="INFO"
    color=$GRAY
    ;;
  esac

  printf "${color}[%s] [%s] %s${NC}\n" "$timestamp" "${loglevel:u}" "$message"
}

function readit() {
  if [ $# -eq 0 ]; then
    my_logger "No URL provided" "ERROR"
  fi

  url="$1"

  if [[ ! "$url" =~ ^[a-zA-Z0-9._/:%-]+$ ]]; then
    my_logger "Invalid URL format" "ERROR"
    exit 1
  fi

  if ! curl -fSL "https://r.jina.ai/$url" 2>/dev/null; then
    my_logger "Failed to fetch https://r.jina.ai/$url" "ERROR"
    exit 1
  fi
}

function buffit() {
  if [ -t 0 ]; then
    if [ -n "$my_buff" ]; then
      echo "$my_buff"
    else
      my_logger "No data piped and 'my_buff' is empty." "WARN"
    fi
  else
    read -r -d '' my_buff
    my_logger "Buffer updated."
  fi
}

function catscreen() {
  if [[ -z "$ZELLIJ" ]]; then
    my_logger "Not running inside a Zellij session." "WARN"
    return 1
  fi

  zellij action dump-screen /tmp/screen-dump.txt
  rg -v -N '^\s*$' /tmp/screen-dump.txt
  rip /tmp/screen-dump.txt
}

function prompt() {
  local context=""

  if ! [ -t 0 ]; then
    while IFS= read -r line; do
      context+="${line}"$'\n'
    done
    context=${context%$'\n'}
  fi

  if [[ -n "$context" ]]; then
    echo "<context>"
    echo -e "$context"
    echo "</context>"
    echo
  fi

  if (( $# > 0 )); then
    echo "<user_instructions>"
    printf "%s " "$@"
    echo
    echo "</user_instructions>"
  fi
}

function wtf() {
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

      if (( $# > 0 )); then
        echo "<user_instructions>"
        printf "%s " "$@"
        echo
        echo "</user_instructions>"
      fi
    )
    else
      my_logger "Not in Zellij session - skipping context building..."
      prompt=$(
      if [[ -n "$other_context" ]]; then
        echo "<other_context>"
        echo -e "$other_context"
        echo "</other_context>"
        echo
      fi

      if (( $# > 0 )); then
        echo "<user_instructions>"
        printf "%s " "$@"
        echo
        echo "</user_instructions>"
      fi
    )
  fi

  my_logger "Context constructed..."
  llm "$prompt" | uv run https://gist.githubusercontent.com/ipruning/ae517e5ca8eda986a090617d5ea717d9/raw/ae44c828cf25bccd7836e339c3c442ac31c73269/richify.py
  my_logger "Inference completed..."
}

function repo-fork-sync() {
  gh repo list --fork --visibility public --json owner,name | jq -r 'map(.owner.login + "/" + .name) | .[]' | xargs -t -L1 gh repo sync
}

function x86_64-zsh-login() {
  arch -x86_64 zsh --login
}

function x86_64-zsh-run() {
  arch -x86_64 zsh -c "$@"
}

function upgrade-all() {
  my_logger "Updating Homebrew..."
  brew update
  brew upgrade

  my_logger "Pruning Homebrew..."
  brew cleanup
  brew autoremove

  my_logger "Updating mise..."
  mise upgrade

  my_logger "Pruning mise..."
  mise prune
  mise reshim

  my_logger "Upgrading GitHub CLI extensions..."
  gh extension upgrade --all

  my_logger "Updating tldr pages..."
  tldr --update

  my_logger "Backing up all packages..."
  brew bundle dump --file="$HOME"/dotfiles/config/packages/Brewfile --force
  brew leaves >"$HOME"/dotfiles/config/packages/Brewfile.txt
  gh extension list | awk '{print $3}' >"$HOME"/dotfiles/config/packages/gh_extensions.txt
  find /Applications -maxdepth 1 -name "*.app" -exec basename {} .app \; | sort >"$HOME"/dotfiles/config/packages/macos_applications.txt
  find /Applications/Setapp -maxdepth 1 -name "*.app" -exec basename {} .app \; | sort >"$HOME"/dotfiles/config/packages/macos_setapp.txt
}
