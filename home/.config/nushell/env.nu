# 👇 Autoload Directory
let autoload_dir = $nu.default-config-dir | path join "autoload"
mkdir $autoload_dir

# 👇 Carapace
$env.CARAPACE_BRIDGES = 'zsh,fish,bash,inshellisense'
mkdir ~/.cache/carapace
/opt/homebrew/bin/carapace _carapace nushell | save --force ~/.cache/carapace/init.nu

# 👇 Alias
alias q = exit

# 👇 Mise
let mise_path = $nu.default-config-dir | path join mise.nu
^mise activate nu
  | lines
  | where not ($it | str starts-with "hide,") and not ($it | str starts-with "set,")
  | str join (char newline)
  | save $mise_path --force
