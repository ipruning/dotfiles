#===============================================================================
# 👇 fzf Chrome 历史记录
#===============================================================================
# fch() {
#   local cols sep google_history open
#   cols=$((COLUMNS / 3))
#   sep='{::}'

#   if [ "$(uname)" = "Darwin" ]; then
#     google_history="$HOME/Library/Application Support/Google/Chrome/Default/History"
#     open=open
#   else
#     google_history="$HOME/.config/google-chrome/Default/History"
#     open=xdg-open
#   fi
#   cp -f "$google_history" /tmp/h
#   sqlite3 -separator $sep /tmp/h \
#     "select substr(title, 1, $cols), url
#     from urls order by last_visit_time desc" |
#     awk -F $sep '{printf "%-'$cols's  \x1b[36m%s\x1b[m\n", $1, $2}' |
#     fzf --ansi --multi | sed 's#.*\(https*://\)#\1#' | xargs $open >/dev/null 2>/dev/null
# }

#===============================================================================
# 👇 fzf Chrome 书签
#===============================================================================
# fcb() {
#   bookmarks_path=~/Library/Application\ Support/Google/Chrome/Default/Bookmarks
#   jq_script='
#         def ancestors: while(. | length >= 2; del(.[-1,-2]));
#         . as $in | paths(.url?) as $key | $in | getpath($key) | {name,url, path: [$key[0:-2] | ancestors as $a | $in | getpath($a) | .name?] | reverse | join("/") } | .path + "/" + .name + "\t" + .url'
#   jq -r "$jq_script" <"$bookmarks_path" |
#     sed -E $'s/(.*)\t(.*)/\\1\t\x1b[36m\\2\x1b[m/g' |
#     fzf --ansi |
#     cut -d$'\t' -f2 |
#     xargs open
# }

#===============================================================================
# 👇 fzf 杀进程
#===============================================================================
# fkill() {
#   (
#     date
#     ps -ef
#   ) |
#     fzf --bind='ctrl-r:reload(date; ps -ef)' \
#       --header=$'Press CTRL-R to reload\n\n' --header-lines=2 \
#       --preview='echo {}' --preview-window=down,3,wrap \
#       --layout=reverse --height=80% | awk '{print $2}' | xargs kill -9
# }

#===============================================================================
# 👇 zellij
#===============================================================================
# zj() {
#   local session=""

#   if [[ $# -eq 1 ]]; then
#     session="$1"
#   else
#     session=$(zellij list-sessions --no-formatting | awk '{
#           session_name=$1; $1="";
#           if ($0 ~ /EXITED/) print "\033[31m" session_name "\033[0m\t" $0;
#           else print "\033[32m" session_name "\033[0m\t" $0;
#       }' | column -t -s $'\t' | fzf --ansi --exit-0 --header="Select a session to attach (or press Esc to create new):" | awk '{print $1}')
#   fi

#   if [[ -n "$session" ]]; then
#     zellij attach "$session"
#   else
#     echo "No session selected"
#   fi
# }

#===============================================================================
# 👇 cd
#===============================================================================
# cd() {
#   if [[ "$#" != 0 ]]; then
#     builtin cd "$@"
#     return
#   fi
#   while true; do
#     local ls=$(echo ".." && ls -p | grep '/$' | sed 's;/$;;')
#     local dir="$(printf '%s\n' "${ls[@]}" |
#       fzf --reverse --preview '
#                 __cd_nxt="$(echo {})";
#                 __cd_path="$(echo $(pwd)/${__cd_nxt} | sed "s;//;/;")";
#                 echo $__cd_path;
#                 echo;
#                 eza --icons --oneline --color=always --ignore-glob=".DS_Store" "${__cd_path}";
#         ')"
#     [[ ${#dir} != 0 ]] || return 0
#     builtin cd "$dir" &>/dev/null
#   done
# }

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
