# README

<!--rehype:style=font-size: 38px; border-bottom: 0; display: flex; min-height: 260px; align-items: center; justify-content: center;-->

[![jaywcjlove/sb](https://wangchujiang.com/sb/lang/english.svg)](README.md) [![jaywcjlove/sb](https://wangchujiang.com/sb/lang/chinese.svg)](README.zh-cn.md)

<!--rehype:style=text-align: center;-->

Personal dotfiles and workstation bootstrap repo.

This repo is intentionally organized around **long-term stable semantics**:

- **`modules/` is the source of truth** for curated “meta-config”, reusable configuration modules, and configs that are *not* naturally dotfiles.
- **`home/` is a Mackup-managed snapshot tree**. It is the *materialized output* of backup/restore (i.e., copied in/out by Mackup). Treat it as “backed-up artifacts”, not the canonical authoring location.
- **`generated/` is disposable**. Anything here can be regenerated.
- **`vendor/` is pinned third-party payload** (plugins/binaries) with explicit lifecycle and upgrades.

If you want to manage Agents / Skills / Prompts inside this repo, start from **`AGENTS.md`**.

## Quick start

### Prerequisites

- macOS (this repo currently contains a lot of macOS app configs: Karabiner, Aerospace, Mos, etc.)
- `git`
- Optional but recommended:
  - `mise` (task runner / bootstrap)
  - `mackup` (backup/restore config files)
  - `brew` (package installation; host inventory snapshots live under `inventory/`)

### Clone

```bash
git clone <your-repo-url> ~/dotfiles
cd ~/dotfiles
````

### Run tasks (preferred)

Tasks live in `.mise/tasks/*.sh`.

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
```

If you do not use `mise`, you can also run the scripts directly:

```bash
./.mise/tasks/init.sh
./.mise/tasks/restore.sh
./.mise/tasks/backup.sh
./.mise/tasks/sync.sh
```

> Notes:
>
> * Exact behavior is defined by the scripts themselves; this README documents the intended semantics and contract.

## Repository contract (the “do not drift” rules)

These are the invariants that keep the repo understandable over time:

1. **Authoring happens in `modules/`**

   * Add/edit your curated configs, templates, scripts, and “meta config” there.
   * Things in `modules/` should be reviewable, stable, and portable.

2. **`home/` is not canonical source**

   * `home/` is a Mackup storage target (a snapshot tree).
   * Prefer not to hand-edit files under `home/` unless you *explicitly* want to change what Mackup will back up/restore.

3. **`generated/` is safe to delete**

   * Shell completions/functions and generated bins belong here.
   * The repo should contain a way to regenerate these outputs (task scripts / tooling).

4. **`vendor/` is where third-party payload lives**

   * Prefer to pin versions and keep upgrades explicit.
   * `vendor/` should not contain personal secrets.

5. **Secrets never enter Git**

   * Use `*.private.*` files that are ignored, or template files like `*.tpl.*`.
   * Keep machine-local secrets outside the repo whenever possible.

## Layout

### Top-level

| Path                                           | Meaning                                                                                  | Lifecycle                   |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------- | --------------------------- |
| `.mise/tasks/`                                 | Bootstrap / backup / restore / sync tasks                                                | Source (hand-edited)        |
| `modules/`                                     | **Canonical** meta-config modules, reusable configs, non-dotfile configs, helper scripts | Source (hand-edited)        |
| `home/`                                        | **Mackup snapshot tree** for dotfiles + app configs (copied by Mackup)                   | Artifact (managed by tools) |
| `generated/`                                   | Generated/disposable outputs (bins, completions, functions)                              | Artifact (regeneratable)    |
| `vendor/`                                      | Pinned third-party binaries/plugins                                                      | Managed (explicit upgrades) |
| `inventory/hosts/`                             | Host-specific inventories / dumps (brew, apps, extensions, etc.)                         | Artifact (periodic refresh) |
| `AGENTS.md`                                    | Contract for Agents / Skills / Prompts in this repo                                      | Source                      |
| `pyproject.toml`, `uv.lock`, `.python-version` | Python tooling for scripts/automation in this repo                                       | Source                      |

### `modules/`

Common patterns used in this repo:

* `modules/bin/` — personal CLI entrypoints / wrappers (e.g., python scripts and short commands)
* `modules/zsh/` — zsh modular config fragments + templates (private env template included)
* `modules/mackup/` — Mackup configuration (`.mackup.cfg` + per-app cfg fragments)
* `modules/surfingkeys/` — browser automation config (Surfingkeys)
* (future) `modules/agents/` or `modules/ai/` — agent prompts, skills, evaluations (see `AGENTS.md`)

### `home/`

`home/` mirrors real paths under `$HOME`, including:

* dotfiles: `.zshrc`, `.gitconfig`, etc.
* XDG configs: `.config/*`
* macOS app support paths: `Library/Application Support/*`, `Library/Preferences/*`

Because this directory is meant for **backup/restore materialization**, it may contain:

* files created/updated by apps
* timestamps / backups (which should typically be excluded/ignored)

If you see noise such as `.DS_Store` or auto-backups inside `home/`, prefer to ignore/exclude them to keep diffs meaningful.

## Workflows

### 1) Day-to-day edits

* Prefer editing **`modules/`** (source)
* Apply changes to your machine via `sync` task (or the repo’s linking mechanism)
* Refresh `home/` via `backup` task when you want to record the current machine state into the Mackup snapshot

Typical loop:

```bash
# edit source modules
$EDITOR modules/...

# apply/link to live system
mise run sync

# snapshot changes into home/ via Mackup + inventories
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

* `init` sets up baseline tooling
* `restore` pulls the Mackup snapshot into the correct locations
* `sync` links/applies `modules/` as the canonical layer

### 3) Host inventories

Host snapshots live under:

```text
inventory/hosts/<hostname>/
```

Examples:

* `brew_dump.txt`, `brew_installed.txt`, `brew_leaves.txt`
* `applications.txt`
* `gh_extensions.txt`

These are intentionally host-specific and are expected to change over time.

## Agents / Skills / Prompts

This repo is designed to host all agent-related assets (agents, skills, prompts, evaluation fixtures) **alongside dotfiles**, under clear lifecycle boundaries.

See **`AGENTS.md`** for conventions and a recommended directory layout.

## License

See `LICENSE`.

## ChangeLog

* 2026-01-02 Update README
* 2025-06-24 Updated README with latest tools, structure, and comprehensive documentation
* 2025-06-23 Complete rewrite of README with comprehensive documentation
* 2022-05-25 Update README
* 2022-03-01 Make the repo public
