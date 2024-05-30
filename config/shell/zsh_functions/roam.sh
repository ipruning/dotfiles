#===============================================================================
# 👇
#===============================================================================
rr() {
  if [ -z "$1" ]; then
    echo "Please provide a search string."
    return 1
  fi

  local token=$ROAM_RESEARCH_TOKEN
  local url=$ROAM_RESEARCH_ENDPOINT
  local query='[:find ?block-uid ?block-str :in $ ?search-string :where [?b :block/uid ?block-uid] [?b :block/string ?block-str] [(clojure.string/includes? ?block-str ?search-string)]]'

  local result=$(curl -s -X POST "$url" \
    -H "accept: application/json" \
    -H "X-Authorization: Bearer $token" \
    -H "Content-Type: application/json" \
    --data-binary '{"query":"'"$query"'","args":["'"$1"'"]}')
  echo "$result" | jq '.result[] | .[1]'
}
