# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a personal dotfiles repository for macOS development environment with dual shell support (zsh/fish) and modern tooling. The repository follows a structured approach with configuration files organized by category and home directory files following XDG standards. All automation is handled through mise tasks and shell functions - there are no traditional build files (Makefile, package.json).

## Key Architecture

### Directory Structure

- `config/` - Configuration files organized by category:
  - `shell/` - Shell configurations (aliases, env, functions, plugins)
  - `packages/` - Homebrew package lists for different machines (M2/M4)
  - `misc/` - Additional configurations (surfingkeys.js)
  - `mackup/` - Mackup configuration for app settings backup
- `home/` - Direct home directory files and XDG configurations
  - `.config/` - Application configurations following XDG standards
- `.mise/tasks/` - Mise task definitions for automation (replaces traditional Makefiles)

### Tool Management Hierarchy

1. **mise**: Primary tool for unified version and tool management (replaces asdf/rtx)
   - Manages languages (Node.js, Python, Go, Rust, Ruby, Deno, Bun, Zig)
   - Manages CLI tools (claude-code, amp, llm, modal, codex, gemini-cli)
   - Task runner for automation (mise tasks in `.mise/tasks/`)
2. **Homebrew**: Package management with machine-specific lists
3. **pre-commit**: Automated linting, security scanning, and CJK text formatting

## Common Commands

### Environment Setup

```bash
# Complete initial setup (installs tools, pre-commit hooks, plugins, creates symlinks)
mise init

# Install all tools and dependencies
mise install

# Set up pre-commit hooks only
pre-commit install

# Source shell configurations
source ~/.zshrc  # for zsh
source ~/.config/fish/config.fish  # for fish
```

### Development Tasks

```bash
# Run linting/pre-commit checks
mise lint

# Sync shell completions for all CLI tools
mise sync-completion

# List all available mise tasks
mise tasks
```

### Package Management

```bash
# Update all tools and packages (master command)
upgrade-all  # Updates Homebrew, mise, gh extensions, and backs up package lists to config/packages/

# Update individual components
brew update && brew upgrade
mise upgrade
gh extension upgrade --all
```

### Pre-commit Operations

```bash
# Run pre-commit hooks manually
pre-commit run --all-files

# Hook pipeline (in order):
# 1. YAML validation + trailing whitespace removal
# 2. Markdown linting with auto-fix
# 3. Secret scanning (ripsecrets)
# 4. Link validation (lychee) with smart excludes
# 5. CJK text formatting (autocorrect)
```

## Shell Configuration

### Dual Shell Support

The repository supports both zsh and fish shells with consistent functionality:

- Aliases are maintained in both `config/shell/aliases.zsh` and `config/shell/aliases.fish`
- Environment variables in `config/shell/env.zsh` and `config/shell/env.fish`
- Shell-specific functions in `config/shell/functions/`

### Key Aliases and Functions

- Modern CLI replacements: `ls` → `eza`, `cat` → `bat`, `find` → `fd`, `grep` → `rg`
- Git shortcuts: `g` → `lazygit`, `gst` → `git status`, `gaa` → `git add --all --verbose`
- Development: `d` → `lazydocker`, `jr` → `jump-to-repo`, `js` → `jump-to-session`
- Navigation: `j` → `zoxide` (smart directory jumping), `y` → `yazi` (with directory change on exit)
- System utilities: `upgrade-all` function updates all package managers and backs up package states

### Private Configuration

Use `.tpl` template files for private configurations:

- `config/shell/env.private.tpl.zsh` → `config/shell/env.private.zsh`
- `config/shell/env.private.tpl.fish` → `config/shell/env.private.fish`

## Development Tools

### Core Tools (via mise)

- **Languages**: Node.js, Python, Go, Rust, Ruby, Deno, Bun, Zig
- **AI/Development**: claude-code, amp, llm, modal, codex, gemini-cli
- **Git Tools**: lazygit, lazydocker, lazysql
- **Quality Tools**: biome, ruff, typos-cli, basedpyright, pre-commit
- **Security**: ripsecrets, lychee

### macOS Applications

- **Terminal**: Ghostty, Zellij (multiplexer)
- **Editor**: Zed, Visual Studio Code, Cursor
- **File Management**: Yazi (terminal file manager)
- **Window Management**: Aerospace (tiling WM)
- **Input**: Karabiner Elements, Linear Mouse

## Package Management Strategy

### Machine-Specific Package Lists

Package lists are maintained per machine type (hostname-based):

- `config/packages/brew_dump.{hostname}.txt` - Complete Homebrew bundle format
- `config/packages/brew_leaves.{hostname}.txt` - Only explicitly installed packages
- `config/packages/brew_installed.{hostname}.txt` - All installed packages

The `upgrade-all` function automatically backs up current package states to these files, enabling machine-specific package management and restoration.

## Quality and Security

### Pre-commit Pipeline

The repository uses a comprehensive pre-commit pipeline with:

- **Code Quality**: YAML validation, markdown linting, trailing whitespace removal
- **Security**: Secret scanning with ripsecrets
- **Link Validation**: Broken link detection with lychee
- **Text Processing**: CJK (Chinese/Japanese/Korean) text formatting with autocorrect

### Tool Configuration

- mise configuration in `home/.config/mise/config.toml`
- Pre-commit hooks in `.pre-commit-config.yaml`
- Shell plugins managed as git submodules in `config/shell/plugins/`

## Working with this Repository

### Adding New Tools

1. Add to `home/.config/mise/config.toml` for programming tools
2. Add to appropriate Homebrew package list for system applications
3. Update aliases in both `config/shell/aliases.zsh` and `config/shell/aliases.fish`
4. Run `upgrade-all` to backup new package state

### Configuration Changes

- Shell configurations must be made in both zsh and fish variants to maintain parity
- Use the `logger` function from `config/shell/functions/utils.zsh` for consistent logging
- Private configurations should use the `.tpl` template system
- Shell plugins are managed as git submodules in `config/shell/plugins/`

### Testing Changes

Run pre-commit hooks before committing:

```bash
mise lint  # or
pre-commit run --all-files
```

### Session and Navigation Patterns

- Repository navigation: `jr` (jump-to-repo) uses `television` for fuzzy finding
- Session management: `js` (jump-to-session) for Zellij sessions
- Automatic Zellij session creation with pattern `repo-t-{basename}`
- Zed editor tasks integrate with terminal tools via `home/.config/zed/tasks.json`

### Plugin Management

ZSH plugins (git submodules):

- `fast-syntax-highlighting` - Real-time syntax highlighting
- `zsh-autosuggestions` - History-based suggestions
- `fzf-tab` - Fuzzy completion interface
- `ugit` - Interactive git undo

Update plugins via `mise init` task which handles both shell and Zellij plugins.
