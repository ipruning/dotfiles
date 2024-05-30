#===============================================================================
# 👇
#===============================================================================
llm() {
  ai "$@"
}

#===============================================================================
# 👇
#===============================================================================
catfiles() {
  for file in "$@"; do
    if [[ -r "$file" ]]; then
      echo "File Name: $(basename "$file")"
      echo "File Content:"
      cat "$file"
      echo ""
    else
      echo "Error: Cannot read $file" >&2
    fi
  done
}

#===============================================================================
# 👇
#===============================================================================
prompt() {
  local added_prompt=$(printf "%s " "$@")
  while IFS= read -r line; do
    echo "$line"
  done
  echo "$added_prompt"
}

#===============================================================================
# 👇 https://kadekillary.work/posts/1000x-eng/
# Examples of efficient data analysis using shell scripts
# hgpt "create a 10 row csv of NBA player data with headers - please only include the data, nothing else" > nba.csv
# dgpt "can you write a sql query to get the average PointsPerGame by Position from the following" "$(cat nba.csv)"
#===============================================================================
function hgpt {
  local prompt=$1

  ai "$prompt"
}
function dgpt() {
  local prompt=$1
  local data=$2
  local prompt=$(echo "${prompt}: ${data}" | tr -s ' ')

  ai "$prompt"
}
