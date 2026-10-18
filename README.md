# dotfiles

Personal configuration references and maintenance tasks for macOS and Linux
hosts. The repository reports drift and missing capabilities; it never
overwrites `$HOME` or rebuilds a machine on its own.

[`AGENTS.md`](AGENTS.md) defines the layout (`scripts/`, `reference/`,
`mackup/`, `shell/`, `commands/`, `services/`, `manual/`, `generated/`,
`inventory/`), the shared status and severity vocabulary, and the
Operator/Executor handoff. This README describes how to operate the tasks.

## Daily maintenance

| Intent | Preview | Apply |
| --- | --- | --- |
| Inspect this host | `mise run check` | read-only |
| Compare reference and live configuration | `mise run diff` | read-only |
| Install locked tools, plugins, and generated shell state | `mise run update` | `mise run update -- --apply` |
| Advance the shared baselines (maintenance host) | `mise run upgrade-tools` | `mise run upgrade-tools -- --apply` |
| Upgrade everything and verify | `mise run upgrade-all` | `mise run upgrade-all -- --apply` |
| Link mise configuration and install missing baseline tools | `mise run mise-sync` | `mise run mise-sync -- --apply` |
| Regenerate `generated/` | `mise run generate` | `mise run generate -- --apply` |
| Diagnose failures | `mise run doctor` | read-only |

`upgrade-all -- --apply` advances the shared mise and Yazi baselines, updates Homebrew formulae and casks plus the other host tools, then runs the full verification gate. Without `--apply`, it previews both update stages. It does not commit or push repository changes.

Every mutating task previews by default and writes only with `--apply`. Discover
the [command index](commands/README.md) and services in [Services](#services);
their flags are their own.

The baseline flow is one-writer: advance it in one checkout, verify and commit,
then pull on the other hosts and run `update`.

## Start

Git and mise are the only bootstrap requirements. Bootstrap a host that dotfiles
manages with:

```bash
curl -fsSL https://mise.run | MISE_SELF_UPDATE_MINIMUM_RELEASE_AGE=0s sh
export PATH="$HOME/.local/bin:$PATH"
git clone https://github.com/ipruning/dotfiles.git ~/dotfiles
cd ~/dotfiles
mise trust
mise install --locked actionlint fd jq python ripgrep rumdl shellcheck tombi uv zizmor
mise exec -- uv sync --locked
mise run mise-sync
mise run mise-sync -- --apply
```

- The installer takes the latest mise; `min_version` (2026.9.18) in both mise
  configs is only a compatibility floor for version-3 lockfiles and npm
  sidecars. Keep the standalone binary at `~/.local/bin/mise` as the single
  owner (it supports `mise self-update`); a second copy from Homebrew or apt can
  bind shell activation to the wrong binary.
- Name the repository tools explicitly. A bare `mise install --locked` also
  loads the global configuration and installs every host-wide tool.
- `settings.auto_install = false` makes these two install commands the only
  bootstrap boundary: later task, exec, and command-not-found paths fail instead
  of downloading. Do not split that gate into narrower settings.
- `uv sync --locked` installs the Python dependencies, including the pinned
  Mackup fork. Python tasks use `.venv`'s interpreter directly, because mise
  inserts its PATH entries where the shims directory sits (after `/usr/bin` on
  Omarchy).
- On Linux, `diff` and `check` select the `linux-lite` profile; macOS selects
  `macos`. Pass `--profile full` to audit every stored reference.

### Host-local ownership policy

When the operating system or another platform owns mise or global configuration,
create the untracked `~/.config/dotfiles/policy.toml` before running any task,
and skip `mise-sync --apply`:

```toml
mode = "audit-only"
mise_path = "/usr/bin/mise"
```

`audit-only` keeps previews, `diff`, `check`, `lint`, and verification, but
rejects `--apply` (and the underlying `apply_*`/`execute_*` operations) before
anything is written. `mise_path` names the host's canonical mise, so a
package-managed binary is not reported as an extra installation. `check` marks
dotfiles-owned shell integration, shared mise capabilities, and generated state
as not applicable; mise health, duplicate owners, Skillshare, and permissions
still apply. An invalid policy fails closed. The policy does not govern
`commands/` or `services/`.

## Development checks

`mise run verify` is the gate for local work and GitHub Actions (Linux x64 and
macOS ARM64): Ruff, ty, tombi (TOML), rumdl (Markdown), pytest, the macOS service suites, `lint`,
the shell gate, and actionlint plus zizmor for workflows. CI fails if verification changes any file. Amp Orbs
provision through `.agents/setup` and check offline with `.agents/resume`; they
never apply host configuration.

- `lint` inspects repository paths, Mackup mappings, and dangling symlinks. Its
  `path.*` findings are host-relative, so warning counts differ between hosts on
  the same commit.
- `shell` runs `bash -n` and ShellCheck on Bash files, and `zsh -n` where zsh is
  installed (elsewhere those files are reported as not applicable).

## Configuration drift

`diff` compares profile-relevant files under `reference/` with their `$HOME`
paths by location and file kind, never contents. Drift exits 0; an incomplete
inspection exits non-zero. It runs the locked Mackup fork against
`mackup/applications/` without touching either side.

```bash
mise run diff
mise run diff -- git --json
```

`restore` and `adopt` are application-scoped mirrors; there is no restore-all.

- `restore -- <app> --apply` moves each changed live path into
  `~/.local/state/dotfiles/restore-backups/` and links it to the reference.
- `adopt -- <app> --apply` copies live files into `reference/` (removing
  reference files whose live counterpart is gone). It writes only inside the
  repository and refuses while affected reference paths have uncommitted
  changes or ignored data. Never commit secrets.

Applications that save by atomic replace (LinearMouse, Zed, Herdr, btop) turn a
link back into a file or write through it; reconcile with `restore` or `adopt`.
Host-specific environment belongs in `~/.zshenv.private.zsh`, which the
reference `.zshenv` sources.

## Linux Lite

```bash
mise run setup-linux-lite
mise run setup-linux-lite -- --apply
exec bash
```

This adds one marked block to `~/.bashrc` (before Ubuntu's non-interactive
early return) that loads `shell/bash/init.bash`, and adds `~/.private.gitconfig`
to Git's includes. Re-running it rewrites the block in place. The Bash module
puts `~/.local/bin` and mise's shims on `PATH`, activates mise, and guards
Starship, Atuin (which owns `Ctrl-R`), and Zoxide (`j`). It provides `..`,
`...`, and a path-segment `Ctrl-W`. It does not create an identity, install
tools, clone private repositories, sync Skillshare, or expose `commands/`.

The Linux Lite profile checks Git, mise, Herdr, Atuin, and btop configuration,
and reports missing optional capabilities as warnings (`--strict` makes them
failures).

The full Zsh reference is safe on Linux (`mise run restore -- zsh`): `.zshrc`
loads `shell/zsh/` and generated completions on every platform, while
`.zshenv` adds `commands/` to `PATH` only on macOS, so repository commands never
shadow Linux system tools. Optional integrations degrade when their tools are
absent.

## Global mise baseline

`reference/.config/mise/config.toml` and its multi-platform `mise.lock` are the
shared personal toolset: interactive commands wanted on every personal host.
Project tools belong to that project's mise config. Services use a distribution
package or `<canonical-mise> -C <project> exec -- <tool>`, never global shims.

`mise-sync --apply` backs up and links the live config to the reference,
installs the locked Go, Node, Ruby, and Rust runtimes first (so `cargo:` builds
do not race an older compiler), installs the whole locked baseline, and rebuilds
shims with `~/.local/bin` first on `PATH`. A tool declared only in the live
config blocks apply until you decide whether it joins the baseline, moves to its
project, or is removed. On an audit-only host the preview is a counterfactual
comparison, not a verdict. On macOS 27 the tool step disables Cargo release
stripping, because stripped proc-macro libraries fail to load until stable Rust
ships LLVM 22.1.8; remove the override once the locked Atuin builds without it.

`update` installs the locked versions of tools already present; `upgrade-tools`
runs `mise upgrade --bump` for tools declared as `latest` (exact pins and refs
are held) and `ya pkg upgrade` when `~/.config/yazi/package.toml` links to this
checkout:

```bash
mise run upgrade-tools -- --apply
mise run verify
git diff -- reference/.config/mise reference/.config/yazi/package.toml
```

Commit the referenced `reference/.config/mise/locks/` sidecars with the lock and
drop sidecars it no longer references. Artifact-capable backends are locked by
URL and checksum; `gem:`, `go:`, and `npm:` are locked by version.

Tool owners:

| Tool | Owner |
| --- | --- |
| Hunk, Lazygit, Lazydocker, Starship, Zoxide, Skillshare | shared mise baseline on every platform |
| Atuin | shared baseline, compiled per host from the pinned fork revision; only `config.toml` is restored |
| btop | Homebrew on macOS; the shared baseline on Linux (Debian's 1.2/1.3 rewrite the linked config) |
| Herdr | official installer at `~/.local/bin/herdr` (`curl -fsSL https://herdr.dev/install.sh \| sh`) |
| Pi | official installer under `~/.pi/agent/install` (`curl -fsSL https://pi.dev/install.sh \| sh`); to migrate from mise, remove its declaration, `mise uninstall --all pi`, and `mise reshim` first |
| GitHub CLI, Codex | the host (Homebrew, APT, Omarchy); version differences are not drift |

## Host health and doctor

`check` reports required executables and optional capabilities for the selected
profile; warnings pass unless `--strict`. It verifies the canonical mise binary,
other mise copies, shim targets, and generated activation. It parses Skillshare's
YAML without running the CLI (`skillshare status` and `doctor` may migrate or
write, so run them explicitly). On macOS it reads `macos-session-health status`.

`doctor` aggregates `check`, `diff`, a `mise-sync` preview, and `lint`, then
probes `mise doctor`, `brew doctor`, and `pueue status` when present. It skips
`skillshare doctor`, which writes. `clean` previews `mise prune --tools`,
`brew autoremove`, and `brew cleanup`, and runs them only with `--apply`.

## Host updates

`update --apply` runs, in order and independently of earlier failures:

- `brew update`, `brew upgrade --formula`, and `brew upgrade --cask` (no sudo);
- `mise self-update` (standalone owner only), `mise install --locked` for
  installed shared tools, and `mise reshim --force`;
- `gh extension upgrade --all`, `tldr --update`, and `ya pkg install`;
- native self-updaters for Sprite, Amp, Claude Code, Tigris, Herdr, Pi, Codex,
  Droid, Grok, Claude Science, Notion `ntn`, Rotom, and `jh`, only when the
  executable lives in that tool's own install root (mise, Homebrew, and unknown
  owners are skipped). Tigris and `ntn` must be user installs in
  `~/.local/bin`; `jh upgrade` needs a valid `jh auth login --remote` session.
  Inside a Herdr session (`HERDR_ENV=1`), Herdr's self-update is skipped;
- finally `generate --offline`.

`update` never changes the shared declaration, installs missing tools, restores
configuration, pulls Git, cleans versions, or restarts services or shells. A
live declaration that differs from the reference makes the mise step report the
conflict. In JSON mode stdout holds one report; failures name the command,
directory, exit code, and output tail.

## Generated state

`generated/` is an ignored local cache (`fd -HI generated` to inspect). Shell
startup only loads it.

`generate` writes shell integrations and completions with the host's mise, and
restores pinned Zsh plugins and Zellij WASM assets. Unchanged outputs report
`unchanged`; clean plugins at their pinned commit skip fetching; dirty plugin
checkouts are reported, not reset; generator errors keep existing files.
`--offline` skips network assets and LLM completion resolution, so a first setup
needs an online `generate`. Open a new shell after files change.

## Host inventory

`inventory -- --apply` writes `inventory/<host>/` snapshots of installed
software (Brewfile, applications, gh extensions, Setapp). A failed collector or
an invalid empty result leaves the snapshot untouched. A snapshot is as old as
its last committed run.

## Services

Each service executable owns its interface, installation, removal, tests, and
generated launchd configuration; its runbook owns operation and recovery:

- [`macos-session-health`](services/macos-session-health/README.md): alerts on
  persistent session symptoms and keeps incident evidence;
- [`macos-maxfiles`](services/macos-maxfiles/README.md): machine-wide file limit
  lifecycle and rollback;
- [`cursoruiviewservice-watchdog`](services/cursoruiviewservice-watchdog/README.md):
  bounded recovery from Apple's text-cursor service memory growth.

The macOS shell configuration expects the checkout at `~/dotfiles`; `lint`
reports when it is elsewhere.

## Skillshare

The Skillshare source repository owns global harness prompts and skills; this
repository stores only the portable configuration (`mise run restore --
skillshare`). Its source lives at `~/.config/skillshare/skills` on every host.

One authoring host runs `skillshare update --all`, reviews, and publishes the
source; other hosts pull it and run `skillshare sync`. This keeps
`.metadata.json` and copied external skills from diverging.

`skillshare sync` writes skills; `sync --all` also writes agents, extras
(`~/.codex`, `~/.claude`), MCP settings, and hooks, but not plugins. Before any
sync, preview everything:

```bash
skillshare sync --all --global --dry-run --force --json
```

Targets merge, so `local > 0` with `pruned == 0` keeps local entries; only
`pruned > 0` plans deletion and needs explicit confirmation. In `skillshare diff
--json`, `action: remove` with `is_sync: false` describes direction, not a
planned deletion. A failed preview means inspection is incomplete. Amp's global
guidance lives in Amp's own settings.

## License

See `LICENSE`.
