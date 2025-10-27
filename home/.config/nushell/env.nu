# 👇 Autoload Directory
let autoload_dir = $nu.default-config-dir | path join "autoload"
mkdir $autoload_dir

# 👇 Mise
let mise_bin = if ("/opt/homebrew/bin/mise" | path exists) {
  "/opt/homebrew/bin/mise"
} else if ("/usr/local/bin/mise" | path exists) {
  "/usr/local/bin/mise"
} else if (($nu.home-path | path join ".local/bin/mise") | path exists) {
  $nu.home-path | path join ".local/bin/mise"
} else {
  null
}

# 👇 Mise
if $mise_bin != null {
  ^$mise_bin activate nu | save -f ($autoload_dir | path join "mise.nu")
} else if ((which mise | length) > 0) {
  ^mise activate nu | save -f ($autoload_dir | path join "mise.nu")
}

# 👇 Carapace
$env.CARAPACE_BRIDGES = 'zsh'
mkdir ~/.cache/carapace
/opt/homebrew/bin/carapace _carapace nushell | save --force ~/.cache/carapace/init.nu

# 👇 Path
$env.PATH = ($env.PATH
  | prepend $"($env.HOME)/Developer/prototypes/utils/bin"
  | prepend $"($env.HOME)/Developer/prototypes/utils/scripts"
  | prepend $"($env.HOME)/dotfiles/config/shell/bin"
  | prepend $"($env.HOME)/.local/bin"
)
