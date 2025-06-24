# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a dotfiles repository for macOS development environments, featuring:

- Dual shell support (zsh and fish)
- Modern CLI tooling (eza, bat, fd, fzf, lazygit, etc.)
- Tool version management via mise
- Machine-specific configurations (M2/M4 Macs)
- Pre-commit hooks for code quality

## Common Development Commands

### Pre-commit Hooks

```bash
# Run all pre-commit hooks manually
pre-commit run --all-files

# Install pre-commit hooks
pre-commit install
```

### Package Management

```bash
# Install all tools defined in mise config
mise install

# Update all tools
mise update

# List installed tools
mise list
```

### Git Workflow

```bash
# Clean git workflow (alias defined)
gtidy  # Runs: gh tidy && git fetch --prune

# Navigate to git root
cdr    # Changes to git repository root

# Browse repo on GitHub
gb     # Opens git repository in browser

# Interactive git management
g      # Alias for lazygit (TUI git interface)
```

## Architecture and Structure

### Configuration Organization

The repository uses a modular approach:

- **`config/shell/`**: Shell configurations split into:
  - `aliases.{zsh,fish}`: Command aliases
  - `env.{zsh,fish}`: Environment setup and plugin loading
  - `env.private.{zsh,fish}`: Private environment variables (gitignored)
  - `functions/`: Utility functions organized by category
  - `plugins/`: Vendored zsh plugins

- **`home/.config/`**: Application configurations following XDG standards
  - Each application has its own directory with isolated configuration
  - Key apps: aerospace, ghostty, karabiner, mise, zed, zellij

### Machine-Specific Handling

Package lists are maintained separately for different machines:

- `config/packages/brew_*.M2.txt`: M2 Mac packages
- `config/packages/brew_*.M4.txt`: M4 Mac packages

### Shell Configuration Flow

1. `.zshrc` sources modular configs from `config/shell/`
2. Environment setup initializes prompts, key bindings, and tools
3. Aliases and functions are loaded for enhanced productivity
4. Private configurations are sourced if they exist

### Tool Integration Pattern

Tools are integrated via mise and shell initialization:

- Version management through `home/.config/mise/config.toml`
- Shell integration via init scripts (e.g., `eval "$(starship init zsh)"`)
- Modern CLI replacements configured as aliases

## Key Development Patterns

### Security and Quality

Pre-commit hooks (run on commit, commit-msg, and pre-push) enforce:

- YAML validation
- Trailing whitespace removal
- CJK text formatting (autocorrect --lint/--fix)
- Secret scanning (ripsecrets --strict-ignore)
- Link checking (lychee with exclusions for config/shell/)

### Modern Tool Replacements

- `eza` → `ls` (with git integration)
- `bat` → `cat` (syntax highlighting)
- `fd` → `find` (faster, intuitive)
- `rg` → `grep` (ripgrep)
- `zoxide` → `cd` (smart directory jumping)

### Terminal Multiplexing

Primary tool is Zellij (not tmux/screen), with configurations in `home/.config/zellij/`

### Editor Integration

Zed is the primary editor with custom tasks for:

- Terminal integration (tv)
- File management (yazi)
- Git operations (lazygit, gitu)
- Docker management (lazydocker)
- Session management (amp, claude, zellij)

Key Zed tasks available:

- `live_grep`: Search across files using tv
- `file_finder`: Find and open files with fd/tv
- `project_finder`: Navigate to git repositories
- `yazi`: File manager integration
- `lazygit`: Git TUI interface
- `amp`: Session management tool
- `zellij`: Terminal multiplexer sessions
