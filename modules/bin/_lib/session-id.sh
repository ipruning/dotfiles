# shellcheck shell=bash
# Helpers for deriving stable per-directory session IDs.
# Source from sibling scripts in modules/bin/.

session_id_sanitize() {
  printf '%s' "$1" | tr -cs '[:alnum:]' '_' | sed 's/^_//; s/_$//'
}

session_id_short_hash() {
  if ! command -v git >/dev/null 2>&1; then
    printf '%s\n' 'session-id: git is required to derive a stable session ID' >&2
    return 127
  fi
  printf '%s' "$1" | git hash-object --stdin | cut -c1-8
}

# Derive "<basename>-<hash>" session id from an absolute path.
session_id_for_dir() {
  local dir="$1"
  local base hash
  base="$(session_id_sanitize "$(basename "$dir")")"
  hash="$(session_id_short_hash "$dir")"
  printf '%s-%s' "$base" "$hash"
}
