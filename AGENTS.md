# Repository Guidelines

## Project Structure & Module Organization

- `config/`: Shared configuration.
  - `shell/` (aliases, env, functions, plugins)
  - `packages/` (Homebrew lists: `brew_*.M2.txt`, `brew_*.M4.txt`)
  - `mackup/` (app settings backup via Mackup)
- `home/`: Files that map to `$HOME` (e.g., `.config/` for fish, Zed, Zellij, Karabiner).
- Private values use templates (e.g., `env.private.tpl.zsh` → `env.private.zsh`). Never commit secrets.

## Build, Test, and Development Commands

- `mise install`: Install toolchain from `~/.config/mise/config.toml`.
- `mise run init`: One‑time setup (pre‑commit, plugin fetch, Mackup restore, completions).
- `mise run lint`: Run all linters/formatters through pre‑commit.
- `pre-commit run -a`: Lint all tracked files locally.
- `mise tasks`: List available repository tasks.

## Coding Style & Naming Conventions

- Shell: bash/zsh/fish. Prefer strict mode in scripts (`set -euo pipefail`).
- Keep functions small and composable; put helpers in `config/shell/functions/`.
- Markdown: linted by markdownlint-cli2; line length is relaxed in this repo.
- Filenames: lowercase with clear purpose; use `.zsh`/`.fish`/`.md` (e.g., `utils.zsh`, `aliases.fish`).

## Testing Guidelines

- No unit tests. Treat tests as repo hygiene.
- Run `mise run lint` before pushing.
- For link changes, verify via pre‑commit’s lychee.
- For shell changes, reload and smoke‑test: `source ~/.zshrc` or `source ~/.config/fish/config.fish`.

## Commit & Pull Request Guidelines

- Commits: Conventional Commits (e.g., `feat(shell): add docker alias`). Keep subjects concise and imperative.
- PRs: Provide summary, rationale, and scope. Link related issues. Include before/after snippets or screenshots for UI/tooling changes (Zed, Zellij, Karabiner).
- Packages: When editing `config/packages/`, note machine context (M2 vs M4).

## Security & Configuration Tips

- Do not commit secrets. Use `*private*` files locally and keep templates (`*.tpl`) in git.
- Pre‑commit runs ripsecrets. If tripped, rotate keys and update templates.
- See `README.md` for installation details and `CLAUDE.md` for agent‑specific context.

## Agent‑Specific Notes (Optional)

- Keep changes minimal, focused, and well‑scoped; prefer small diffs.
- Use clear plans and concise preambles when running commands. Run `mise run lint` before finishing.
- Avoid committing directly unless requested; update docs when behavior changes.
