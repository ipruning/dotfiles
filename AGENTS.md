# Agent Configuration for Dotfiles Repository

## Build/Lint/Test Commands

- `mise init` - Initialize monorepo CI/CD tools, update plugins and dependencies
- `mise lint` - Run pre-commit hooks and code linting/formatting
- `mise sync-completion` - Sync shell completion files for all installed tools
- No test suite - this is a dotfiles configuration repository

## Architecture & Structure

- **home/** - Home directory dotfiles (`.zshrc`, `.config/*`, etc.)
- **config/shell/** - Shell configuration (aliases, env vars, functions, plugins)
- **config/packages/** - Package manifests (brew dumps, installed apps lists)
- **config/mackup/** - Mackup configuration for app settings backup
- **.mise/tasks/** - Task automation scripts (init, lint, sync-completion)
- Configuration managed via symlinks from `~/dotfiles` to `~/`
- Uses `mise` for tool version management and task automation
- Uses `mackup` for application settings sync
- Private environment variables in `config/shell/env.private.zsh` (templated via 1Password `op inject`)

## Code Style & Conventions

- Shell scripts use bash with strict mode: `set -euo pipefail`
- Always use `uv` instead of `pip` for Python package management
- Use `ast-grep` for syntax-aware searches, not `rg`/`grep`
- No emojis in output or code
