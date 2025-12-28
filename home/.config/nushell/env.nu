# 👇 Private Environment Variables
const private_env = "~/.config/nushell/env.private.nu"
source $private_env

# 👇 Mise
let mise_path = $nu.default-config-dir | path join mise.nu
^mise activate nu | save $mise_path --force
