# AGENTS.md

## Architecture

- `home/` - Dotfiles symlinked to $HOME (e.g., .zshrc, .gitconfig, .config/)
- `modules/` - Modular configs: zsh (aliases, env, functions), mackup, surfingkeys
- `scripts/` - Executable utilities (Python and shell scripts)
- `inventory/hosts/` - Per-machine package lists (mac-mini/, macbook/)
- `vendor/plugins/` - ZSH plugins (fzf-tab, autosuggestions, syntax-highlighting)
- `.mise/tasks/` - Automation tasks (init, sync, backup, restore)
