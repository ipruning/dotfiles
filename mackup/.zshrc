BOOTSTRAP_FILE="$HOME/dotfiles/config/shell/bootstrap.zsh"

if [[ -f "$BOOTSTRAP_FILE" ]]; then
  source "$BOOTSTRAP_FILE"
else
  echo "Warning: $BOOTSTRAP_FILE not found."
fi
