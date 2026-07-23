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
mise install --locked fd jq python ripgrep shellcheck uv
mise exec -- uv sync --locked
mise tasks
mise run mise-sync
mise run mise-sync -- --apply
```

This repository deliberately standardizes both macOS and Linux on the
standalone executable at `~/.local/bin/mise`. Do not install a second copy with
Homebrew, apt, or another package manager: package-managed mise has a different
update owner and may leave generated shell activation bound to the wrong
binary. The upstream installer uses this standalone path by default, and this
installation supports `mise self-update`.

`mise trust` is required because this repository declares a project virtual
environment. The explicit `mise install --locked ...` command requires every
project tool to have a URL and checksum for the current platform in
`mise.lock`. `mise exec -- uv sync --locked` then materializes the locked Python
dependencies, including the pinned Mackup fork, before shell activation makes
uv directly available. Mise auto-install is disabled for task, exec, and
command-not-found paths: these two commands form the explicit bootstrap
boundary, and later commands fail instead of quietly downloading a missing
tool or project dependency.

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

Choose the operation by intent; `mise tasks` and each task's `--help` remain the
authoritative command interfaces:

| Intent | Documentation |
| --- | --- |
| Bootstrap a small Linux host | [Linux Lite setup](#linux-lite-setup) |
| Compare, restore, or adopt configuration | [Configuration drift](#configuration-drift) |
| Converge global mise tools across hosts | [Global mise convergence](#global-mise-convergence) |
| Inspect host and repository health | [Host health](#host-health) |
| Update installed tools | [Host updates](#host-updates) |
| Refresh generated shell state | [Generated runtime](#generated-runtime) |
| Record installed software | [Host inventory](#host-inventory) |
| Operate a self-installing module | [Standalone tools](#standalone-tools) |
| Inspect Skillshare ownership | [Skillshare](#skillshare) |

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

The Linux Lite drift profile observes Git, mise, and Skillshare configuration.
Skillshare remains optional: a missing executable, configuration, or source is
a warning for a human or AI operator to evaluate, not a setup action.

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
- The repository mise configuration carries no repository bins. Its committed
  lockfile contains URLs and checksums for both `macos-arm64` and `linux-x64`,
  so bootstrap uses the same reviewed tool artifacts on both platforms.

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
`pyproject.toml` and recorded in `uv.lock`. The bootstrap command `mise exec --
uv sync --locked` provisions it, so no Mackup fetch happens during inspection.
It loads application definitions directly from `mackup/applications/` and does
not install `~/.mackup` links or change either side.

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

## Global mise convergence

The tracked global `config.toml` and multi-platform `mise.lock` are the shared
personal interactive baseline for macOS and Linux hosts. They do not own
systemd services, cron jobs, workers, or project runtimes: those must use a
system package or invoke the owning project's Mise config explicitly. Installed
tools, download caches, shims, and generated shell functions remain local
runtime state and are rebuilt from the shared declaration rather than
synchronized through Git.

Preview the complete convergence first:

```bash
mise run mise-sync
mise run mise-sync -- --json
```

An apply backs up and links the live mise configuration to `reference/`, runs
the canonical executable's `install --locked` against `$HOME`, then rebuilds
shims with `~/.local/bin` forced to the front of `PATH`:

```bash
mise run mise-sync -- --apply
```

Before replacing the live declaration, `mise-sync` compares its `[tools]`
entries with the tracked baseline. Any live-only tool blocks apply and is named
in the report. Decide whether to add it to the shared baseline, move it to its
project or service owner, or remove it explicitly; `mise-sync` never makes that
destructive choice. An unreadable or invalid live configuration also blocks
apply because ownership cannot be established safely.

This operation deliberately does not pull Git, self-update mise, update the
lockfile, remove an alternate package-managed mise, or install tools during
shell startup. A canonical binary older than the repository's hard minimum
must still be updated directly before any repository task can launch.
Backends that support lockfile URLs are artifact-locked; package-manager
backends such as `gem:`, `go:`, and `npm:` are version-locked but retain their
upstream package manager's artifact and integrity semantics.

Global tools should be interactive commands wanted on every personal host.
Project tools belong in that project's Mise configuration. Long-running Linux
services should use the distribution package when appropriate, or an explicit
`~/.local/bin/mise -C <project> exec -- <tool>` command; they must not depend on
global shims. A genuinely host-specific tool is an explicit exception, not a
second global configuration truth.

## Host health

`mise run check` reports required executables and optional capabilities
separately. The selected profile determines the current check set, which the
plain or JSON report lists directly. On macOS, the report also consumes
`macos-session-health status --format json` to detect an unavailable collector
or notification path.

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
are likewise reported as not ready. The report also verifies that
`~/.local/bin/mise` is a real executable rather than a package-manager symlink,
warns when another mise installation exists on `PATH` or at a common system
location, verifies that mise-owned shims target the canonical executable, and
checks that generated Zsh activation names only the canonical executable.

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

The task discovers most supported updaters on `PATH`, reports missing tools as
skipped, applies available updates in a stable order, and continues independent
steps after a failure. Mise is the exception: its self-update, tool upgrade,
and reshim steps always invoke `~/.local/bin/mise` explicitly. The self-update
runs without the unrelated plugin update side effect. The preview is the
authoritative list of supported updaters and the exact commands available on
the current host. Any failed step makes the command exit non-zero. It
deliberately does not run `brew cleanup`, `brew autoremove`, or `mise prune`;
removal and pruning require a separate, explicit operation.

For mise, the preview records the active installed tool versions. An apply
updates the standalone CLI first, then passes that explicit list to
`mise upgrade`; a configured but missing mise tool is not installed. Other
missing CLIs are skipped rather than bootstrapped. Package managers may still
replace package dependencies as part of an ordinary upgrade.

When the live global mise files are linked to `reference/`, the mise tool
upgrade may refresh the tracked lockfile. Run `update --apply` on a checkout
where that declaration change will be reviewed and committed. Other hosts use
`mise-sync --apply` to consume the committed lock without bumping it.

A hard `min_version` failure happens before mise can launch this repository's
`update` task. In that bootstrap case, update the canonical binary directly
with `~/.local/bin/mise self-update`, then run the task normally.

`update` does not pull this repository, run Skillshare, or write live
configuration back into `reference/`. Inspect the resulting host state
separately:

```bash
mise run runtime
```

Review the runtime preview and apply it only when it plans relevant Zsh changes.
If the apply reports refreshed Zsh state, open a new Zsh or run `exec zsh` to
load the new functions, completions, and plugins:

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

The runtime task owns generated shell functions, completions, plugins, caches,
and other declared runtime artifacts. Its preview is the authoritative list of
planned operations on the current host. `--offline` limits an apply to local
generation and cache maintenance. It never runs Skillshare or writes host
inventory; snapshots have their own explicit task (see Host inventory).
Generated files are a cache: shell startup sources them but does not regenerate
them. The mise generator always invokes `~/.local/bin/mise` by absolute path, so
the cached activation remains stable across self-updates and across macOS and
Linux hosts.

Repository-owned source builds are an explicit, slower sub-operation:

```bash
mise run runtime -- --build
mise run runtime -- --build --apply
```

This refreshes the sources named by the runtime plan under the ignored
`generated/sources/`, builds them with their declared commands, and atomically
installs the artifacts into `generated/bin/`. Any other binary placed there
must name its own owner; `mise run check` reports unknown binaries.

## Host inventory

Inventory snapshots record which software a host had installed at one point in
time. They are tracked under `inventory/<host>/` so history stays reviewable,
and they are only ever written by the explicit task:

```bash
mise run inventory
mise run inventory -- --json
mise run inventory -- --apply
```

The preview is the authoritative list of collectors, destinations, and skipped
host capabilities. A failed collector or an invalid empty result makes the
command exit non-zero and leaves the existing snapshot untouched. Collectors
whose domain permits zero items instead write an empty snapshot, replacing any
stale non-empty result. Nothing regenerates these files implicitly — a snapshot
is as old as its last committed run, never a claim about current host truth.

## Standalone tools

`bag-mode`, `macos-session-health`, and `macos-maxfiles` are self-installing
modules. Each executable owns its command interface, installation, removal,
tests, and generated launchd configuration. Their local runbooks own the
module-specific operating and recovery decisions:

- [`bag-mode`](modules/bag-mode/README.md): closed-lid operation, restoration,
  and safe removal;
- [`macos-session-health`](modules/macos-session-health/README.md): incident
  diagnosis and guarded recovery;
- [`macos-maxfiles`](modules/macos-maxfiles/README.md): machine-wide limit
  lifecycle, rollback, and reboot behavior.

Ordinary commands under `modules/bin/` are independent of the dotfiles
inspection tasks. Linux Lite deliberately does not add them to `PATH`. The macOS
shell configuration currently expects this repository at `~/dotfiles`; `mise run
lint` reports when that assumption is false.

## Skillshare

Global harness prompts and AI skills remain owned by the Skillshare source
repository. This repository stores only the reference Skillshare configuration
and reports when its executable, configuration, or source directory is absent.
It does not install or synchronize Skillshare automatically.

The default `skillshare sync` operation synchronizes skills. The stored
configuration also declares opt-in extras targets under `~/.config/amp`,
`~/.codex`, and `~/.claude`; an explicit extras sync writes those global
harness directories. Before that external write, inspect the exact affected
files:

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
