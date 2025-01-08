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
  gh extension list | awk '{print $3}' >"$HOME"/dotfiles/config/packages/gh_extensions.txt
  find /Applications -maxdepth 1 -name "*.app" -exec basename {} .app \; | sort >"$HOME"/dotfiles/config/packages/macos_applications.txt
  find /Applications/Setapp -maxdepth 1 -name "*.app" -exec basename {} .app \; | sort >"$HOME"/dotfiles/config/packages/macos_setapp.txt
}

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
      zellij attach "${session}"
    else
      # Multiple sessions - show selection with all sessions
      local session=$(echo "$sessions" | awk '{
        session_name=$1; $1="";
        if ($0 ~ /EXITED/) print "\033[31m" session_name "\033[0m\t" $0;
        else print "\033[32m" session_name "\033[0m\t" $0;
      }' | column -t -s $'\t' | fzf --ansi --exit-0 --header="Select a session to attach (or press Esc to create new):" | awk '{print $1}')

      if [[ -n "$session" ]]; then
        zellij attach "${session}"
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

function sfork() {
  gh repo list --fork --visibility public --json owner,name | jq -r 'map(.owner.login + "/" + .name) | .[]' | xargs -t -L1 gh repo sync
}

function ggist() {
  local filename="$1"

  if [[ -z "$filename" ]]; then
    echo "Usage: getgist <filename>"
    return 1
  fi

  local raw_url=$(gh api \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    /gists | jq -r ".[] | .files | to_entries[] | select(.key == \"$filename\") | .value.raw_url" | head -n 1)

  if [[ -z "$raw_url" ]]; then
    echo "Error: Gist file '$filename' not found."
    return 1
  fi

  echo "$raw_url"
}

function grandomid() {
  random_number() {
    echo $((100000 + RANDOM % 900000))
  }

  generate_id() {
    local prefix=$1
    local random_num=$(random_number)
    echo "${prefix}${random_num}"
  }

  local prefix="${1:-id}"

  generate_id "$prefix"
}
