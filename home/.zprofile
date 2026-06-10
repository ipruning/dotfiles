# .zprofile is login-shell only. Do not duplicate the PATH list here: `.zshenv`
# owns it so non-login shells used by agents and scripts get the same baseline.
# macOS may run /etc/zprofile/path_helper after `.zshenv`, so re-assert the
# shared ordering for login shells if the helper function is available.
(( $+functions[_dotfiles_core_path] )) && _dotfiles_core_path

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
