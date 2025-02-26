# AI Agent Guidelines for Working with this Codebase

## Environment & Prerequisites
- This is primarily a dotfiles repository for macOS environment configuration
- Uses Homebrew for package management with primary dependencies in `config/packages/Brewfile`
- Main shell: zsh with customizations

## Code Style & Conventions
- Shell scripts: 2-space indentation, snake_case for function/variable names
- Python: 4-space indentation
- Use shellcheck for shell script linting and shfmt for formatting
- Python: Use ruff for formatting and linting

## Testing & Development
- No formal test infrastructure in this repository
- Manual validation of shell functions should be performed before committing
- Run `upgrade-all` function to update dependencies and backup package lists

## Documentation Practices
- Use emoji prefixes like "👇" for section comments in configuration files
- Comment non-obvious functionality
- Include function documentation for reusable shell functions

## Commit Conventions
- Use conventional commit format: feat:, build:, chore:
- Follow existing coding patterns in similar files