# 👇 Private Environment Variables (optional; a fresh restore may not have it)
# source is a parse-time keyword, so `if (path exists) { source }` still fails
# to parse a missing file. Sourcing `null` is a documented no-op, so resolve to
# the path only when it exists — the nushell equivalent of the guarded Zsh env.
const private_env = "~/Library/Application Support/nushell/env.private.nu"
source (if ($private_env | path exists) { $private_env } else { null })
