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

Git and mise are the only bootstrap requirements. mise provides the pinned
Python and uv versions; uv provides the locked project dependencies.

```bash
git clone <your-repo-url> ~/dotfiles
cd ~/dotfiles
mise install python uv
mise tasks
```

`mise tasks` is the authoritative command list. The main inspection interface
is:

```bash
mise run diff
mise run check
mise run lint
mise run verify
```

## Configuration drift

`mise run diff` compares `reference/` with the corresponding paths under the
current `$HOME`. It reports locations and file kinds, never file contents.
Ordinary drift exits successfully; an incomplete inspection, such as an
unreadable path or invalid Mackup response, exits non-zero.

```bash
mise run diff
mise run diff -- git
mise run diff -- --json
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

## License

See `LICENSE`.
