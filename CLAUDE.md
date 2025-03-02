# AI Agent Guidelines for Working with this Codebase

## Environment & Commands

- macOS dotfiles repository with zsh as main shell
- Package management: `brew update && brew upgrade && brew cleanup`
- Version management: `mise upgrade && mise prune && mise reshim`
- Backup commands: `upgrade-all` (backs up packages to `config/packages/`)
- Linting: For shell scripts use shellcheck: `shellcheck <file.sh>`
- Formatting: For shell scripts use shfmt: `shfmt -i 2 -w <file.sh>`
- Python linting/formatting: `ruff check` and `ruff format`

## Code Style & Conventions

- Shell: 2-space indentation, snake_case for variables/functions
- Python: 4-space indentation, follow PEP 8 conventions
- Git shortcuts: Use `g` function for git operations or `lazygit`
- Error handling: Use conditional checks in shell scripts with early returns

## Documentation & Design

- Use emoji prefixes (👇) for section comments
- Document non-obvious functionality
- Include function descriptions in shell functions
- Default to built-in tools and commands when possible
- Follow existing patterns in similar files
- Keep configuration sections logically grouped

## Commit Conventions

- Use conventional commit format: `feat:`, `fix:`, `build:`, `chore:`
- Align with existing code structure and organization
