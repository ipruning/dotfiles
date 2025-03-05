function logger() {
  local RED='\033[0;31m'
  local YELLOW='\033[1;33m'
  local GRAY='\033[0;90m'
  local NC='\033[0m'

  local message=$1
  local loglevel=${2:-"INFO"}
  local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  local color=$GRAY

  case "${loglevel:u}" in
  "ERROR")
    color=$RED
    ;;
  "WARN")
    color=$YELLOW
    ;;
  "INFO")
    if [ "$DRY_RUN" = true ]; then
      color=$YELLOW
    else
      color=$GRAY
    fi
    ;;
  *)
    loglevel="INFO"
    color=$GRAY
    ;;
  esac

  printf "${color}[%s] [%s] %s${NC}\n" "$timestamp" "${loglevel:u}" "$message"
}
