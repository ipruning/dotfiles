# dotfiles

Personal macOS configuration, workstation setup, and standalone maintenance
tools.

## Repository model

- `modules/` contains maintained source: commands, shell fragments, Mackup
  config, app config, and self-installing tools.
- `home/` is Mackup backup data copied to and from `$HOME`. Edit tracked shell
  startup files there only when changing restored shell behavior.
- `generated/` is rebuilt by repository commands. Host inventory under
  `generated/docs/<hostname>/` is tracked; generated binaries, completions,
  functions, and plugins are not.

Agent-specific rules live in `AGENTS.md`; files under `modules/` also inherit
`modules/AGENTS.md`.

## Setup and commands

The task entrypoints require macOS, Git, mise, uv, and gum. Individual tasks
report their own additional dependencies.

```bash
git clone <your-repo-url> ~/dotfiles
cd ~/dotfiles
mise tasks
```

Use `mise run <task>` when a task exists. Each task delegates to a
`modules/bin/dotfiles-*` command rather than duplicating its behavior in
`mise.toml`.

A new machine uses the repository entrypoints in this order:

```bash
mise run init
mise run restore
mise run sync
```

`init` establishes the baseline tool and plugin environment. `restore` applies
Mackup data and materializes private configuration when its authorized inputs
are available. `sync` rebuilds generated shell assets, refreshes managed
plugins, runs Skillshare, and records host inventory.

`restore` prints the Mackup filesystem plan before asking to apply it. For an
inspection-only run, including machine-readable output for an agent, use:

```bash
mise run restore -- --dry-run
mise run restore -- --dry-run --json
```

Mackup runs directly from the immutable Git commit pinned in
`modules/bin/_lib/mackup.sh`; it is not installed as a persistent command.

## Editing and applying changes

- Change maintained commands and shell fragments under `modules/`, then run the
  matching `mise` task or command.
- Change live app configuration through the app or its file under `$HOME`, then
  run `mise run backup` to update `home/` through Mackup.
- Change tracked shell startup files directly under `home/`, then run
  `mise run restore` to apply them.
- Rebuild generated content with `mise run sync`; do not hand-edit
  `generated/` without a regeneration path.
- Install or upgrade a self-installing tool from its source under
  `modules/<tool>/`. Daily commands must resolve to the installed path, not the
  repository source.

Run `mise run doctor --strict` after path or layout changes.

## Standalone tools

### bag-mode

`bag-mode` keeps a MacBook operational with its lid closed and restores the
settings captured when its controller session began. Its LaunchDaemon executes
a root-owned controller from `/Library/PrivilegedHelperTools`.

```bash
brew install brightness
modules/bag-mode/bag-mode install --dry-run
modules/bag-mode/bag-mode install
bag-mode start
bag-mode doctor --strict --json
```

Use `bag-mode --help` and `bag-mode help <command>` for lifecycle, recovery,
notification, and exit-code behavior.

### macos-session-health

`macos-session-health` monitors macOS user-session launch failures and stores
diagnostics in SQLite.

```bash
modules/macos-session-health/macos-session-health install
macos-session-health status --format json
macos-session-health incident --hours 6 --format markdown
```

Recovery safety and incident interpretation live in
`modules/macos-session-health/README.md`.

### macos-maxfiles

`macos-maxfiles` owns the machine-wide launchd maxfiles setting and generates
its LaunchDaemon during installation.

```bash
modules/macos-maxfiles/macos-maxfiles install --dry-run
modules/macos-maxfiles/macos-maxfiles install
macos-maxfiles status --json
```

## Skillshare

Global harness prompts and AI skills are owned by the Skillshare source repo.
This repository stores only its Mackup-managed config. `restore` and `sync` run
Skillshare so installed prompts match that source.

## Python scripts

Standalone Python scripts declare their runtime and dependencies with PEP 723.
The repository development environment uses `pyproject.toml` and `uv.lock`.
Read versions from those machine-readable sources instead of copying them into
documentation.

## License

See `LICENSE`.
