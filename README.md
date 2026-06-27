# README

<!--rehype:style=font-size: 38px; border-bottom: 0; display: flex; min-height: 260px; align-items: center; justify-content: center;-->

[![jaywcjlove/sb](https://wangchujiang.com/sb/lang/english.svg)](README.md) [![jaywcjlove/sb](https://wangchujiang.com/sb/lang/chinese.svg)](README.zh-cn.md)

<!--rehype:style=text-align: center;-->

Personal dotfiles and workstation bootstrap repo.

The repo uses three file roles:

- **`modules/` contains hand-edited source.** Put reusable scripts, templates, shell fragments, Mackup config, launchd config, and non-dotfile app config here.
- **`home/` contains Mackup snapshots.** Mackup copies files between this tree and `$HOME`. Do not use it as an authoring directory, except for tracked shell bootstrap files under `home/` (`.zshenv`, `.zprofile`, `.zshrc`). The ignored `home/.zshenv.private.zsh` file is generated locally from `home/.zshenv.private.tpl.zsh` when 1Password is available.
- **`generated/` contains generated output** for files with a regeneration path, such as completions, functions, plugins, and host snapshots.
  - `generated/plugins/` contains third-party ZSH plugins (git-ignored).
  - `generated/docs/<hostname>/` stores host-specific snapshots (brew/apps/extensions).

Global harness prompts and AI skills are managed in the Skillshare source repo. This repo only bootstraps their sync during `restore` and `sync`; start from **`AGENTS.md`** for dotfiles-specific operating rules.

## Quick start

### Prerequisites

- macOS (this repo currently contains a lot of macOS app configs: Karabiner, Aerospace, Mos, etc.)
- `git`
- Tasks assume:
  - `mise` (task runner)
  - `uv` (for `uvx mackup ...`)
  - `gum` (task logs, confirmation prompts, and spinner output)
- Task-specific:
  - `init`: `curl` and `op` (1Password CLI) for env injection
  - `backup` / `restore`: `mackup` (invoked via `uvx`, which will install it if missing)
- Optional:
  - `brew` (package installation; host snapshots live under `generated/docs/<hostname>/`)

### Clone

```bash
git clone <your-repo-url> ~/dotfiles
cd ~/dotfiles
```

### Arch Linux note: 1Password CLI beta for `openv`

`modules/zsh/env.zsh` contains `openv`, which uses `op environment read`.

On some Arch setups:

- `/usr/bin/op` (stable) may be too old and not include `environment` commands.
- A manually downloaded beta binary in `$HOME` may fail desktop integration with errors like
  `connection reset` / `PipeAuthError(NoCreds)`.

Use this setup so both app integration and `environment read` work:

```bash
# 1) Download beta package using stable op
mkdir -p ~/.cache/op
PATH=/usr/bin:$PATH op update --channel beta --directory ~/.cache/op

# 2) Extract
zip="$(ls -t ~/.cache/op/op_linux_*_v*.zip | head -n1)"
unzip -o "$zip" -d ~/.cache/op

# 3) Install with correct owner/group/mode (important)
# Use /usr/bin/install explicitly (don't rely on shell alias/function/path shadowing)
sudo /usr/bin/install -o root -g onepassword-cli -m 2755 ~/.cache/op/op /usr/local/bin/op

# 4) Verify
hash -r
op --version
ls -l /usr/local/bin/op
op environment read --help >/dev/null
```

Expected `ls -l` shape:

- owner/group: `root onepassword-cli`
- mode includes setgid: `-rwxr-sr-x` (`2755`)

Quick runtime checks:

```bash
op signin --account my.1password.com
openv-longbridge
# safer verification: print only variable names, not secret values
env | rg '^LONGPORT_' | cut -d= -f1
```

### Run tasks (preferred)

Most tasks are exposed through `mise run ...`. Simple tasks may live directly in
`.mise/tasks/*.sh`; longer or environment-sensitive tasks are defined in
`.mise/config.toml` and run `.mise/scripts/*.sh` via `bash` so `mise` does not
directly exec scripts that mutate shell, Mackup, or mise-related state.

List tasks:

```bash
mise tasks
```

Run a task:

```bash
mise run init
mise run restore
mise run backup
mise run sync
mise run up
mise run zsh-profile
```

If you do not use `mise`, you can also run the scripts directly:

```bash
./.mise/tasks/init.sh
./.mise/scripts/restore.sh
./.mise/tasks/backup.sh
./.mise/scripts/sync.sh
./.mise/tasks/up.sh
./.mise/tasks/zsh-profile.sh
```

> Notes:
>
> - Scripts are authoritative for command behavior.

## Repository contract

These are the invariants that keep the repo understandable over time:

1. **Reusable dotfile module source lives in `modules/`**
   - Add or edit curated configs, templates, and scripts there. Task entrypoints and shared task scripts live under `.mise/`.
   - Things in `modules/` should be reviewable, stable, and portable.

2. **`home/` is a Mackup snapshot**
   - Mackup writes to this tree during backup and restores from it during restore.
   - Do not hand-edit files under `home/` unless you want to change what Mackup will back up or restore.
   - Exception: tracked shell bootstrap files under `home/` (`.zshenv`, `.zprofile`, `.zshrc`) are intentionally edited when changing Mackup-restored shell startup behavior. Ignored `home/.zshenv.private.zsh` is generated locally from `home/.zshenv.private.tpl.zsh` when 1Password is available.

3. **`generated/` is generated output**
   - Shell completions and functions are regenerated by `sync`.
   - `generated/plugins/` contains third-party ZSH plugins (git-ignored, cloned by `init`).
   - `generated/docs/<hostname>/` stores host-specific snapshots.

4. **Secrets never enter Git**
   - Use `*.private.*` files that are ignored, or template files like `*.tpl.*`.
   - Tracked files under `home/` must not contain secrets.
   - Ignored materialized files such as `home/.zshenv.private.zsh` may be generated locally from templates.

## Layout

### Top-level

| Path                        | Meaning                                                                                                   | Role                        |
| --------------------------- | --------------------------------------------------------------------------------------------------------- | --------------------------- |
| `.mise/tasks/`              | Simple task entrypoint scripts                                                                            | Source                      |
| `.mise/scripts/`            | Shared helpers and bash implementations for TOML-defined tasks                                             | Source                      |
| `modules/`                  | Hand-edited source for reusable scripts, templates, shell fragments, Mackup config, and launchd config     | Source                      |
| `home/`                     | Mackup snapshot of selected files under `$HOME`                                                           | Snapshot                    |
| `generated/`                | Generated output; `docs/` is tracked, while `bin/`, `completions/`, `functions/`, and `plugins/` are not   | Generated output            |
| `AGENTS.md`                 | Operating contract for agents working in this dotfiles repo                                               | Source                      |
| `pyproject.toml`, `uv.lock` | Python project environment: direct dependency constraints in `pyproject.toml`, resolved versions in `uv.lock` | Source / lockfile           |

### `modules/`

Common patterns used in this repo:

- `modules/bin/` — personal CLI entrypoints / wrappers (e.g., python scripts and short commands)
- `modules/zsh/` — zsh modular config fragments + templates (private env template included)
- `modules/mackup/` — Mackup configuration (`.mackup.cfg` + per-app cfg fragments)
- `modules/surfingkeys/` — browser automation config (Surfingkeys)

### `home/`

`home/` mirrors real paths under `$HOME`, including:

- dotfiles: `.zshrc`, `.gitconfig`, etc.
- XDG configs: `.config/*`
- macOS app support paths: `Library/Application Support/*`, `Library/Preferences/*`

Because this directory is a Mackup snapshot, it may contain:

- files created/updated by apps
- timestamps / backups (which should typically be excluded/ignored)
- tracked shell bootstrap files (`.zshenv`, `.zprofile`, `.zshrc`) that define Mackup-restored shell startup behavior
- ignored local secret materializations such as `.zshenv.private.zsh`, generated from tracked templates before Mackup restore

If you see noise such as `.DS_Store` or auto-backups inside `home/`, prefer to ignore/exclude them to keep diffs meaningful.

## Workflows

### 1) Day-to-day edits

- Prefer editing **`modules/`** (source), except tracked shell bootstrap files under `home/` when changing Mackup-restored shell startup behavior
- Apply changes to your machine via your own linking mechanism
- `sync` regenerates shell completions/functions, refreshes third-party plugin clones, runs Skillshare sync for skills/extras, and writes host snapshots under `generated/docs/<hostname>/`
- `up` updates Homebrew-managed packages, mise tools, and selected developer CLIs
- Refresh `home/` via `backup` task when you want to record the current machine state into the Mackup snapshot

Typical loop:

```bash
# edit source modules
$EDITOR modules/...

# apply/link to live system
mise run sync

# snapshot changes into home/ via Mackup
mise run backup
```

### 2) New machine bootstrap

Typical flow:

```bash
mise run init
mise run restore
mise run sync
```

Where:

- `init` sets up baseline tooling
- `restore` optionally generates ignored private materializations such as `home/.zshenv.private.zsh`, pulls the Mackup snapshot into the correct locations, then syncs Skillshare extras such as global harness prompt files
- `sync` regenerates shell completions/functions, refreshes third-party plugin clones, runs Skillshare sync for skills/extras, and writes host snapshots

### 3) Host snapshots

Host snapshots live under:

```text
generated/docs/<hostname>/
```

Examples:

- `brew_dump.txt`
- `applications.txt`, `setapp.txt`
- `gh_extensions.txt`

These are intentionally host-specific and are expected to change over time.
They are host-specific snapshots (brew/apps/gh extensions, etc.), not config.
Homebrew is tracked as a single `brew bundle dump` output; derived reports such
as leaves or explicitly requested formulae are not kept.

## Python dependency policy

Standalone Python scripts use PEP 723 metadata and pin their runtime packages in the script header. They may support an older Python than the repo development environment. The repo development environment uses `pyproject.toml` for direct dependency constraints and `uv.lock` for resolved versions. Do not copy current package versions into prose; read them from the script header or `uv.lock`.

## Agents and skills

Global harness prompt files such as `~/.codex/AGENTS.md`, `~/.claude/CLAUDE.md`, and `~/.config/amp/AGENTS.md` live in the Skillshare source repo under `extras/{codex,claude,amp}/`. `skillshare sync extras` distributes them. This repo only stores the Skillshare routing config (`~/.config/skillshare/config.yaml`) through Mackup so restored machines know where to sync from.

Dotfiles keeps only the bootstrap hooks that call Skillshare during `restore` and `sync`. See **`AGENTS.md`** for this repo's operating contract.

## License

See `LICENSE`.

## ChangeLog

- 2026-01-02 Update README
- 2025-06-24 Updated README with latest tools, structure, and comprehensive documentation
- 2025-06-23 Complete rewrite of README with comprehensive documentation
- 2022-05-25 Update README
- 2022-03-01 Make the repo public
