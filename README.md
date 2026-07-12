# README

<!--rehype:style=font-size: 38px; border-bottom: 0; display: flex; min-height: 260px; align-items: center; justify-content: center;-->

[![jaywcjlove/sb](https://wangchujiang.com/sb/lang/english.svg)](README.md) [![jaywcjlove/sb](https://wangchujiang.com/sb/lang/chinese.svg)](README.zh-cn.md)

<!--rehype:style=text-align: center;-->

Personal dotfiles and workstation setup repo.

The repo uses three file roles:

- **`modules/` contains source files.** Put reusable scripts, templates, shell fragments, Mackup config, launchd config, and app config here.
- **`home/` contains the Mackup backup tree.** Mackup copies files between this tree and `$HOME`. Do not edit files here, except tracked shell startup files (`.zshenv`, `.zprofile`, `.zshrc`) when changing restored shell behavior. The ignored `home/.zshenv.private.zsh` file is generated from `home/.zshenv.private.tpl.zsh`.
- **`generated/` contains generated files.** This includes completions, shell functions, plugins, and host inventory files.
  - `generated/plugins/` contains third-party Zsh plugins (git-ignored).
  - `generated/docs/<hostname>/` stores host inventory files for Homebrew, apps, and extensions.

Skillshare manages global harness prompts and AI skills from its own source repo. This repo runs Skillshare during `restore` and `sync`.

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
  - `brew` (package installation; host inventory files live under `generated/docs/<hostname>/`)

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

### Run commands

Use `mise run ...` after cloning. Each mise task runs a command in `modules/bin/`.
After `modules/bin` is on `PATH`, the same commands can be run directly.

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
mise run doctor
mise run zsh-profile
```

If you do not use `mise`, you can also run the commands directly:

```bash
modules/bin/dotfiles-init
modules/bin/dotfiles-restore
modules/bin/dotfiles-backup
modules/bin/dotfiles-sync
modules/bin/dotfiles-up
modules/bin/dotfiles-doctor
modules/bin/dotfiles-zsh-profile
```

### Standalone bag-mode

`modules/bag-mode/bag-mode` is a self-installing, single-file macOS utility,
exposed in the repository as `modules/bin/bag-mode`. It keeps
a MacBook awake with its lid closed, restores its captured settings when
stopped, and uses a LaunchDaemon to supervise one privileged controller.

Copy that one file to another Mac, then run:

```bash
brew install brightness
chmod +x bag-mode
./bag-mode install
bag-mode start
bag-mode status
```

Humans and AI agents start from the same progressively disclosed help:

```bash
./bag-mode --help
./bag-mode install --help
```

The install help contains the dependency, sudo handoff, safe installation
order, and machine-verifiable success criteria. Automation can consume
`bag-mode doctor --strict --json` and `bag-mode status --json`; unsupported
options fail with exit code `2` instead of being ignored.

Installation keeps the user CLI at `/usr/local/bin/bag-mode`, but the
LaunchDaemon executes a separate root-owned controller from
`/Library/PrivilegedHelperTools`. A writable PATH directory therefore cannot
replace the executable that launchd runs as root.

`status` keeps independent facts independent:

- `enabled` is the request to keep the controller running.
- `phase` is `stopped`, `starting`, `running`, or `recovery_required`.
- `recovery_required` means the controller exited before captured settings
  were restored.
- `brightness_pending` means power settings are already restored, but the
  built-in display is unavailable.

Stop and restore the settings captured at startup:

```bash
bag-mode stop
```

When macOS hides the built-in panel while the lid is closed, `stop` restores
the power settings and records `brightness_pending=true` instead of discarding
the brightness target. Open the lid and run `bag-mode recover`; starting
bag-mode again with the lid open also applies the pending target. `stop` and
`recover` return exit code `69` while brightness remains pending.

Notifications are optional. A generic notifier implements the contract shown
by `bag-mode help notifier`. To install a brrr sender without retaining a
dependency on its Skill directory:

```bash
bag-mode notifier install-brrr /path/to/brrr-send.sh
bag-mode notifier test
```

The sender is copied into the user's Application Support directory. The
controller does not read Skillshare directories at runtime.

### Standalone macos-maxfiles

`modules/macos-maxfiles/macos-maxfiles` owns the machine-wide launchd maxfiles
setting. It generates and installs its LaunchDaemon instead of keeping a bare
plist in the repository:

```bash
macos-maxfiles install --dry-run
macos-maxfiles install
macos-maxfiles status --json
```

## Repository Rules

These rules keep file ownership clear:

1. **Edit source files in `modules/`**
   - Put curated configs, templates, shell fragments, and dotfiles commands there.
   - `modules/bin/dotfiles-*` contains command behavior. Mise tasks call those commands.

2. **Treat `home/` as Mackup data**
   - `backup` writes current user config into `home/`.
   - `restore` copies files from `home/` into `$HOME`.
   - Edit tracked shell startup files in `home/` only when changing restored shell startup behavior.
   - `home/.zshenv.private.zsh` is ignored and generated from `home/.zshenv.private.tpl.zsh`.

3. **Treat `generated/` as generated files**
   - `sync` regenerates shell completions and functions.
   - `generated/plugins/` contains third-party Zsh plugins (git-ignored, cloned by `init`).
   - `generated/docs/<hostname>/` contains host inventory files.

4. **Secrets never enter Git**
   - Use `*.private.*` files that are ignored, or template files like `*.tpl.*`.
   - Tracked files under `home/` must not contain secrets.
   - Ignored materialized files such as `home/.zshenv.private.zsh` may be generated locally from templates.

## Layout

### Top-level

| Path                        | Meaning                                                                                                   | Kind                        |
| --------------------------- | --------------------------------------------------------------------------------------------------------- | --------------------------- |
| `mise.toml`                  | Mise task definitions that call `modules/bin/dotfiles-*` commands                                          | Source file                 |
| `modules/`                  | Source files for scripts, templates, shell fragments, Mackup config, and launchd config                    | Source files                |
| `home/`                     | Mackup backup tree for selected files under `$HOME`                                                       | Backup data                 |
| `generated/`                | Generated files; `docs/` is tracked, while `bin/`, `completions/`, `functions`, and `plugins/` are not     | Generated files             |
| `AGENTS.md`                 | Instructions for agents working in this repo                                                              | Source file                 |
| `pyproject.toml`, `uv.lock` | Python dependency inputs and resolved versions                                                            | Source file / lockfile      |

### `modules/`

Common patterns used in this repo:

- `modules/bin/` — shell commands and Python commands
- `modules/<tool>/` — substantial self-installing tools exposed through a
  relative symlink in `modules/bin/`
- `modules/zsh/` — zsh modular config fragments + templates (private env template included)
- `modules/mackup/` — Mackup configuration (`.mackup.cfg` + per-app cfg fragments)
- `modules/surfingkeys/` — browser automation config (Surfingkeys)

### `home/`

`home/` stores Mackup backups for paths under `$HOME`, including:

- dotfiles: `.zshrc`, `.gitconfig`, etc.
- XDG configs: `.config/*`
- macOS app support paths: `Library/Application Support/*`, `Library/Preferences/*`

Because this directory is Mackup data, it may contain:

- files created/updated by apps
- timestamps and app backups
- tracked shell startup files (`.zshenv`, `.zprofile`, `.zshrc`) that define restored shell behavior
- ignored local secret files such as `.zshenv.private.zsh`

If you see noise such as `.DS_Store` or auto-backups inside `home/`, prefer to ignore/exclude them to keep diffs meaningful.

## Workflows

### 1) Day-to-day edits

- Prefer editing `modules/`, except tracked shell startup files under `home/`
- Apply changes with the relevant command
- `sync` regenerates shell completions/functions, refreshes third-party plugin clones, runs Skillshare sync for skills/extras, and writes host inventory files under `generated/docs/<hostname>/`
- `up` updates Homebrew-managed packages, mise tools, and selected developer CLIs
- Run `backup` when you want Mackup to copy current user config into `home/`

Typical loop:

```bash
# edit source files
$EDITOR modules/...

# apply/link to live system
mise run sync

# copy current user config into home/ through Mackup
mise run backup
```

### 2) New machine setup

Typical flow:

```bash
mise run init
mise run restore
mise run sync
```

Where:

- `init` installs baseline tools and plugin files
- `restore` generates private files when possible, restores Mackup files, and syncs Skillshare extras
- `sync` regenerates shell completions/functions, refreshes third-party plugin clones, runs Skillshare sync, and writes host inventory files

### 3) Host inventory

Host inventory files live under:

```text
generated/docs/<hostname>/
```

Examples:

- `brew_dump.txt`
- `applications.txt`, `setapp.txt`
- `gh_extensions.txt`

These files are host-specific and change over time. They are inventory, not config.
Homebrew is tracked as a single `brew bundle dump` output; derived reports such
as leaves or explicitly requested formulae are not kept.

## Python dependency policy

Standalone Python scripts use PEP 723 metadata and pin their runtime packages in the script header. They may support an older Python than the repo development environment. The repo development environment uses `pyproject.toml` for direct dependency constraints and `uv.lock` for resolved versions. Do not copy current package versions into prose; read them from the script header or `uv.lock`.

## Agents and skills

Global harness prompt files such as `~/.codex/AGENTS.md`, `~/.claude/CLAUDE.md`, and `~/.config/amp/AGENTS.md` live in the Skillshare source repo under `extras/{codex,claude,amp}/`. `skillshare sync extras` copies them into tool config directories. This repo stores only the Skillshare config (`~/.config/skillshare/config.yaml`) through Mackup.

`restore` and `sync` run Skillshare so prompt files match the Skillshare source repo.

## License

See `LICENSE`.

## ChangeLog

- 2026-01-02 Update README
- 2025-06-24 Updated README with latest tools, structure, and comprehensive documentation
- 2025-06-23 Complete rewrite of README with comprehensive documentation
- 2022-05-25 Update README
- 2022-03-01 Make the repo public
