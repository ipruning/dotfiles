# Agent Guidelines

This file is for agents working in this repo. Human-facing repository
documentation lives in `README.md`.

## Source

- `README.md` is the human-facing guide for layout, command names, Mackup
  behavior, Skillshare ownership, and host inventory rules.
- `mise.toml` defines tasks. Each task calls a `modules/bin/dotfiles-*`
  command; do not duplicate command behavior outside those commands.
- `modules/AGENTS.md` adds rules for files under `modules/`.

## Working Rules

- Prefer editing source files in `modules/`.
- Treat `home/` as Mackup data. Edit tracked shell startup files there only
  when changing restored shell startup behavior.
- Treat `generated/` as generated files. Delete or edit files there only when a
  regeneration path exists.
- Never commit secrets. Use ignored `*.private.*` files or tracked templates.

## Commands

- Use `mise tasks` to list repo commands.
- Use the relevant `mise run <task>` entrypoint when one exists.
- For direct script checks, run the `modules/bin/dotfiles-*` command or helper
  being changed.
- `mise run doctor [--strict] [--json]` checks hardcoded paths without mutating
  files.

## Skillshare Boundary

- Read the `README.md` Agents and skills section before changing Skillshare
  config.
- Do not edit global harness prompt files in this repo.
- When changing where Skillshare installs prompt files, update the Skillshare
  source repo and this repo's Skillshare config together, then verify from this
  repo with `skillshare extras list --json` and
  `skillshare sync --all --dry-run --json`.

## Commits

- Follow Conventional Commits with a scope, for example
  `chore(mise): update tasks`.
- Keep commits focused on one logical change.
- Include commands run when summarizing work.
