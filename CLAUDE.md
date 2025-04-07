# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

- macOS-focused dotfiles for consistent system configuration
- Cross-shell compatibility (zsh and fish) with parallel functionality
- Managed via symbolic links from repository to home directory locations

## Repository Structure

- config/shell: Shell configurations (zsh and fish)
- config/packages: Package configurations (brew, npm, etc.)
- config/misc: Miscellaneous configs
- home: User home directory configurations

## Code Style Guidelines

- Indent: 2 spaces (general), 4 spaces for C/H files
- Line endings: LF (Unix-style)
- Shell function naming: kebab-case (e.g., `upgrade-all`)
- Variable naming: snake_case (e.g., `local timestamp`)
- Shell conditionals: Check command existence before use: `command -v X &>/dev/null`

## Shell-Specific Patterns

- zsh: Use functions with parameters and defaults: `local loglevel=${2:-"INFO"}`
- fish: Use set_color for output formatting
- Maintain parallel functionality across shells with shell-specific syntax

## Commands

- No formal build/lint/test commands in this repository
- For shell script testing: Run scripts directly or source them manually
- Edit shell scripts with care to maintain cross-shell compatibility
- Package updates: Check brew_dump, brew_leaves, and brew_installed for package lists

## Best Practices

- Add clear section headers with comments: `# Section Name`
- Check environment variables before use: `if [ "$DRY_RUN" = true ]`
- Keep dotfiles well-organized by function and shell type
- Test changes on both shells before committing
