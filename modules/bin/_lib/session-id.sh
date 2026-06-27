# shellcheck shell=bash
# Helpers for deriving stable per-directory session IDs.
# Source from sibling scripts in modules/bin/.

session_id_sanitize() {
  printf '%s' "$1" | tr -cs '[:alnum:]' '_' | sed 's/^_//; s/_$//'
}

session_id_short_hash() {
  if command -v shasum >/dev/null 2>&1; then
    printf '%s' "$1" | shasum -a 256 | awk '{print substr($1,1,8)}'
  elif command -v sha256sum >/dev/null 2>&1; then
    printf '%s' "$1" | sha256sum | awk '{print substr($1,1,8)}'
  elif command -v md5 >/dev/null 2>&1; then
    printf '%s' "$1" | md5 -q | cut -c1-8
  elif command -v md5sum >/dev/null 2>&1; then
    printf '%s' "$1" | md5sum | awk '{print substr($1,1,8)}'
  else
    date +%s
  fi
}

# Derive "<basename>-<hash>" session id from an absolute path.
session_id_for_dir() {
  local dir="$1"
  local base hash
  base="$(session_id_sanitize "$(basename "$dir")")"
  hash="$(session_id_short_hash "$dir")"
  printf '%s-%s' "$base" "$hash"
}
