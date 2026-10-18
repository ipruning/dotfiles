# Agent Guidelines

This file governs work in this repository. Human-facing behavior and command
semantics live in `README.md`.

## Layout

Each top-level directory is one primitive. Use these names in code, output, and
documentation; do not invent synonyms.

| Directory | Primitive | Owner and rule |
| --- | --- | --- |
| `scripts/` | task | Every `mise run <task>`. `mise.toml` stays a thin adapter: task `foo-bar` runs `python -m scripts.foo_bar`; companion modules are named `<task>_*.py`. |
| `reference/` | reference | Desired configuration files. Compared with live files, applied only by an explicit scoped `restore`. |
| `mackup/` | mapping | Application-to-path mapping consumed by the pinned Mackup fork. |
| `shell/` | shell fragment | Zsh and Bash files sourced by the reference startup files. |
| `commands/` | command | Independent user commands on the macOS `PATH`, indexed in `commands/README.md`. |
| `services/` | service | Self-installing tools that own their installation, launchd/systemd files, tests, and runbook. |
| `manual/` | manual config | Tracked configuration no task applies; the operator copies it by hand (browser extension settings, GitHub rulesets). |
| `generated/` | generated | Ignored local output written only by `mise run generate`. Never track it or read it as host truth. |
| `inventory/` | snapshot | Per-host software snapshots written only by `mise run inventory`; one point in time, never current host truth. |

On the host side, **live** means the file at its `$HOME` location. The
repository root is `DOTFILES_ROOT` in shell and `repo_root` in Python.

## Vocabulary

- **Operations**: `check` inspects the host, `lint` the repository, `diff`
  reference against live. They never change state. Every other task plans by
  default (`plan_*`) and changes state only with `--apply`; human-facing text
  calls the plan a preview.
- **Directions**: `restore` makes live point at reference; `adopt` copies live
  back into reference. `update` installs locked tool versions and runs host
  self-updaters; `upgrade-tools` advances the lock; `mise-sync` connects mise
  configuration and installs missing baseline tools; `generate` rewrites
  `generated/`.
- **Status** (`scripts.models.Status`), shared by every report: `planned`,
  `succeeded`, `unchanged`, `skipped`, `failed`. Explain a non-success status in
  `reason`. Summaries use `status_summary`.
- **Severity** (findings and `doctor` steps): `ok`, `warn`, `error`. A result
  that does not apply has `applicable: false` and renders as `skipped`.
- **JSON lists**: `changes` holds file-level edits a task plans or made
  (`restore`, `adopt`, `setup-linux-lite`); `steps` holds ordered commands or
  generators, whether or not their result is a file (`update`, `generate`,
  `inventory`, `clean`, `mise-sync`). `diff` keeps `changes` from the Mackup
  protocol to mean observed drift.

## Working rules

- Use `mise tasks` and `mise tasks info <task>` to discover repository
  operations without executing them. Inspection and maintenance CLIs expose
  `mise run <task> -- --help`; aggregate verification tasks do not. Commands
  and services document their own interfaces; read their index or runbook
  instead of probing a bare command or assuming task flags.
- Keep `diff`, `check`, and `lint` read-only. A repair or installation belongs
  in an explicit user-directed operation, not inside an inspection.
- External commands used by `check` must be proven read-only. A deeper probe
  that writes caches, migrations, or temporary target files belongs in the
  finding's suggested action, not in inspection.
- Do not add `--dry-run` flags or mutate-by-default task entrypoints.
- Keep stdout machine-readable when `--json` is selected and send operational
  failures to stderr. Every JSON document carries `schema_version`,
  `operation`, and `ok`; mutating operations add `apply`; domain failures with
  `--json` emit the shared error document from `scripts/render.py`.
- Compose tasks through their public functions or `python -m scripts.<task>
  --json`. Do not import another module's underscore names.
- Compare reference and live configuration by location and metadata. Do not
  expose configuration contents in drift reports.
- Parse structured data with its real parser: `jq` or a JSON library for JSON,
  `tomllib` or a TOML-aware CLI for TOML, and `ruamel.yaml` for YAML. Never
  approximate these formats with grep, regular expressions, or string splits.
- Keep Finding JSON compatible: `check`, `severity`, `applicable`, `code`,
  `message`, `path`, and `action`. Put concrete facts in `message` and `path`;
  `action` suggests inspection or an explicit operator command; it never
  authorizes automatic repair.
- Add owner checks only for observed conflicts with known candidates; do not
  build a generic package-manager or PATH ownership framework.
- Add persistent state only for a real transaction or cross-process recovery
  requirement. Before growing a production file beyond roughly 800 lines,
  choose explicitly to split its domain, delete obsolete behavior, or freeze
  its scope. `services/macos-session-health` is frozen at its current scope.
- Never commit secrets. Track templates (`*.tpl.*`); keep materialized
  `*private*` files ignored.
- Run `mise run verify` after changing Python tasks, shell files, mappings, or
  repository layout.

## Commands and services

- New command names use kebab-case. Directly invoked commands use a working
  shebang and executable mode. Keep helpers inside their command; add a shared
  helper only when at least two real commands call it.
- Agent-facing output stays parseable. Send diagnostics to stderr and provide a
  JSON format when another program consumes the result.
- Runtime state, logs, and exported evidence live outside the repository.
- A service's executable owns its command interface, installation, removal, and
  generated system configuration. Keep its tests and runbook beside it, and do
  not add a second wrapper under `commands/`. Generate host-specific launchd
  files during installation rather than tracking a second plist source. Verify
  lifecycle changes through the service's public CLI: installation preview,
  tests, installed status, and uninstall path.
- Use ast-grep for one-off, read-only structural investigation. Persistent
  Python policy belongs in Ruff or ty; do not add `sgconfig.yml` or a separate
  ast-grep gate.

## Operator handoff

- The human who owns the target host is the Operator. An agent carrying out a
  delegated task is the Executor.
- Before mutating the host, use the operation's public inspection or preview
  entrypoint.
- Stop before mutation when inspection exposes ambiguous ownership, unclear
  scope, destructive effects that were not already authorized, or multiple
  legitimate outcomes. Report the verified facts, impact, options,
  recommendation, and exact decision needed from the Operator.
- A recommendation is not authorization. Approval of one option does not
  authorize adjacent options or cleanup.
- Apply only the selected operation, then rerun the relevant inspection and
  report residual findings.

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

## Skillshare boundary

Global harness prompts and skills are owned by the Skillshare source repo.
This repository may inspect the configured source and store its reference
configuration, but it must not synchronize or rewrite global harness files.
Pi's `.pi/agent/AGENTS.md` is the explicit exception: the `agents` Mackup
mapping owns it, and only an operator-directed scoped restore applies it.

## Commits

- Follow Conventional Commits with a scope, for example
  `feat(check): add host capability checks`.
- Keep commits focused on one logical change.
- Include commands actually run when summarizing work.
