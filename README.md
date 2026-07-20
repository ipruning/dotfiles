# dotfiles

Personal configuration references and standalone maintenance tools for macOS
and Linux hosts. This repository reports drift and missing capabilities. It
does not automatically overwrite `$HOME` or rebuild an entire machine.

## Repository model

- `reference/` contains the intended examples compared with live files under
  `$HOME`.
- `mackup/` declares which application paths belong to each reference.
- `scripts/` implements typed inspection tasks and explicit maintenance tasks;
  every mutating task previews by default and writes only with `--apply`.
- `modules/bin/` contains independent user commands.
- `modules/<tool>/` contains substantial tools that own their installation and
  removal.
- `generated/` is optional shell runtime state. A missing generated directory
  is a host-health warning, not a reason to mutate the repository.
- `inventory/` contains per-host software snapshots written only by
  `mise run inventory`.

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
mise exec -- uv sync --locked
mise tasks
```

`mise trust` is required because this repository declares a project virtual
environment. `mise install` provides the pinned Python and uv versions, then
`mise exec -- uv sync --locked` materializes the locked project dependencies,
including the pinned Mackup fork, before shell activation makes uv directly
available. Task auto-install is disabled: these two commands form the explicit
bootstrap boundary, and a later `mise run ...` does not quietly download a
missing task tool or project dependency.

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
task that edits shell and Git bootstrap configuration in place; like every
mutating task it previews by default:

```bash
mise run setup -- --profile linux-lite
mise run setup -- --profile linux-lite --apply
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

## Linux Zsh contract

Linux Lite targets Bash, but the full Zsh reference is deliberately safe to
restore on a Linux host as well, so `mise run restore -- zsh` is supported
there. The contract is a split between experience and commands:

- The Zsh *experience* loads on Linux. `.zshrc` sources `modules/zsh/` (aliases,
  environment, completions, plugins) and the generated completion directory
  regardless of platform; the Homebrew block is macOS-only and the clash block
  is Linux-only.
- The user bin and mise shim directories load on every platform. The repository
  *command directories* do not: `.zshenv` prepends `modules/bin` and
  `generated/bin` to `PATH` only under `darwin*`, so a Linux host never gains
  repository commands and can never shadow a system tool — most importantly
  iproute2 `ss`, whose repository namesake is `skillshare-source`.
- The mise configuration reinforces this: it carries no repository bins, and its
  `lockfile_platforms` covers both `macos-arm64` and `linux-x64`, so restoring
  the macOS mise config onto Linux cannot expose a repository command either.

What is not promised: optional tools (atuin, starship, tv) are host-managed and
their integrations degrade silently when the tool is absent. `mise run shell`
reflects the same asymmetry — it syntax-checks Zsh files only where `zsh` is
installed and marks them not-applicable elsewhere rather than failing.

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

The command runs the immutable Mackup fork pinned as a locked git dependency in
`pyproject.toml` (recorded in `uv.lock`), so `mise install` provisions it and no
Mackup fetch happens during inspection. It loads application definitions
directly from `mackup/applications/` and does not install `~/.mackup` links or
change either side.

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
symlinks. Its `path.*` findings are host-relative: a machine-specific path
referenced by tracked configuration is reported OK where it exists and as a
warning on hosts where it does not, so warning counts legitimately differ
between machines running the same commit. `mise run verify` adds Python formatting, type checking, behavior
tests, the standalone module suites on macOS, and the shell gate: `mise run shell`
runs Bash syntax checks and ShellCheck for Bash files. Zsh files receive syntax
checking when `zsh` is available.

## Host updates

Updating installed tools is an explicit mutation, separate from configuration
inspection. Preview the exact commands first:

```bash
mise run update
mise run update -- --json
mise run update -- --apply
```

The task discovers supported updaters on `PATH`, reports missing tools as
skipped, applies available updates in a stable order, and continues independent
steps after a failure. Any failed step makes the command exit non-zero. Current
steps cover Homebrew metadata and packages, global mise tools and shims,
GitHub CLI extensions, tldr pages, Yazi packages, Sprite, Amp,
Claude Code, Codex, Tigris, and Pi extensions. It deliberately does not run
`brew cleanup`,
`brew autoremove`, or `mise prune`; removal and pruning require a separate,
explicit operation.

For mise, the preview first reads the active installed versions and passes that
explicit list to `mise upgrade`; a configured but missing mise tool is not
installed. Other missing CLIs are skipped rather than bootstrapped. Package
managers may still replace package dependencies as part of an ordinary upgrade.

`update` does not pull this repository, run Skillshare, or write live
configuration back into `reference/`. Inspect the resulting host state
separately:

```bash
mise run runtime
```

Review the runtime preview and apply it only when needed. If runtime reports
refreshed Zsh state, apply it and then open a new Zsh or run `exec zsh` to load
the new functions, completions, and plugins:

```bash
mise run runtime -- --apply
exec zsh
```

From the refreshed shell, inspect the resulting host and configuration state:

```bash
mise run check
mise run diff
```

## Generated runtime

Shell runtime is maintained separately from tool updates and configuration
restore. Preview the owned operations, then apply them explicitly:

```bash
mise run runtime
mise run runtime -- --json
mise run runtime -- --apply
```

The runtime task generates Zsh initialization and completion files for commands
already on `PATH`, removes stale completion files in its fixed ownership set,
clones or fast-forwards the three Zsh plugins consumed by `modules/zsh/env.zsh`,
downloads checksum-pinned Zellij WASM files, rebuilds the bat cache, and removes
Zsh completion dumps. `--offline` limits an apply to local generation and cache
maintenance. It never runs Skillshare or writes host inventory; snapshots have
their own explicit task (see Host inventory).

The two source-built binaries are an explicit, slower sub-operation:

```bash
mise run runtime -- --build
mise run runtime -- --build --apply
```

This clones or fast-forwards `ipruning/atuin` and `craftzdog/op-cache` under the
ignored `generated/sources/`, builds them with Cargo, and atomically installs the
artifacts into `generated/bin/`. Any other binary placed there must name its own
owner; `mise run check` reports unknown binaries.

## Host inventory

Inventory snapshots record which software a host had installed at one point in
time. They are tracked under `inventory/<host>/` so history stays reviewable,
and they are only ever written by the explicit task:

```bash
mise run inventory
mise run inventory -- --json
mise run inventory -- --apply
```

The task writes four snapshots per host: `Brewfile` (`brew bundle dump`),
`applications.txt` (`/Applications`), `setapp.txt` (`/Applications/Setapp`),
and `gh_extensions.txt` (`gh extension list`). A collector whose tool or
directory is absent is reported as skipped; a collector that fails or produces
empty output makes the command exit non-zero and leaves the existing snapshot
untouched. Nothing regenerates these files implicitly — a snapshot is as old
as its last committed run, never a claim about current host truth.

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
