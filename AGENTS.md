# Repository Guidelines

## Project Structure & Module Organization

- `config/`: shared configuration.
  - `shell/`: aliases, env, functions, plugins.
  - `packages/`: Homebrew lists (`brew_*.M2.txt`, `brew_*.M4.txt`).
  - `mackup/`: app settings backup via Mackup.
- `home/`: maps to `$HOME` (e.g., `.config/` for fish, Zed, Zellij, Karabiner).
- Private values use templates (e.g., `env.private.tpl.zsh` → `env.private.zsh`). Never commit secrets.

## Build, Test, and Development Commands

- `mise install`: install toolchain from `~/.config/mise/config.toml`.
- `mise run init`: one‑time setup (pre‑commit, plugin fetch, Mackup restore, completions).
- `mise run lint`: run all linters/formatters via pre‑commit.
- `pre-commit run -a`: lint all tracked files locally.
- `mise tasks`: list available repo tasks.

## Coding Style & Naming Conventions

- Shell (bash/zsh/fish); prefer strict mode: `set -euo pipefail`.
- Small, composable functions; put helpers in `config/shell/functions/`.
- Markdown is linted by markdownlint-cli2; line length is relaxed.
- Filenames: lowercase and purpose‑driven; use `.zsh`/`.fish`/`.md` (e.g., `utils.zsh`, `aliases.fish`).
- “One file, one job”: keep each script focused.

## Testing Guidelines

- No unit tests; treat tests as repo hygiene.
- Run `mise run lint` (or `pre-commit run -a`) before pushing.
- For link changes, pre‑commit’s lychee checks links.
- For shell changes, reload and smoke‑test:
  - zsh: `source ~/.zshrc`
  - fish: `source ~/.config/fish/config.fish`

## Commit & Pull Request Guidelines

- Conventional Commits (e.g., `feat(shell): add docker alias`); concise, imperative subjects.
- PRs: include summary, rationale, scope; link issues; add before/after snippets or screenshots for UI/tooling (Zed, Zellij, Karabiner).
- When editing `config/packages/`, note machine context (M2 vs M4).

## Security & Configuration Tips

- Do not commit secrets; keep `*private*` files local and commit only templates (`*.tpl`).
- pre‑commit runs ripsecrets; if tripped, rotate keys and update templates.
- See `README.md` for installation and `CLAUDE.md` for agent context.
