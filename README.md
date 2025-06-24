# My dotfiles

<!--rehype:style=font-size: 38px; border-bottom: 0; display: flex; min-height: 260px; align-items: center; justify-content: center;-->

[![jaywcjlove/sb](https://wangchujiang.com/sb/lang/english.svg)](README.md) [![jaywcjlove/sb](https://wangchujiang.com/sb/lang/chinese.svg)](README.zh-cn.md)

<!--rehype:style=text-align: center;-->

Personal dotfiles for macOS development environment with zsh/fish shell support and modern tooling.

## Features

- 🐚 **Dual shell support**: zsh and fish configurations with modern plugins
- 🛠️ **Tool management**: mise for unified version and tool management
- 📦 **Package management**: Homebrew with machine-specific lists (M2/M4)
- ⚡ **Modern CLI tools**: eza, bat, fd, fzf, lazygit, yazi, zellij
- 🎨 **Consistent theming**: Starship prompt with catppuccin-mocha theme
- 🔧 **Pre-commit hooks**: Automated linting, security scanning, and CJK text formatting
- 📱 **macOS apps**: Aerospace, Karabiner, Ghostty, Zed, Linear Mouse
- 🔍 **Enhanced productivity**: atuin for shell history, television for file exploration

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/ipruning/dotfiles.git ~/dotfiles
   ```

2. Install dependencies with mise:

   ```bash
   mise install
   ```

3. Set up pre-commit hooks:

   ```bash
   pre-commit install
   ```

4. Source shell configurations:

   ```bash
   # For zsh
   source ~/.zshrc

   # For fish
   source ~/.config/fish/config.fish
   ```

## Structure

- `config/` - Configuration files organized by category
  - `shell/` - Shell configurations (aliases, env, functions, plugins)
  - `packages/` - Homebrew package lists for different machines (M2/M4)
  - `misc/` - Additional configurations (surfingkeys.js)
  - `mackup/` - Mackup configuration for app settings backup
- `home/` - Direct home directory files and XDG configurations
  - `.config/` - Application configurations following XDG standards
    - `aerospace/` - Window management
    - `atuin/` - Shell history sync
    - `bat/` - Syntax highlighting themes
    - `fish/` - Fish shell configuration
    - `gh/` - GitHub CLI
    - `karabiner/` - Keyboard remapping
    - `mise/` - Tool version management
    - `television/` - File explorer themes
    - `yazi/` - Terminal file manager
    - `zed/` - Code editor settings
    - `zellij/` - Terminal multiplexer layouts

## Tools & Applications

### CLI Tools (via mise)

- **Languages**: Node.js, Python, Go, Rust, Ruby, Deno, Bun
- **Development**: pre-commit, shellcheck, various linters (biome, ruff, typos-cli)
- **Security**: ripsecrets, lychee, cosign, slsa-verifier
- **Productivity**: lazygit, atuin, fzf, just, gfold
- **AI/ML**: claude-code, amp, llm, modal, codex
- **Build Tools**: cargo-binstall, xh, tea, kamal

### macOS Applications

- **Window Management**: Aerospace (tiling window manager)
- **Keyboard**: Karabiner Elements (key remapping)
- **Mouse**: Linear Mouse (acceleration and scrolling)
- **Terminal**: Ghostty (modern terminal emulator)
- **Editor**: Zed (collaborative code editor)
- **Terminal Multiplexer**: Zellij (modern tmux alternative)
- **File Manager**: Yazi (terminal file manager)
- **Version Control**: Lazygit (terminal git UI)

## Customization

### Private Configurations

Use `.tpl` template files for private configurations:

- `config/shell/env.private.tpl.zsh` → `config/shell/env.private.zsh`
- `config/shell/env.private.tpl.fish` → `config/shell/env.private.fish`

### Machine-Specific Packages

Package lists are maintained for different machine types:

- `config/packages/brew_dump.M2.txt` - Complete M2 Mac package list
- `config/packages/brew_dump.M4.txt` - Complete M4 Mac package list
- `config/packages/brew_leaves.M*.txt` - Explicitly installed packages
- `config/packages/brew_installed.M*.txt` - All installed packages

## Key Features & Highlights

### Shell Enhancements

- **zsh plugins**: fast-syntax-highlighting, zsh-autosuggestions, zsh-autocomplete, fzf-tab
- **Modern aliases**: `ls` → `eza`, `cat` → `bat`, `find` → `fd`, `grep` → `rg`
- **Smart navigation**: zoxide for intelligent directory jumping
- **History sync**: atuin for cross-device shell history

### Security & Quality

- **Pre-commit hooks**: YAML validation, trailing whitespace removal, CJK text formatting
- **Secret scanning**: ripsecrets to prevent credential leaks
- **Link checking**: lychee for broken link detection
- **Code quality**: Multiple linters (biome, ruff, typos-cli) with automated fixes

### Development Workflow

- **Git integration**: lazygit, ugit for enhanced version control
- **Terminal multiplexing**: Zellij with custom layouts and plugins
- **File management**: Yazi with preview support and modern navigation
- **Code editing**: Zed with task integration for terminal tools

## ChangeLog

- 2025-06-24 Updated README with latest tools, structure, and comprehensive documentation
- 2025-06-23 Complete rewrite of README with comprehensive documentation
- 2022-05-25 Update README
- 2022-03-01 Make the repo public
