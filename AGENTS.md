# Agent Guidelines

This file governs work in this repository. Human-facing behavior and command
semantics live in `README.md`.

## Layout

Each top-level directory owns one primitive:

| Directory | Primitive | Owner and rule |
| --- | --- | --- |
| `scripts/` | task | Every `mise run <task>`. `mise.toml` stays a thin adapter: task `foo-bar` runs `python -m scripts.foo_bar`; companion modules are named `<task>_*.py`. |
| `reference/` | reference | Desired configuration files. Compared with live files, applied only by an explicit scoped `restore`. |
| `mackup/` | mapping | Application-to-path mapping used by the repository's configuration tasks. |
| `shell/` | shell fragment | Zsh and Bash files sourced by the reference startup files. |
| `commands/` | command | Independent user commands on the macOS `PATH`, indexed in `commands/README.md`. |
| `services/` | service | Self-installing tools that own their installation, launchd/systemd files, tests, and runbook. |
| `manual/` | manual config | Tracked configuration no task applies; the operator copies it by hand (browser extension settings, GitHub rulesets). |
| `generated/` | generated | Ignored local output written only by `mise run generate`. Never track it or read it as host truth. |
| `inventory/` | snapshot | Per-host software snapshots written only by `mise run inventory`; one point in time, never current host truth. |

On the host side, **live** means the file at its `$HOME` location. The
repository root is `DOTFILES_ROOT` in shell and `repo_root` in Python.

## Working rules

- `check`, `lint`, and `diff` (plus every external command they invoke) must
  stay strictly read-only. Every other task plans by default (`plan_*`) and
  mutates only with `--apply`; do not add `--dry-run` flags or mutate-by-default
  entrypoints. Run the corresponding read-only check or preview before mutating
  the host with `--apply`.
- Direction: `restore` makes live point at reference; `adopt` copies live back
  into reference.
- `--json` emits only machine-readable JSON on stdout and sends operational
  failures to stderr. Keep report and `Finding` schemas compatible with
  `scripts/models.py` and `scripts/render.py` (`changes` for file-level edits
  or drift; `steps` for ordered commands or generators).
- Compose tasks through their public functions or `python -m scripts.<task>
  --json`. Aggregate verification tasks do not expose `--help`.
- Compare reference and live configuration by location and metadata; never
  expose configuration contents in drift reports.
- Use `ruamel.yaml` for YAML reads and writes. Persistent Python lint/type
  policy belongs in Ruff or ty.
- Never commit secrets. Track templates (`*.tpl.*`); keep materialized
  `*private*` files ignored.
- Run `mise run verify` after changing Python tasks, shell files, mappings, or
  repository layout.

## Commands and services

- New command names use kebab-case. Runtime state, logs, and exported evidence
  live outside the repository.
- A service's executable owns its CLI, installation, removal, and dynamically
  generated launchd/systemd configuration; keep its tests and runbook beside it
  and do not add a second wrapper under `commands/`. `services/macos-session-health`
  is frozen at its current scope.
- Verify service changes through the relevant public CLI preview, tests, or
  lifecycle path.

## Dependency policy

Two tiers, in decreasing strictness:

1. Hard floor: Git and mise bootstrap the repository; `mise.toml` pins every
   executable the repository itself needs and `uv.lock` pins its Python
   packages. Nothing else is required.
2. Optional host capabilities (atuin, starship, zsh, tv, gum, ...): guard every
   use (`command -v`, `[[ -d ]]`, `[[ -r ]]`), degrade gracefully when absent,
   and report the gap as a `check` warning with an install hint. Shared
   personal tools may be declared in the global mise reference; host-specific
   tools belong to that host's package manager. Neither path may install
   during inspection or shell startup.

If a tool participates in `mise run verify`, it must be pinnable through mise.
If it is not pinnable, the gate must skip its scope loudly instead of failing.
Do not add cross-platform installers for optional tools.

## Shell and mise on this host

These rules describe the reference Zsh setup; Linux Lite Bash uses
`mise activate`.

- Every Zsh, interactive or not, resolves mise tools through the shims that
  `.zshenv` puts first on `PATH`; Zsh never loads `mise activate`. `PATH` holds
  no `mise/installs/<tool>/<version>` directory, so an upgrade or install is
  visible on the next call in every shell and agent snapshot.
- Project `[env]` values, `_.file`, `_.path`, and `_.python.venv` reach only
  processes mise launches: shims, `mise exec --`, and `mise run`. The shell
  itself does not see them; inspect them with `mise env`, and run non-mise
  programs that need them with `mise exec -- <command>`.
- In a project with `_.python.venv`, bare `python` is the mise interpreter, not
  the virtualenv. Use `uv run`, `mise exec -- python`, or `.venv/bin/python`.
- `gh` belongs to the shared mise baseline, so its shim applies directory
  `[env]` such as the `GH_TOKEN` that selects the account under a workspace;
  `gh auth git-credential` used by Git resolves the same shim.
- `.zshenv` puts `~/.bun/bin` on `PATH` for `bun add -g` packages.
- The global mise config enables `idiomatic_version_file_enable_tools =
  ["pnpm"]`, so a project that pins pnpm only through `package.json`
  `packageManager` gets that version. `auto_install = false` still applies:
  install a missing version with `mise install pnpm@<version>`.

## Skillshare boundary

Global harness prompts and skills are owned by the Skillshare source repo.
This repository may inspect the configured source and store its reference
configuration, but it must not synchronize or rewrite global harness files.

## Commits

- Follow Conventional Commits with a scope, for example
  `feat(check): add host capability checks`.
