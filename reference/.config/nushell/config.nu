# 👇 Path
use std/util "path add"

# 👇 Homebrew Path
if ("/opt/homebrew/bin" | path exists) {
  path add "/opt/homebrew/bin"
}

# 👇 Cached shell integrations
# Mackup links this file from the live XDG config path, so resolving the link
# locates this checkout without assuming that it lives at ~/dotfiles.
const repo_root = (
  $nu.config-path | path expand | path dirname | path dirname | path dirname | path dirname
)
const generated_functions = ($repo_root | path join "generated/functions")
const mise_init = ($generated_functions | path join "_mise.nu")
const zoxide_init = ($generated_functions | path join "_zoxide.nu")
const mise_bin = ("~/.local/bin/mise" | path expand)
const zoxide_bin = ("~/.local/share/mise/shims/zoxide" | path expand)
source (if (($mise_init | path exists) and ($mise_bin | path exists)) { $mise_init } else { null })
source (if (($zoxide_init | path exists) and ($zoxide_bin | path exists)) { $zoxide_init } else { null })

# 👇 Banner
$env.config.show_banner = false

# 👇 Completions
if not (which carapace | is-empty) {
  let carapace_completer = {|spans: list<string>|
    carapace $spans.0 nushell ...$spans | from json
  }
  $env.config.completions.external = {
    enable: true
    max_results: 100
    completer: $carapace_completer
  }
}

# 👇 Editor
let zed = (which zed | get -o 0.path)
if $zed != null {
  $env.config.buffer_editor = [$zed "--wait"]
  $env.EDITOR = "zed --wait"
  $env.VISUAL = "zed --wait"
}

# 👇 Functions
def select-repo [] {
  tv git-repos | default ""
}

def open-repo [cwd: string = "nvim"] {
  let r = (select-repo)
  if $r != "" { ^$cwd $r }
}

def --env jump-repo [] {
  let r = (select-repo)
  if $r != "" { cd $r }
}

# 👇 Alias
alias jr = jump-repo
alias or = open-repo
