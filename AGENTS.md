# Agent Guidelines

This file governs work in this repository. Human-facing behavior and command
semantics live in `README.md`.

## Source ownership

- `mise.toml` is the task interface. Keep it as a thin adapter to modules under
  `scripts/`.
- `scripts/` owns inspection plus explicit host update, runtime refresh, and
  application-scoped restore behavior. Tests exercise public CLI and
  `inspect_*` interfaces.
- `reference/` is comparison data and the source for explicit scoped restore;
  it is never applied automatically.
- `mackup/` owns the application-to-path mapping consumed by the pinned Mackup
  fork.
- `modules/` owns independent commands and self-installing tools. It inherits
  `modules/AGENTS.md`.
- `generated/` is optional runtime state. Do not track host inventories or
  claim that it represents current host truth.

## Working rules

- Use `mise tasks` to discover commands and the relevant `mise run <task>`
  entrypoint for verification.
- Keep `diff`, `check`, and `lint` read-only. A repair or installation belongs
  in an explicit user-directed operation, not inside an inspection.
- Keep stdout machine-readable when `--json` is selected and send operational
  failures to stderr.
- Compare reference and live configuration by location and metadata. Do not
  expose configuration contents in drift reports.
- Never commit secrets. Track templates; keep materialized `*private*` files
  ignored.
- Run `mise run verify` after changing Python tasks, shell files, mappings, or
  repository layout.
- Naming rule: `apply_*` operations change file state and serialize their
  results as `changes`; `execute_*` operations run external commands and
  serialize theirs as `steps`.

## Skillshare boundary

Global harness prompts and skills are owned by the Skillshare source repo.
This repository may inspect the configured source and store its reference
configuration, but it must not synchronize or rewrite global harness files.

## Commits

- Follow Conventional Commits with a scope, for example
  `feat(inspect): add host capability checks`.
- Keep commits focused on one logical change.
- Include commands actually run when summarizing work.
