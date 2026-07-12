# Module Guidelines

## Scope

`modules/` stores source files: executable commands, self-installing tools,
command helpers, shell config fragments, Mackup config, LaunchDaemon plist
files, and templates. Keep runtime state and generated local files outside this tree
unless the repository already marks those paths as generated files.

## `bin/`

- Put user-facing commands in `modules/bin/`.
- Put shared command helpers in `modules/bin/_lib/`.
- Commands that need common logging, dependency checks, prompts, or timeout
  helpers should source `modules/bin/_lib/load.sh`.
- Domain-specific helper files may source `load.sh` themselves. Commands should
  source the domain helper directly, for example `modules/bin/_lib/mackup.sh`.
- Files under `modules/bin/_lib/` are sourced helpers, not direct commands.
  Keep them non-executable.
- New executable names should use kebab-case. Use `.py` for Python helpers that
  are imported or edited as Python modules; otherwise prefer an executable
  script name without an extension.
- Scripts intended to be invoked directly must be executable and include a
  working shebang.
- Use the repository toolchain: run configured tools through `mise exec --`, and
  use `uv run --script` with PEP 723 metadata for standalone Python scripts.
- CLIs that agents or scripts call should keep stdout parseable and send
  diagnostics to stderr. Prefer `--format json` when another program will read
  the output. On failures, exit non-zero and print the command, setting, or
  file path needed to fix the failure.
- Long-running monitors should store state under `~/Library/Application Support`
  and logs under `~/Library/Logs`. Do not write runtime state into the
  repository.

## Self-installing modules

- A substantial standalone tool may live in `modules/<tool>/` when one
  executable owns its command interface, installation, removal, generated
  launchd configuration, and runbook.
- Keep `modules/bin/<tool>` as a relative symlink to that executable so the
  repository still has one command discovery path.
- Generate host-specific plist files during installation. Do not keep another
  plist source file when the executable is already the sole owner of its
  lifecycle.

## `launchdaemons/`

- Put source plist files for macOS system LaunchDaemons in
  `modules/launchdaemons/`.
- Install these plist files to `/Library/LaunchDaemons/` at runtime.
- Use this directory only for root-owned system-domain jobs. Do not add
  logged-in user-session jobs here.
- Validate plist changes with `plutil -lint`.
- Installed LaunchDaemon plist files must be owned by `root:wheel` and have
  mode `0644`.
- After changing a loaded LaunchDaemon, use
  `sudo launchctl bootout system /Library/LaunchDaemons/<file>.plist` and then
  `sudo launchctl bootstrap system /Library/LaunchDaemons/<file>.plist` so
  launchd rereads the plist.
- Inspect loaded jobs with `sudo launchctl print system/<label>`.
- Keep LaunchDaemons narrow and quiet. Prefer one-shot setup jobs for system
  limits and privileged helpers. A self-installing tool that owns a generated
  LaunchDaemon plist keeps that plist inside its implementation instead.

## Verification

- For script changes, run the relevant CLI directly with representative inputs.
- For self-installing module lifecycle changes, run its own test and verify its
  installed `status` after installation.
- For LaunchDaemon changes, validate the source plist, install it with
  `root:wheel` ownership and `0644` mode, then inspect the loaded job with
  `sudo launchctl print system/<label>`.
- Keep verification output focused: report the command, exit status, and the
  behavior that proves the change.
