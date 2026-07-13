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
or synchronize Skillshare extras. The Bash module adds `~/.local/bin`,
`modules/bin`, and `generated/bin` to `PATH`, then activates mise in interactive
shells. The managed block is placed before Ubuntu's non-interactive early
return, so direct SSH commands also receive the durable PATH without interactive
shell initialization.

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
install `~/.mackup` links and cannot back up, restore, or apply files.

When a live configuration should become the reference, copy or edit that
specific file deliberately and rerun `diff`. When the reference should become
live, edit that live file deliberately. Git protects repository changes; it
does not roll back `$HOME` or system state.

## Host health

`mise run check` reports required runtimes and optional capabilities separately.
Current checks cover the mise/uv/Python bootstrap, private Git configuration,
Skillshare, Television, and optional generated shell directories.

```bash
mise run check
mise run check -- --json
mise run check -- --strict
```

Warnings do not fail the normal command because different hosts intentionally
have different capabilities. `--strict` treats warnings as failures.

When Skillshare is present, `check` also runs `skillshare doctor --json`. It
does not treat the executable, YAML file, and source directory alone as proof
that synchronization is healthy. Generated shell directories containing only
their tracked `.gitkeep` are likewise reported as empty, not ready.

`mise run lint` inspects repository paths, Mackup mappings, and dangling
symlinks. `mise run verify` adds Python formatting, type checking, and behavior
tests.

## Standalone tools

`bag-mode`, `macos-session-health`, and `macos-maxfiles` are self-installing
modules. Each executable owns its command interface, installation, removal,
tests, and generated launchd configuration. Their source and usage remain under
the corresponding `modules/<tool>/` directory.

Ordinary commands under `modules/bin/` are independent of the dotfiles
inspection tasks. Shell startup currently expects this repository at
`~/dotfiles`; `mise run lint` reports when that assumption is false.

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

On a new Linux machine, the complete public setup is:

```bash
curl -fsSL https://raw.githubusercontent.com/runkids/skillshare/main/install.sh | sh
mkdir -p ~/Developer/ipruning ~/.config/skillshare
git clone https://github.com/ipruning/skills.git ~/Developer/ipruning/skills
test -e ~/.config/skillshare/config.yaml || \
  cp ~/dotfiles/reference/.config/skillshare/config.yaml \
    ~/.config/skillshare/config.yaml
skillshare sync --json
skillshare doctor --json
```

The `test` guard prevents an existing host-specific configuration from being
overwritten. Private tracked repositories require that machine's authorized
GitHub access. Current Skillshare versions may return exit status 0 while
`install --json` contains a non-empty `failed` array; `mise run check` catches
the resulting doctor warning, and automation must inspect that array rather
than trusting the process status alone.

## License

See `LICENSE`.
