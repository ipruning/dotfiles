# 👇 zellij
#===============================================================================
function zj() {
  # Check if zellij is installed
  if ! command -v zellij >/dev/null 2>&1; then
    echo "Zellij is not installed. Please install it first."
    return 1
  fi

  # If session name is provided as argument, use it directly
  if [[ $# -eq 1 ]]; then
    zellij attach "$1" 2>/dev/null || zellij --session "$1"
    return
  fi

  # List and format existing sessions
  local session=$(zellij list-sessions --no-formatting | awk '{
    session_name=$1; $1="";
    if ($0 ~ /EXITED/) print "\033[31m" session_name "\033[0m\t" $0;
    else print "\033[32m" session_name "\033[0m\t" $0;
  }' | column -t -s $'\t' | fzf --ansi --exit-0 --header="Select a session to attach (or press Esc to create new):" | awk '{print $1}')

  # If no session is selected or no sessions exist, create a new one
  if [[ -z "$session" ]]; then
    zellij
  else
    zellij attach "$session"
  fi
}
# 如果 "$ZELLIJ" 是 0 就代表已经在仓库里了

#===============================================================================
# 👇 Roam Research
#===============================================================================
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

#===============================================================================
# 👇 Proxy Configuration
#===============================================================================
function set_proxy() {
  export https_proxy=http://127.0.0.1:6152
  export http_proxy=http://127.0.0.1:6152
  export all_proxy=socks5://127.0.0.1:6153
}
function nunset_proxy() {
  unset https_proxy http_proxy all_proxy
}

#===============================================================================
# 👇 gh-sync-fork
#===============================================================================
functiongh-sync-fork() {
  gh repo list --fork --visibility public --json owner,name | jq -r 'map(.owner.login + "/" + .name) | .[]' | xargs -t -L1 gh repo sync
}

#===============================================================================
# 👇 fava
#===============================================================================
function r-fava() {
  fava ${HOME}/Databases/Ledger/main.bean -p 4000
}

#===============================================================================
# 👇 upgrade / backup
#===============================================================================
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
  mise upgrade

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
