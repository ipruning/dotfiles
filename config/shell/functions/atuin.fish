set -gx ATUIN_SESSION (atuin uuid)
set --erase ATUIN_HISTORY_ID

function _atuin_preexec --on-event fish_preexec
    if not test -n "$fish_private_mode"
        set -g ATUIN_HISTORY_ID (atuin history start -- "$argv[1]")
    end
end

function _atuin_postexec --on-event fish_postexec
    set -l s $status

    if test -n "$ATUIN_HISTORY_ID"
        ATUIN_LOG=error atuin history end --exit $s -- $ATUIN_HISTORY_ID &>/dev/null &
        disown
    end

    set --erase ATUIN_HISTORY_ID
end

function _atuin_search
    # Save current command
    set -l current_cmd (commandline)

    # Enter alternate screen buffer
    echo -ne "\033[?1049h"

    # Run Atuin
    set -l ATUIN_H (ATUIN_SHELL_FISH=t ATUIN_LOG=error ATUIN_QUERY=$current_cmd atuin search --keymap-mode=emacs $argv -i 3>&1 1>&2 2>&3 | string collect)

    # Return to main screen buffer
    echo -ne "\033[?1049l"

    # Process results
    if test -n "$ATUIN_H"
        if string match --quiet '__atuin_accept__:*' "$ATUIN_H"
            set -l ATUIN_HIST (string replace "__atuin_accept__:" "" -- "$ATUIN_H" | string collect)
            commandline -r "$ATUIN_HIST"
            commandline -f execute
        else
            commandline -r "$ATUIN_H"
        end
    else
        commandline -r "$current_cmd"
    end

    commandline -f repaint
end

function _atuin_bind_up
    # Fallback to fish's builtin up-or-search if we're in search or paging mode
    if commandline --search-mode; or commandline --paging-mode
        up-or-search
        return
    end

    # Only invoke atuin if we're on the top line of the command
    set -l lineno (commandline --line)

    switch $lineno
        case 1
            _atuin_search --shell-up-key-binding
        case '*'
            up-or-search
    end
end

bind \cr _atuin_search
if bind -M insert > /dev/null 2>&1
bind -M insert \cr _atuin_search
end
