function zj() {
  if ! command -v zellij >/dev/null 2>&1; then
    echo "zellij is not installed. please install it first."
    return 1
  fi

  if [[ "$ZELLIJ" == "0" ]]; then
    echo "Already in a zellij session. please exit first."
    return 1
  fi

  # get existing sessions
  local sessions=$(zellij list-sessions --no-formatting)

  # Different behavior based on number of existing sessions
  if [[ -n "$sessions" ]]; then
    # Count total number of sessions (including EXITED ones)
    local session_count=$(echo "$sessions" | grep -c "^")

    if [[ "$session_count" -eq 1 ]]; then
      # If only one session exists, attach directly
      local session=$(echo "$sessions" | awk '{print $1}')
      zellij attach "$session"
    else
      # Multiple sessions - show selection with all sessions
      local session=$(echo "$sessions" | awk '{
        session_name=$1; $1="";
        if ($0 ~ /EXITED/) print "\033[31m" session_name "\033[0m\t" $0;
        else print "\033[32m" session_name "\033[0m\t" $0;
      }' | column -t -s $'\t' | fzf --ansi --exit-0 --header="Select a session to attach (or press Esc to create new):" | awk '{print $1}')

      if [[ -n "$session" ]]; then
        zellij attach "$session"
      else
        zellij
      fi
    fi
  else
    # No existing sessions - Esc creates new
    local session=$(echo "" | fzf --ansi --print-query --header="Enter new session name (or press Esc for unnamed session):" | head -1)

    if [[ -n "$session" ]]; then
      zellij --session "$session"
    else
      zellij
    fi
  fi
}

function sroam() {
  if [ -z "$1" ]; then
    echo "Please provide a search string."
    return 1
  fi

  local token=$ROAM_RESEARCH_TOKEN
  local url=$ROAM_RESEARCH_ENDPOINT
  local query='[:find ?block-uid ?block-str :in $ ?search-string :where [?b :block/uid ?block-uid] [?b :block/string ?block-str] [(clojure.string/includes? ?block-str ?search-string)]]'

  http POST "$url" \
    accept:application/json \
    "X-Authorization:Bearer $token" \
    Content-Type:application/json \
    query="$query" \
    args:="[\"$1\"]" | jq -r '.result[] | .[1]'
}

function sproxy() {
  export https_proxy=http://127.0.0.1:6152
  export http_proxy=http://127.0.0.1:6152
  export all_proxy=socks5://127.0.0.1:6153
}
function uproxy() {
  unset https_proxy http_proxy all_proxy
}

functiongh-sync-fork() {
  gh repo list --fork --visibility public --json owner,name | jq -r 'map(.owner.login + "/" + .name) | .[]' | xargs -t -L1 gh repo sync
}

function r-fava() {
  fava ${HOME}/Databases/Ledger/main.bean -p 4000
}

function r-completion() {
  echo -e "\033[33mGenerating completions...\033[0m"
  rm -f ~/.zcompdump
  compinit
}

function r-update() {
  echo -e "\033[33mUpdating Homebrew...\033[0m"
  brew update

  echo -e "\033[33mUpdating tldr pages...\033[0m"
  tldr --update
}

function r-upgrade() {
  echo -e "\033[33mUpgrading Homebrew formulas...\033[0m"
  brew upgrade

  echo -e "\033[33mCleaning up Homebrew...\033[0m"
  brew cleanup && brew autoremove

  echo -e "\033[33mUpgrading GitHub CLI extensions...\033[0m"
  gh extension upgrade --all

  echo -e "\033[33mUpdating mise...\033[0m"
  mise upgrade --bump

  echo -e "\033[33mUpdating rust...\033[0m"
  rustup update && rustup self update
}

function r-backup() {
  echo -e "\033[33mBacking up all packages...\033[0m"
  brew bundle dump --file="$HOME"/dotfiles/config/packages/Brewfile --force
  brew leaves >"$HOME"/dotfiles/config/packages/Brewfile.txt
  brew update
  cp "$HOME"/.zsh_history "$HOME"/Databases/Backup/CLI/zsh_history_$(date +\%Y_\%m_\%d_\%H_\%M_\%S).bak
  gh extension list | awk '{print $3}' >"$HOME"/dotfiles/config/packages/gh_extensions.txt
  ls /Applications | rg '\.app' | sed 's/\.app//g' >"$HOME"/dotfiles/config/packages/macos_applications.txt
  ls /Applications/Setapp | rg '\.app' | sed 's/\.app//g' >"$HOME"/dotfiles/config/packages/macos_setapp.txt
}

function rgist() {
  local filename="$1"
  local command="${2:-uv}"  # Default to 'uv'
  local command_args="${3:-run}"
  local cachedir="${XDG_CACHE_HOME:-$HOME/.cache}/rgist"
  local cachefile
  local raw_url
  local gist_id

  if [[ -z "$filename" ]]; then
    echo "Usage: rgist <filename> [command] [command_args]"
    echo "  command: The command to execute the downloaded file. Default is 'uv'."
    echo "  command_args: The arguments for the command. Default is 'run'."
    return 1
  fi

  # Extract gist_id from latest gist for caching purposes
  gist_id=$(gh api \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    /gists | jq -r ".[0].id")

  if [[ -z "$gist_id" ]]; then
    echo "Error: Could not retrieve latest gist ID."
    return 1
  fi

  # Set up caching filename based on gist id and the filename provided by the user
  mkdir -p "$cachedir"
  cachefile="$cachedir/${gist_id}_$(echo "$filename" | sed 's/[^a-zA-Z0-9_.]/_/g')"


  # Check for cached file and avoid re-downloading if possible
  if [[ -f "$cachefile" ]]; then
    if [[ "$command" == "uv" ]] && [[ "$command_args" == "run" ]]; then
        if [[ -n "$(find "$cachefile" -mmin +1440)" ]]; then
        echo "Cache expired. Re-downloading file."
      else
          echo "Using cached version of '$filename'."
          "$command" "$command_args" "$cachefile"
          return 0
      fi
    else
         echo "Using cached version of '$filename'."
          if ! command -v "$command" &> /dev/null; then
              echo "Error: Command '$command' not found in PATH."
            return 1
           fi
       "$command" "$command_args" "$cachefile"
       return 0
    fi
  fi

  # Get the raw URL for the filename
  raw_url=$(gh api \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    /gists | jq -r ".[] | .files | to_entries[] | select(.key == \"$filename\") | .value.raw_url" | head -n 1)

  if [[ -z "$raw_url" ]]; then
    echo "Error: Gist file '$filename' not found."
    return 1
  fi

  echo "Downloading '$filename' from Gist..."

  # Download and cache the file
  curl -sL "$raw_url" -o "$cachefile"

  if ! command -v "$command" &> /dev/null; then
     echo "Error: Command '$command' not found in PATH."
    return 1
  fi

  "$command" "$command_args" "$cachefile"
}

function randomid() {
  random_number() {
    echo $((100000 + RANDOM % 900000))
  }

  # Generate ID
  generate_id() {
    local prefix=$1  # Get prefix
    local random_num=$(random_number) # Get random number
    echo "${prefix}${random_num}"
  }

  # Get prefix (use default "id" if not provided)
  local prefix="${1:-id}"

  # Generate and print ID
  generate_id "$prefix"
}
