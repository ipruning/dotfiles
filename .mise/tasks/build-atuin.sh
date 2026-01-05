#!/usr/bin/env bash
#MISE description="Build and copy atuin binary"

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/_lib.sh"

REPO_DIR="$HOME/Developer/ipruning/atuin"

require_cmd cargo
[[ -d "$REPO_DIR" ]] || die "repo dir not found: $REPO_DIR"

DOTFILES_DIR="$(repo_root)"
DEST_DIR="$DOTFILES_DIR/generated/bin"

mkdir -p "$DEST_DIR"

pushd "$REPO_DIR" >/dev/null
cargo build --release -p atuin
popd >/dev/null

BIN_SRC="$REPO_DIR/target/release/atuin"
[[ -x "$BIN_SRC" ]] || die "built binary not found/executable: $BIN_SRC"

install -m 0755 "$BIN_SRC" "$DEST_DIR/atuin"
