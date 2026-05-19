typeset -U path

# Make mise shims available to login/app-launched shells before .zshrc runs.
# Keep this static so it works even before Homebrew's mise is on PATH.
if [[ ${OSTYPE:-} == darwin* ]]; then
  [[ -d /usr/local/bin ]] && path=(/usr/local/bin $path)
  [[ -d /opt/homebrew/bin ]] && path=(/opt/homebrew/bin $path)
fi

[[ -d "$HOME/.local/share/mise/shims" ]] && path=("$HOME/.local/share/mise/shims" $path)
export PATH

# if [[ $OSTYPE == darwin* ]]; then
#   if [[ "$TERM_PROGRAM" == "ghostty" ]]; then
#     if [[ -z "$ZELLIJ" ]]; then
#       latest_session=$(/opt/homebrew/bin/zellij list-sessions --no-formatting --short | grep -v "^repo-" | head -n 1)
#       if [[ -n "$latest_session" ]]; then
#         /opt/homebrew/bin/zellij attach --create "$latest_session"
#       else
#         /opt/homebrew/bin/zellij
#       fi
#     fi
#   fi
# fi
