function my_logger() {
  local RED='\033[0;31m'
  local YELLOW='\033[1;33m'
  local GRAY='\033[0;90m'
  local NC='\033[0m'
  
  local message=$1
  local is_error=${2:-false}
    
  if [ "$is_error" = true ]; then
    printf "${RED}[ERROR] %s${NC}\n" "$message" >&2
  elif [ "$DRY_RUN" = true ]; then
    printf "${YELLOW}[INFO] [DRY-RUN] %s${NC}\n" "$message"
  else
    printf "${GRAY}[INFO] %s${NC}\n" "$message"
  fi
}

function readit() {
  if [ $# -eq 0 ]; then
    my_logger "No URL provided" "true"
  fi

  url="$1"

  if [[ ! "$url" =~ ^[a-zA-Z0-9._/:%-]+$ ]]; then
    my_logger "Invalid URL format" "true"
    exit 1
  fi

  if ! curl -fSL "https://r.jina.ai/$url" 2>/dev/null; then
    my_logger "Failed to fetch https://r.jina.ai/$url" "true"
    exit 1
  fi
}

function buffit() {
  if [ -t 0 ]; then
    if [ -n "$my_buff" ]; then
      echo "$my_buff"
    else
      my_logger "No data piped and 'my_buff' is empty." "true"
    fi
  else
    read -r -d '' my_buff
    my_logger "Buffer updated."
  fi
}

function prompt() {
  local other_context=""
  local user_instructions=$(printf "%s " "$@")

  if ! [ -t 0 ]; then
    while IFS= read -r line; do
      other_context+="${line}"$'\n'
    done
    other_context=${other_context%$'\n'}
  fi

  if [[ -z "$other_context" ]]; then
    echo "$user_instructions"
  else
    echo "<context>"
    echo -e "$other_context"
    echo "</context>"
    echo
    echo "<user_instructions>"
    echo "$user_instructions"
    echo "</user_instructions>"
  fi
}

function catscreen() {
  if [[ -z "$ZELLIJ" ]]; then
    my_logger "Not running inside a Zellij session." "true"
    return 1
  fi

  zellij action dump-screen /tmp/screen-dump.txt
  cat /tmp/screen-dump.txt
  rip /tmp/screen-dump.txt
}

function wtf() {
  local terminal_context=""
  local other_context=""
  local user_instructions=$(printf "%s " "$@")

  if [[ -n "$ZELLIJ" ]]; then
    terminal_context=$(catscreen | sed '/^.*>.*wtf/,$d')
  else
    my_logger "Not running inside a Zellij session." "true"
    return 1
  fi

  if ! [ -t 0 ]; then
    while IFS= read -r line; do
      other_context+="${line}"$'\n'
    done
    other_context=${other_context%$'\n'}
  fi

  local prompt=$(
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

    echo "<user_instructions>"
    echo "$user_instructions"
    echo "</user_instructions>"
  )
  
  echo "$prompt"
  echo
  llm $prompt | uv run https://gist.githubusercontent.com/ipruning/ae517e5ca8eda986a090617d5ea717d9/raw/ae44c828cf25bccd7836e339c3c442ac31c73269/richify.py
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

# 👇 session utils
# https://github.com/zellij-org/zellij/issues/2744
# https://github.com/zellij-org/zellij/issues/3081#issuecomment-1904349853
function jump_to_repo() {
  local repo_path

  repo_path=$(tv git-repos)
  [[ -z "$repo_path" ]] && return
  cd "${repo_path}"

  local repo_name=$(basename "${repo_path}")
}

function jump_to_repo_with_zellij_session() {
  if [[ -n "$ZELLIJ" ]]; then
  else
    local repo_path
    repo_path=$(tv git-repos)
    [[ -z "$repo_path" ]] && return
    cd "${repo_path}"
    local repo_name=$(basename "${repo_path}")
    zellij attach "${repo_name}" 2>/dev/null || zellij --session "${repo_name}"
  fi
}

function jump_to_zellij_session() {
  if [[ -n "$ZELLIJ" ]]; then
  else
    if [[ "$TERM_PROGRAM" == "ghostty" ]]; then
      zj_sessions=$(zellij list-sessions --no-formatting --short)
      case $(echo "$zj_sessions" | grep -c '^.') in
        0)
          zellij
          ;;
        1)
          zellij attach "$zj_sessions"
          ;;
        *)
          selected_session=$(echo "$zj_sessions" | tv --no-preview) &&
          [[ -n "$selected_session" ]] && zellij attach "$selected_session"
          ;;
      esac
    fi
  fi
}
