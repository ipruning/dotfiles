#===============================================================================
# 👇 Building
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

buffit() {
  # Check if data is being piped or redirected to the function
  if [ -t 0 ]; then # Checks if the standard input (file descriptor 0) is a terminal
    # If no data is piped, check if my_buff is already set and print it if it is
    if [ -n "$my_buff" ]; then
      echo "$my_buff"
    else
      echo "No data piped and my_buff is empty."
    fi
  else
    # Capture the input from standard in to my_buff
    export my_buff=$(cat)
  fi
}

prompt() {
  # Check if stdin is a terminal (interactive)
  if [ -t 0 ]; then
    local input=""
  else
    local input=$(cat)
  fi

  local added_prompt=$(printf "%s " "$@")

  # If no input, just print the prompt
  if [[ -z "$input" ]]; then
    echo "$added_prompt"
  # If input, print the prompt and the input
  else
    echo "<context>"
    echo "$input"
    echo "</context>"
    echo ""
    echo "<prompt>"
    echo "$added_prompt"
    echo "</prompt>"
  fi
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
