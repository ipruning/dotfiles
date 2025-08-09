# Repository Guidelines

## Project Structure & Module Organization

- `config/` — Shared configuration:
  - `shell/` (aliases, env, functions, plugins)
  - `packages/` (Homebrew lists: `brew_*.M2.txt`, `brew_*.M4.txt`)
  - `mackup/` (app settings backup via Mackup)
- `home/` — Files that map to `$HOME` (e.g., `.config/` for fish, zed, zellij, karabiner, etc.).
- Private values use templates: `env.private.tpl.zsh` → `env.private.zsh` (and fish equivalent). Never commit secrets.

## Build, Test, and Development Commands

- `mise install` — Install toolchain from `~/.config/mise/config.toml`.
- `mise run init` — One‑time setup: pre-commit, plugin fetch, Mackup restore, completions.
- `mise run lint` — Run all linters/formatters through pre‑commit.
- `pre-commit run -a` — Lint all tracked files locally.
- `mise tasks` — List available repo tasks.

## Coding Style & Naming Conventions

- **Shell**: bash/zsh/fish. Prefer strict mode in scripts (`set -euo pipefail`). Keep functions small and composable; put zsh/fish helpers in `config/shell/functions/`.
- **Markdown**: linted by markdownlint-cli2; line length is relaxed in this repo.
- **Filenames**: lowercase with clear purpose, extensions `.zsh`/`.fish`/`.md` (e.g., `utils.zsh`, `aliases.fish`).
- **Formatting/Linting**: managed by pre‑commit hooks: markdownlint, ripsecrets, lychee, autocorrect.

## Testing Guidelines

- No unit tests. Treat “tests” as repo hygiene:
  - Run `mise run lint` before pushing.
  - For link changes, verify via pre‑commit’s lychee.
  - For shell changes, reload and smoke‑test: `source ~/.zshrc` or `source ~/.config/fish/config.fish`.

## Commit & Pull Request Guidelines

- **Commits**: Follow Conventional Commits (`feat:`, `chore:`, `refactor:`). Write concise, imperative subjects.
- **PRs**: Provide a summary, rationale, and scope. Link related issues. Include before/after snippets or screenshots for UI/tooling changes (e.g., Zed, Zellij, Karabiner). Note machine context (M2/M4) when editing `config/packages/`.

## Security & Configuration Tips

- Do not commit secrets. Use `*private*` files locally; keep templates (`*.tpl`) in git.
- Pre‑commit runs ripsecrets automatically. If tripped, rotate keys and update templates.
- See `README.md` for installation details and `CLAUDE.md` for agent-specific context.
