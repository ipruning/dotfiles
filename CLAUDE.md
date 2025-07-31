# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a personal dotfiles repository for macOS development environment with dual shell support (zsh/fish) and modern tooling. The repository follows a structured approach with configuration files organized by category and home directory files following XDG standards.

## Key Architecture

### Directory Structure

- `config/` - Configuration files organized by category:
  - `shell/` - Shell configurations (aliases, env, functions, plugins)
  - `packages/` - Homebrew package lists for different machines (M2/M4)
  - `misc/` - Additional configurations (surfingkeys.js)
  - `mackup/` - Mackup configuration for app settings backup
- `home/` - Direct home directory files and XDG configurations
  - `.config/` - Application configurations following XDG standards

### Tool Management

- **mise**: Primary tool for unified version and tool management (replaces asdf/rtx)
- **Homebrew**: Package management with machine-specific lists
- **pre-commit**: Automated linting, security scanning, and CJK text formatting

## Common Commands

### Environment Setup

```bash
# Install all tools and dependencies
mise install

# Set up pre-commit hooks
pre-commit install

# Source shell configurations
source ~/.zshrc  # for zsh
source ~/.config/fish/config.fish  # for fish
```

### Package Management

```bash
# Update all tools and packages
upgrade-all  # Custom function that updates Homebrew, mise, gh extensions, and backs up package lists

# Update individual components
brew update && brew upgrade
mise upgrade
gh extension upgrade --all
```

### Pre-commit Operations

```bash
# Run pre-commit hooks manually
pre-commit run --all-files

# Hooks include: YAML validation, trailing whitespace removal, markdown linting, 
# secret scanning (ripsecrets), link checking (lychee), CJK text formatting (autocorrect)
```

## Shell Configuration

### Dual Shell Support

The repository supports both zsh and fish shells with consistent functionality:

- Aliases are maintained in both `config/shell/aliases.zsh` and `config/shell/aliases.fish`
- Environment variables in `config/shell/env.zsh` and `config/shell/env.fish`
- Shell-specific functions in `config/shell/functions/`

### Key Aliases and Functions

- Modern CLI replacements: `ls` → `eza`, `cat` → `bat`, `find` → `fd`
- Git shortcuts: `g` → `lazygit`, `gst` → `git status`, `gaa` → `git add --all --verbose`
- Development: `d` → `lazydocker`, `jr` → `jump-to-repo`
- System utilities: `upgrade-all` function updates all package managers

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

Package lists are maintained per machine type:

- `config/packages/brew_dump.M2.txt` - Complete M2 Mac package list
- `config/packages/brew_dump.M4.txt` - Complete M4 Mac package list
- `config/packages/brew_leaves.M*.txt` - Explicitly installed packages
- `config/packages/brew_installed.M*.txt` - All installed packages

The `upgrade-all` function automatically backs up current package states to these files.

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

### Configuration Changes

- Shell configurations should be made in both zsh and fish variants
- Use the `logger` function from `config/shell/functions/utils.zsh` for consistent logging
- Private configurations should use the `.tpl` template system

### Testing Changes

Run pre-commit hooks before committing:

```bash
pre-commit run --all-files
```
