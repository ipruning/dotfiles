# echo ">>> .zprofile is loaded. Shell: $SHELL, Options: $-"

typeset -U path

if [[ $OSTYPE == darwin* ]]; then
  if [[ "$TERM_PROGRAM" == "ghostty" ]]; then
    # if [[ -z "$ZELLIJ" ]]; then
    #   latest_session=$(/opt/homebrew/bin/zellij list-sessions --no-formatting --short | grep -v "^repo-" | head -n 1)
    #   if [[ -n "$latest_session" ]]; then
    #     /opt/homebrew/bin/zellij attach --create "$latest_session"
    #   else
    #     /opt/homebrew/bin/zellij
    #   fi
    # fi
  fi
fi

if [[ $OSTYPE == linux* ]]; then
  typeset -U path
fi
