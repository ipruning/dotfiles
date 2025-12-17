# 👇 Autoload Directory
let autoload_dir = $nu.default-config-dir | path join "autoload"
mkdir $autoload_dir

# 👇 Carapace
$env.CARAPACE_BRIDGES = 'zsh,fish,bash,inshellisense'
mkdir ~/.cache/carapace
/opt/homebrew/bin/carapace _carapace nushell | save --force ~/.cache/carapace/init.nu

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
alias q = exit

# 👇 Private Environment Variables
const private_env = "~/.config/nushell/env.private.nu"
source $private_env

# 👇 Mise
let mise_path = $nu.default-config-dir | path join mise.nu
^mise activate nu | save $mise_path --force
