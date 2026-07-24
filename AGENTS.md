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
- `generated/` is optional runtime state. Do not track files under it or
  claim that it represents current host truth.
- `inventory/` holds per-host software snapshots written only by `mise run
  inventory`. A snapshot records one point in time; never read it as current
  host truth.

## Working rules

- Use `mise tasks` to discover commands and the relevant `mise run <task>`
  entrypoint for verification.
- Keep `diff`, `check`, and `lint` read-only. A repair or installation belongs
  in an explicit user-directed operation, not inside an inspection.
- Mutating tasks preview by default; only `--apply` changes state. Do not add
  `--dry-run` flags or mutate-by-default entrypoints.
- Keep stdout machine-readable when `--json` is selected and send operational
  failures to stderr. Every JSON document carries `schema_version`,
  `operation`, and `ok`; mutating operations add `apply`; domain failures with
  `--json` emit the shared error document from `scripts/render.py`.
- Compare reference and live configuration by location and metadata. Do not
  expose configuration contents in drift reports.
- Parse structured data with its real parser: `jq` or a JSON library for JSON,
  `tomllib` or a TOML-aware CLI for TOML, and `ruamel.yaml` for YAML. Never
  approximate these formats with grep, regular expressions, or string splits.
- Never commit secrets. Track templates; keep materialized `*private*` files
  ignored.
- Run `mise run verify` after changing Python tasks, shell files, mappings, or
  repository layout.
- Naming rule: `apply_*` operations change file state and serialize their
  results as `changes`; `execute_*` operations run external commands and
  serialize theirs as `steps`.

## Dependency policy

Three tiers, in decreasing strictness:

1. Hard floor: Git and mise bootstrap the repository; mise pins every tool the
   repository itself needs (Python, uv, ShellCheck). Nothing else is required.
2. Optional host capabilities (atuin, starship, zsh, tv, gum, brightness, ...):
   guard every use (`command -v`, `[[ -d ]]`, `[[ -r ]]`), degrade gracefully
   when absent, and report the gap as a `check` warning with an install hint.
   Shared personal tools may be declared in the global Mise reference;
   host-specific tools belong to that host's package manager. Neither path may
   install during inspection or shell startup.
3. Self-built binaries under `generated/bin` are additive enhancements and must
   never be load-bearing; hosts without them use upstream tools or lose the
   feature.

Adjudication when adding a dependency: if a tool participates in `mise run
verify`, it must be pinnable through mise. If it is not pinnable, the gate must
skip its scope loudly instead of failing. Do not add cross-platform installers
for optional tools.

## Skillshare boundary

Global harness prompts and skills are owned by the Skillshare source repo.
This repository may inspect the configured source and store its reference
configuration, but it must not synchronize or rewrite global harness files.

## Commits

- Follow Conventional Commits with a scope, for example
  `feat(inspect): add host capability checks`.
- Keep commits focused on one logical change.
- Include commands actually run when summarizing work.
