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
