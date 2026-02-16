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

## Performance Optimization Guidelines

- Shell prompt modules (starship, etc.) run on every keystroke — prefer fast tools over correct-by-spec parsers.
- Tool speed hierarchy: **shell builtins** (`[ -f ]`, `command -v`) > **awk/sed/grep** (~2ms) > **compiled CLI** (yq/jq ~8ms) > **heavy CLI** (gh/modal/uvx ~20-400ms).
- Always benchmark with `hyperfine` before and after. Don't assume faster — measure.
- When changing conditional logic (`when`/`if-elif`), enumerate all input combinations in a truth table to catch mismatches between `when` and `command` branches.
- Acceptable trade-off: sacrifice strict format parsing (yq/jq) for regex matching (awk) on files you control (dotfiles, CLI configs).

## Security & Configuration Tips

- Never commit secrets. Use templates and `*.private.*` files, and keep sensitive data out of `generated/` and `home/`.
