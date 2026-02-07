# Repository Guidelines

## Project Structure & Module Organization

- `modules/` is the canonical source of configs, scripts, and templates. Common areas: `modules/bin/`, `modules/zsh/`, `modules/mackup/`, `modules/surfingkeys/`.
- `home/` is a Mackup snapshot tree (artifact). Avoid hand edits unless you are intentionally changing backup output.
- `.mise/tasks/` contains the primary task scripts used for bootstrap, backup, restore, and sync.
- `generated/` holds regenerated outputs (bin/completions/functions/plugins/docs). Safe to delete when regeneration is available.
  - `generated/plugins/` contains third-party ZSH plugins (git-ignored).
  - `generated/docs/<hostname>/` stores host-specific snapshots (brew/apps/extensions).

## Build, Test, and Development Commands

- `mise tasks` lists available tasks.
- `mise run init` installs/updates tooling, plugins, and Mackup links.
- `mise run restore` restores the Mackup snapshot into the system.
- `mise run backup` runs `mackup backup --force` to snapshot configs into `home/`.
- `mise run sync` pulls plugins, regenerates shell completions/functions, and injects secrets.
- `mise run zsh-profile [runs] [warmup]` profiles Zsh startup (requires `hyperfine`).

## Coding Style & Naming Conventions

- Bash task scripts use `#!/usr/bin/env bash`, `set -euo pipefail`, and 2-space indentation.
- Prefer a functional core with an imperative shell: keep pure logic separate from I/O and side effects.
- New scripts in `modules/bin/` should be executable and use kebab-case names (Python helpers end in `.py`).
- Templates use `*.tpl.*`; secrets belong in `*.private.*` files (ignored by git).

## Testing Guidelines

- No formal automated test suite is defined.
- Verify changes by running the relevant `mise` task and confirming outputs in `generated/` and `home/` look intentional.
- For script changes, run the script directly with representative inputs.

## Commit & Pull Request Guidelines

- Follow Conventional Commits: `type(scope): summary` (e.g. `chore(brew): update packages`).
- **Always include a scope** — use the tool or directory name: `brew`, `mise`, `zsh`, `ghostty`, `bin`, `yazi`, `docs`, etc.
- Multiple scopes: `chore(brew,mise): ...` (cap at 3).
- Keep commits focused and scoped to a single logical change.
- Write concise, specific summaries — no LLM filler words.
- PRs should include: a short summary, impacted paths (for example `modules/zsh/`), and commands run.

## Security & Configuration Tips

- Never commit secrets. Use templates and `*.private.*` files, and keep sensitive data out of `generated/` and `home/`.
