#===============================================================================
# 👇 fzf Chrome 历史记录
#===============================================================================
fch() {
  local cols sep google_history open
  cols=$((COLUMNS / 3))
  sep='{::}'

  if [ "$(uname)" = "Darwin" ]; then
    google_history="$HOME/Library/Application Support/Google/Chrome/Default/History"
    open=open
  else
    google_history="$HOME/.config/google-chrome/Default/History"
    open=xdg-open
  fi
  cp -f "$google_history" /tmp/h
  sqlite3 -separator $sep /tmp/h \
    "select substr(title, 1, $cols), url
    from urls order by last_visit_time desc" |
    awk -F $sep '{printf "%-'$cols's  \x1b[36m%s\x1b[m\n", $1, $2}' |
    fzf --ansi --multi | sed 's#.*\(https*://\)#\1#' | xargs $open >/dev/null 2>/dev/null
}

#===============================================================================
# 👇 fzf Chrome 书签
#===============================================================================
fcb() {
  bookmarks_path=~/Library/Application\ Support/Google/Chrome/Default/Bookmarks
  jq_script='
        def ancestors: while(. | length >= 2; del(.[-1,-2]));
        . as $in | paths(.url?) as $key | $in | getpath($key) | {name,url, path: [$key[0:-2] | ancestors as $a | $in | getpath($a) | .name?] | reverse | join("/") } | .path + "/" + .name + "\t" + .url'
  jq -r "$jq_script" <"$bookmarks_path" |
    sed -E $'s/(.*)\t(.*)/\\1\t\x1b[36m\\2\x1b[m/g' |
    fzf --ansi |
    cut -d$'\t' -f2 |
    xargs open
}

#===============================================================================
# 👇 fzf 杀进程
#===============================================================================
fkill() {
  (
    date
    ps -ef
  ) |
    fzf --bind='ctrl-r:reload(date; ps -ef)' \
      --header=$'Press CTRL-R to reload\n\n' --header-lines=2 \
      --preview='echo {}' --preview-window=down,3,wrap \
      --layout=reverse --height=80% | awk '{print $2}' | xargs kill -9
}

#===============================================================================
# 👇 zellij
#===============================================================================
zj() {
  local session=""

  if [[ $# -eq 1 ]]; then
    session="$1"
  else
    session=$(zellij list-sessions --no-formatting | awk '{
          session_name=$1; $1="";
          if ($0 ~ /EXITED/) print "\033[31m" session_name "\033[0m\t" $0;
          else print "\033[32m" session_name "\033[0m\t" $0;
      }' | column -t -s $'\t' | fzf --ansi --exit-0 --header="Select a session to attach (or press Esc to create new):" | awk '{print $1}')
  fi

  if [[ -n "$session" ]]; then
    zellij attach "$session"
  else
    echo "No session selected"
  fi
}

# _zj_completion() {
#   local sessions
#   sessions=($(zellij list-sessions --no-formatting | awk '{print $1}'))
#   _describe 'sessions' sessions
# }

# compdef _zj_completion zj

#===============================================================================
# 👇 cd
#===============================================================================
cd() {
  if [[ "$#" != 0 ]]; then
    builtin cd "$@"
    return
  fi
  while true; do
    local ls=$(echo ".." && ls -p | grep '/$' | sed 's;/$;;')
    local dir="$(printf '%s\n' "${ls[@]}" |
      fzf --reverse --preview '
                __cd_nxt="$(echo {})";
                __cd_path="$(echo $(pwd)/${__cd_nxt} | sed "s;//;/;")";
                echo $__cd_path;
                echo;
                eza --icons --oneline --color=always --ignore-glob=".DS_Store" "${__cd_path}";
        ')"
    [[ ${#dir} != 0 ]] || return 0
    builtin cd "$dir" &>/dev/null
  done
}

#===============================================================================
# 👇 rip-venv
#===============================================================================
rip-venv() {
  # Ensure a directory path is provided
  if [[ -z "$1" ]]; then
    echo "Error: No directory path provided. Please specify a path."
    return 1
  elif [[ ! -d "$1" ]]; then
    echo "Error: The provided path is not a directory or does not exist."
    return 1
  fi

  # Use fd to find .venv directories and store the results
  local venv_dirs
  venv_dirs=$(fd --type d --hidden --no-ignore ".venv" "$1" 2>/dev/null)

  # Check if fd is not installed
  if ! command -v fd &>/dev/null; then
    echo "Error: 'fd' command is not installed. Please install fd to use this function."
    return 1
  fi

  # Inform if no .venv directories are found
  if [[ -z "$venv_dirs" ]]; then
    echo "No .venv directories found."
    return 0
  fi

  # Process each directory path
  echo "Found .venv directories:"
  echo "$venv_dirs"
  echo "Proceed with deletion? [y/N]"
  IFS= read -r proceed </dev/tty
  if [[ $proceed =~ ^[Yy]$ ]]; then
    echo "$venv_dirs" | while IFS= read -r line; do
      echo "Deleting $line..."
      rip "$line"
      echo "Deleted: $line"
    done
  else
    echo "Deletion canceled."
  fi
}
