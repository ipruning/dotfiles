# dotfiles

Personal configuration references and standalone maintenance tools for macOS
and Linux hosts. This repository reports drift and missing capabilities. It
does not automatically overwrite `$HOME` or rebuild an entire machine.

## Repository model

- `reference/` contains the intended examples compared with live files under
  `$HOME`.
- `mackup/` declares which application paths belong to each reference.
- `scripts/` implements the read-only repository tasks in typed Python.
- `modules/bin/` contains independent user commands.
- `modules/<tool>/` contains substantial tools that own their installation and
  removal.
- `generated/` is optional shell runtime state. A missing generated directory
  is a host-health warning, not a reason to mutate the repository.

Agent-specific rules live in `AGENTS.md`. Files under `modules/` also inherit
`modules/AGENTS.md`.

## Start

Git and mise are the only bootstrap requirements. On a machine without mise,
install it first and expose its user binary to the current bootstrap process:

```bash
curl -fsSL https://mise.run | sh
export PATH="$HOME/.local/bin:$PATH"
git clone https://github.com/ipruning/dotfiles.git ~/dotfiles
cd ~/dotfiles
mise trust
mise install
mise tasks
```

`mise trust` is required because this repository declares a project virtual
environment. mise then provides the pinned Python and uv versions; uv provides
the locked project dependencies.

`mise tasks` is the authoritative command list. The main inspection interface
is:

```bash
mise run diff
mise run check
mise run lint
mise run verify
```

On Linux, `diff` and `check` automatically select the small `linux-lite`
profile. macOS selects `macos`. Use `--profile full` when deliberately auditing
every stored reference:

```bash
mise run diff -- --profile full
mise run check -- --profile full
```

## Linux Lite setup

Inspection remains read-only. The explicit setup task is the only repository
task that changes host configuration:

```bash
mise run setup -- --profile linux-lite --dry-run
mise run setup -- --profile linux-lite
exec bash
```

It preserves the existing `~/.bashrc`, adds one marked block that loads
`modules/bash/init.bash`, and adds `~/.private.gitconfig` to Git's includes. It
does not create an identity, install optional tools, clone private repositories,
or synchronize Skillshare extras. The Bash module adds `~/.local/bin` and mise's
shim directory to `PATH`, then activates mise in interactive shells. It does not
expose `modules/bin` or `generated/bin` on Linux. The managed block is placed
before Ubuntu's non-interactive early return, so direct SSH commands also receive
the user and mise paths without interactive shell initialization.

The Linux Lite drift profile observes only Git and Skillshare configuration.
Skillshare remains optional: a missing executable, configuration, or source is a
warning for a human or AI operator to evaluate, not a setup action.

## Configuration drift

`mise run diff` compares profile-relevant files under `reference/` with the
corresponding paths under the current `$HOME`. It reports locations and file
kinds, never file contents. Ordinary drift exits successfully; an incomplete
inspection, such as an unreadable path or invalid Mackup response, exits
non-zero.

```bash
mise run diff
mise run diff -- git
mise run diff -- --json
mise run diff -- --profile full
```

The command runs the immutable Mackup commit pinned in `scripts/diff.py` and
loads application definitions directly from `mackup/applications/`. It does not
install `~/.mackup` links or change either side.

Restore is deliberately application-scoped. It defaults to the same read-only
plan; `--apply` first moves each changed live path into
`~/.local/state/dotfiles/restore-backups/`, then links the live path to its
reference. There is no implicit restore-all operation.

```bash
mise run restore -- git
mise run restore -- git --json
mise run restore -- git --apply
```

When a live configuration should become the reference, adopt is the mirror of
restore: it is application-scoped, defaults to the same read-only plan, and
`--apply` copies the live truth into `reference/` (and removes reference files
whose live counterpart is gone). It writes only inside the repository, never
under `$HOME`, and refuses to run while the affected reference paths have
uncommitted changes, so Git can always revert an adoption.

```bash
mise run adopt -- mise
mise run adopt -- mise --json
mise run adopt -- mise --apply
```

Git protects repository changes; restore backups protect the replaced live
paths.

## Host health

`mise run check` reports required executables and optional capabilities separately.
Linux Lite requires Git and mise, checks private Git configuration and optional
Skillshare state, and warns when a legacy PATH still exposes repository command
directories. The macOS and full profiles additionally cover the project
Python/uv runtime, Television, generated shell directories, their required
runtime files, and generated binaries without a repository owner. On macOS,
`check` also consumes `macos-session-health status --format json` to warn when
the launch agent is missing or unloaded, the last snapshot is stale, or recent
notification deliveries keep failing.

```bash
mise run check
mise run check -- --json
mise run check -- --strict
```

Warnings do not fail the normal command because different hosts intentionally
have different capabilities. `--strict` treats warnings as failures.

When Skillshare is present, `check` also runs `skillshare doctor --json`. It
does not treat the executable, YAML file, and source directory alone as proof
that synchronization is healthy. Missing or empty generated shell directories
are likewise reported as not ready.

`mise run lint` inspects repository paths, Mackup mappings, and dangling
symlinks. `mise run verify` adds Python formatting, type checking, behavior
tests, and the shell gate: `mise run shell` runs Bash and Zsh syntax checks
plus ShellCheck over the tracked shell files outside `reference/`.

## Host updates

Updating installed tools is an explicit mutation, separate from configuration
inspection. Preview the exact commands first:

```bash
mise run update -- --dry-run
mise run update -- --dry-run --json
mise run update
```

The task discovers supported updaters on `PATH`, reports missing tools as
skipped, applies available updates in a stable order, and continues independent
steps after a failure. Any failed step makes the command exit non-zero. Current
steps cover Homebrew metadata and packages, global mise tools and shims,
GitHub CLI extensions, tldr pages, Yazi packages, Sprite's update check, Amp,
Tigris, and Pi extensions. It deliberately does not run `brew cleanup`,
`brew autoremove`, or `mise prune`; removal and pruning require a separate,
explicit operation.

`update` does not pull this repository, install missing tools, run Skillshare,
or write live configuration back into `reference/`. Inspect the resulting host
state separately:

```bash
mise run runtime -- --dry-run
mise run check
mise run diff
```

## Generated runtime

Shell runtime is maintained separately from tool updates and configuration
restore. Preview the owned operations, then apply them explicitly:

```bash
mise run runtime -- --dry-run
mise run runtime -- --dry-run --json
mise run runtime
```

The runtime task generates Zsh initialization and completion files for commands
already on `PATH`, removes stale completion files in its fixed ownership set,
clones or fast-forwards the three Zsh plugins consumed by `modules/zsh/env.zsh`,
downloads checksum-pinned Zellij WASM files, rebuilds the bat cache, and removes
Zsh completion dumps. `--offline` limits an apply to local generation and cache
maintenance. It never runs Skillshare or writes host inventory.

The two source-built binaries are an explicit, slower sub-operation:

```bash
mise run runtime -- --build --dry-run
mise run runtime -- --build
```

This clones or fast-forwards `ipruning/atuin` and `craftzdog/op-cache` under the
ignored `generated/sources/`, builds them with Cargo, and atomically installs the
artifacts into `generated/bin/`. Any other binary placed there must name its own
owner; `mise run check` reports unknown binaries.

## Standalone tools

`bag-mode`, `macos-session-health`, and `macos-maxfiles` are self-installing
modules. Each executable owns its command interface, installation, removal,
tests, and generated launchd configuration. Their source and usage remain under
the corresponding `modules/<tool>/` directory.

Ordinary commands under `modules/bin/` are independent of the dotfiles
inspection tasks. Linux Lite deliberately does not add them to `PATH`. The macOS
shell configuration currently expects this repository at `~/dotfiles`; `mise run
lint` reports when that assumption is false.

## Skillshare

Global harness prompts and AI skills remain owned by the Skillshare source
repository. This repository stores only the reference Skillshare configuration
and reports when its executable, configuration, or source directory is absent.
It does not install or synchronize Skillshare automatically.

The stored configuration synchronizes skills only. Harness extras such as
global `AGENTS.md` or `CLAUDE.md` remain machine-specific because managed hosts
like exe.dev may already own those paths. Before any extras operation, inspect
the exact affected files:

```bash
skillshare diff --json
skillshare sync extras --dry-run --force --json
```

Installing Skillshare, choosing a source repository, and synchronizing skills
are separate operator decisions. Linux Lite reports the missing capability and
stops there; use the Skillshare source repository's current instructions if the
host should gain that capability.

## License

See `LICENSE`.
