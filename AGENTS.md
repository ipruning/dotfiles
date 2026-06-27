# Repository Guidelines

## Project Structure & Module Organization

- `modules/` contains hand-edited source for configs, scripts, and templates. Common areas include `modules/bin/`, `modules/zsh/`, `modules/mackup/`, `modules/launchagents/`, and `modules/surfingkeys/`.
- `home/` is a Mackup snapshot tree. Avoid hand edits unless you are changing backup output. Tracked shell bootstrap files under `home/` (`.zshenv`, `.zprofile`, `.zshrc`) are the exception; edit them when changing Mackup-restored shell startup behavior. The ignored `home/.zshenv.private.zsh` file is generated locally from `home/.zshenv.private.tpl.zsh` when 1Password is available.
- `.mise/tasks/` contains simple task entrypoint scripts; `.mise/scripts/` contains shared helpers and bash implementations used by TOML-defined tasks.
- `generated/` contains generated output for files with a regeneration path, such as completions, functions, plugins, and host snapshots. Delete these files only when regeneration is available.
  - `generated/plugins/` contains third-party Zsh plugins (git-ignored).
  - `generated/docs/<hostname>/` stores host-specific snapshots (brew/apps/extensions).

## Build, Test, and Development Commands

- `mise tasks` lists available tasks.
- `mise run init` installs or updates tooling, plugins, and Mackup links.
- `mise run restore` restores the Mackup snapshot into the system.
- `mise run backup` runs `mackup backup --force` to snapshot configs into `home/`.
- The Skillshare source repo owns agent prompt files such as `~/.codex/AGENTS.md`, `~/.claude/CLAUDE.md`, and `~/.config/amp/AGENTS.md`. It stores them under `extras/{codex,claude,amp}/` and distributes them with `skillshare sync extras`. Do not add these files to Mackup or regenerate them from this repo.
- `mise run sync` pulls plugins, regenerates shell completions/functions, runs Skillshare sync (skills + extras), and writes host package/app snapshots.
- `mise run up` updates Homebrew-managed packages, mise tools, and selected developer CLIs.
- `mise run zsh-profile [runs] [warmup]` profiles Zsh startup (requires `hyperfine`).

## Skillshare Prompt Boundary

- Keep only the Skillshare bootstrap hooks for `restore` and `sync` in this repo. Edit global harness prompts in the Skillshare source repo.
- Do not reintroduce `modules/agents/`, `mise run agents`, or prompt snapshots under `home/.codex/`, `home/.claude/`, or `home/.config/amp/`.
- Mackup should not manage `~/.codex/AGENTS.md`, `~/.claude/CLAUDE.md`, or `~/.config/amp/AGENTS.md`; keep `modules/mackup/.mackup/agents.cfg` limited to independent agent configs such as `.pi/agent/AGENTS.md`.
- Mackup should manage Skillshare's routing config (`~/.config/skillshare/config.yaml`) through `modules/mackup/.mackup/skillshare.cfg`, so a restored machine can find the skills/extras source repo and prompt targets.
- When changing where Skillshare installs prompt files, update the Skillshare source repo and the active Skillshare config together, then verify from this repo with `skillshare extras list --json` and `skillshare sync --all --dry-run --json`.
- For extras that target tool root directories containing unrelated files (for example `~/.codex`, `~/.claude`, or `~/.config/amp`), keep the configured `mode: copy`; do not switch to `merge` unless you have verified the pruning behavior for that target.

## Coding Style & Naming Conventions

- Bash task scripts use `#!/usr/bin/env bash`, `set -euo pipefail`, and 2-space indentation.
- Put parsing, selection, and formatting logic in functions. Keep file, process, and network I/O at the script edge.
- New scripts in `modules/bin/` should be executable and use kebab-case names. Python helpers may end in `.py`.
- Templates use `*.tpl.*`; secrets belong in `*.private.*` files (ignored by git).

## Testing Guidelines

- This repo does not define an automated test suite.
- Verify changes by running the relevant `mise` task and confirming that changes under `generated/` and `home/` match the task you ran.
- For script changes, run the script directly with representative inputs.

## Commit & Pull Request Guidelines

- Follow Conventional Commits: `type(scope): summary` (e.g. `chore(brew): update packages`).
- **Always include a scope**: use the tool or directory name, such as `brew`, `mise`, `zsh`, `ghostty`, `bin`, `yazi`, or `docs`.
- Multiple scopes: `chore(brew,mise): ...` (cap at 3).
- Keep commits focused and scoped to a single logical change.
- Write concise, specific summaries. Do not use filler words.
- PRs should include: a short summary, impacted paths (for example `modules/zsh/`), and commands run.

## Performance Optimization Guidelines

- Shell prompts such as Starship run frequently during interactive use. Prefer fast tools over strict parsers.
- Tool speed hierarchy: **shell builtins** (`[ -f ]`, `command -v`) > **awk/sed/grep** (~2ms) > **compiled CLI** (yq/jq ~8ms) > **heavy CLI** (gh/modal/uvx ~20-400ms).
- Always benchmark with `hyperfine` before and after the change. Do not assume a change is faster. Measure it.
- When changing conditional logic (`when`/`if-elif`), enumerate all input combinations in a truth table to catch mismatches between `when` and `command` branches.
- Acceptable trade-off: sacrifice strict format parsers (yq/jq) for regex-based matching (awk) on files you control (dotfiles, CLI configs).

## Security & Configuration Tips

- Never commit secrets. Use templates and `*.private.*` files. Tracked files under `home/` must not contain secrets; ignored materialized files such as `home/.zshenv.private.zsh` may be generated locally from templates.
