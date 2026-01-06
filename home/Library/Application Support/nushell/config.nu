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

# 👇 Banner
$env.config.show_banner = false

# 👇 Completions
let carapace_completer = {|spans: list<string>|
  carapace $spans.0 nushell ...$spans | from json
}

$env.config.completions.external = {
  enable: true
  max_results: 100
  completer: $carapace_completer
}

# 👇 Editor
$env.config.buffer_editor = ["/opt/homebrew/bin/zed", "--wait"]
$env.EDITOR = "/opt/homebrew/bin/zed --wait"

# 👇 Edit Mode
# $env.config.edit_mode = 'vi'

# 👇 Functions
def open-repo [cwd: string = "nvim"] {
  let r = (tv git-repos | default "")
  if $r != "" { ^$cwd $r }
}

def jump-repo [cwd: string = "cd"] {
  let r = (tv git-repos | default "")
  if $r != "" { ^$cwd $r }
}

# 👇 Alias
alias jr = jump-repo
alias or = open-repo
