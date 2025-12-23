# Atuin integration for Nushell
# Migrated from custom zsh version with alternate screen support
# Minimum supported version: 0.93.0

$env.ATUIN_SESSION = (atuin uuid | str replace -a "-" "")
hide-env -i ATUIN_HISTORY_ID

# Magic token to make sure we don't record commands run by keybindings
let ATUIN_KEYBINDING_TOKEN = $"# (random uuid)"

# === Hooks ===
let _atuin_pre_execution = {||
    if ($nu | get history-enabled?) == false { return }
    let cmd = (commandline)
    if ($cmd | is-empty) { return }
    if not ($cmd | str starts-with $ATUIN_KEYBINDING_TOKEN) {
        $env.ATUIN_HISTORY_ID = (atuin history start -- $cmd)
    }
}

let _atuin_pre_prompt = {||
    let last_exit = $env.LAST_EXIT_CODE
    if 'ATUIN_HISTORY_ID' not-in $env { return }
    with-env { ATUIN_LOG: error } {
        atuin history end $'--exit=($last_exit)' -- $env.ATUIN_HISTORY_ID | complete
    }
    hide-env ATUIN_HISTORY_ID
}

# === Custom search command with alternate screen ===
def _atuin_search_cmd [...flags: string] {
    # `commandline edit --accept` was added in Nu 0.107.0
    let supports_accept = (version).major > 0 or (version).minor >= 107

    let env_kvs = if $supports_accept {
        'ATUIN_LOG: error, ATUIN_QUERY: $current_cmd, ATUIN_SHELL: nu'
    } else {
        # Older Nu: don't set ATUIN_SHELL=nu (mirrors atuin's official behavior)
        'ATUIN_LOG: error, ATUIN_QUERY: $current_cmd'
    }

    let accept_line = if $supports_accept {
        'commandline edit --accept ($output | str replace "__atuin_accept__:" "")'
    } else {
        # Fallback: insert only (strip prefix), user presses Enter manually
        'commandline edit ($output | str replace "__atuin_accept__:" "")'
    }

    [
        $ATUIN_KEYBINDING_TOKEN,
        ([
            'let current_cmd = (commandline)',
            'let current_cursor = (commandline get-cursor)',

            # Optional: snapshot tty settings; if stty is unavailable, this becomes ""
            'let tty_state = (do --ignore-errors { ^stty -g } | default "" | str trim)',

            # Enter alternate screen
            'print -n (ansi -e "?1049h")',

            # Critical: ignore non-zero exit codes so cleanup always runs (Esc/Ctrl-C, etc.)
            ([
                'let output = (do --ignore-errors {',
                $'with-env { ($env_kvs) } {',
                ([
                    'run-external atuin search',
                    ($flags | append [--interactive] | each {|e| $'"($e)"'}),
                    'e>| str trim',
                ] | flatten | str join ' '),
                '}',
                '} | default "" )',
            ] | str join "\n"),

            # Leave alternate screen
            'print -n (ansi -e "?1049l")',

            # Restore tty settings if captured
            'if not ($tty_state | is-empty) { do --ignore-errors { ^stty $tty_state } | ignore }',

            # Defensive terminal mode reset:
            # - kitty keyboard protocol: restore normal mode (CSI < u)
            # - bracketed paste: ensure enabled (CSI ? 2004 h)
            'print -n (ansi -e "<u")',
            'print -n (ansi -e "?2004h")',

            # Restore commandline state
            'if ($output | is-empty) {',
            '  commandline edit $current_cmd',
            '  commandline set-cursor $current_cursor',
            '} else if ($output | str starts-with "__atuin_accept__:") {',
            $accept_line,
            '} else {',
            '  commandline edit $output',
            '}',
        ] | flatten | str join "\n"),
    ] | str join "\n"
}

# === Register hooks ===
$env.config = ($env | default {} config).config
$env.config = ($env.config | default {} hooks)
$env.config = (
    $env.config | upsert hooks (
        $env.config.hooks
        | upsert pre_execution ($env.config.hooks | get pre_execution? | default [] | append $_atuin_pre_execution)
        | upsert pre_prompt ($env.config.hooks | get pre_prompt? | default [] | append $_atuin_pre_prompt)
    )
)

# === Keybindings (Ctrl+R only, no up arrow) ===
$env.config = ($env.config | default [] keybindings)
$env.config = (
    $env.config | upsert keybindings (
        $env.config.keybindings
        | append {
            name: atuin
            modifier: control
            keycode: char_r
            mode: [emacs, vi_normal, vi_insert]
            event: { send: executehostcommand cmd: (_atuin_search_cmd) }
        }
    )
)
