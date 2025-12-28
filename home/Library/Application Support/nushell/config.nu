# 👇 Path
use std/util "path add"

# 👇 Homebrew Path
if ("/opt/homebrew/bin" | path exists) {
  path add "/opt/homebrew/bin"
}

# 👇 Mise
let autoload_dir = ($nu.default-config-dir | path join "vendor/autoload")
let mise_autoload = ($autoload_dir | path join "mise.nu")

if not (which mise | is-empty) {
  mkdir $autoload_dir
  ^mise activate nu | save -f $mise_autoload
}

# 👇 Zoxide
source ~/.zoxide.nu

# 👇 Starship
# $env.STARSHIP_CONFIG = ($nu.home-path | path join ".config/starship.toml")
# $env.STARSHIP_SHELL = "nu"
# mkdir ($nu.data-dir | path join "vendor/autoload")
# starship init nu | save -f ($nu.data-dir | path join "vendor/autoload/starship.nu")

# 👇 Completions
# let carapace_completer = {|spans: list<string>|
#   carapace $spans.0 nushell ...$spans | from json
# }

# $env.config.completions.external = {
#   enable: true
#   max_results: 100
#   completer: $carapace_completer
# }

# 👇 Television
# def tv_smart_autocomplete [] {
#     let line = (commandline)
#     let cursor = (commandline get-cursor)
#     let lhs = ($line | str substring 0..$cursor)
#     let rhs = ($line | str substring $cursor..)
#     let output = (tv --inline --autocomplete-prompt $lhs | str trim)

#     if ($output | str length) > 0 {
#         let needs_space = not ($lhs | str ends-with " ")
#         let lhs_with_space = if $needs_space { $"($lhs) " } else { $lhs }
#         let new_line = $lhs_with_space + $output + $rhs
#         let new_cursor = ($lhs_with_space + $output | str length)
#         commandline edit --replace $new_line
#         commandline set-cursor $new_cursor
#     }
# }

# $env.config = (
#   $env.config
#   | upsert keybindings (
#       $env.config.keybindings
#       | append [
#           {
#               name: tv_completion,
#               modifier: Control,
#               keycode: char_t,
#               mode: [vi_normal, vi_insert, emacs],
#               event: {
#                   send: executehostcommand,
#                   cmd: "tv_smart_autocomplete"
#               }
#           }
#       ]
#   )
# )

# 👇 Table Mode
# $env.config.table.mode = 'markdown'
# $env.config.table.mode = 'psql'

# 👇 Editor
# $env.config.buffer_editor = ["/opt/homebrew/bin/zed", "--wait"]
# $env.config.buffer_editor = "hx"

# 👇 Edit Mode
# $env.config.edit_mode = 'vi'

# 👇 Banner
# $env.config.show_banner = false

# 👇 History
# $env.config.history = {
#   file_format: sqlite
#   max_size: 1_000_000
#   sync_on_enter: true
#   isolation: true
# }

# 👇 Atuin
# source ~/dotfiles/config/shell/functions/atuin.nu

# 👇 Functions
# def open-repo [cwd: string = "nvim"] {
#   let r = (tv git-repos | default "")
#   if $r != "" { ^$cwd $r }
# }

# def jump-repo [cwd: string = "cd"] {
#   let r = (tv git-repos | default "")
#   if $r != "" { ^$cwd $r }
# }

# 👇 Alias
# alias jr = jump-repo
# alias or = open-repo
# alias q = exit
