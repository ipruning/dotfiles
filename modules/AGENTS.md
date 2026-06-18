# Module Guidelines

## Scope

`modules/` stores reusable dotfile modules: executable helpers, shell config
fragments, Mackup config, LaunchAgent plist sources, and templates. Keep runtime
state and generated local files outside this tree unless the repository
already marks those paths as generated output.

## `bin/`

- Put user-facing CLI helpers and thin wrappers in `modules/bin/`.
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

## `libexec/`

- Put implementation files behind user-facing wrappers in `modules/libexec/`.
- Keep direct user commands in `modules/bin/`; `modules/libexec/` files may rely
  on their wrapper for runtime selection, environment setup, and stable argv.

## `launchagents/`

- Put source plist files for macOS user LaunchAgents in `modules/launchagents/`.
- Install these plist files to `~/Library/LaunchAgents/` at runtime.
- Use this directory only for user-session jobs that run under the logged-in
  user. Do not add LaunchDaemon or system-domain jobs here.
- Validate plist changes with `plutil -lint`.
- After changing `ProgramArguments` or environment, use
  `launchctl bootout gui/$UID ~/Library/LaunchAgents/<file>.plist` and then
  `launchctl bootstrap gui/$UID ~/Library/LaunchAgents/<file>.plist` so launchd
  rereads the plist. `launchctl kickstart` alone restarts the existing job
  definition and may not pick up plist edits.
- Inspect loaded jobs with `launchctl print gui/$UID/<label>`.
- By default, avoid LaunchAgents that run frequent probes or print repeated
  logs. Disable or rate-limit probes that repeatedly wake, restart, or query
  unstable macOS services.

## `launchdaemons/`

- Put source plist files for macOS system LaunchDaemons in
  `modules/launchdaemons/`.
- Install these plist files to `/Library/LaunchDaemons/` at runtime.
- Use this directory only for root-owned system-domain jobs. Do not add
  logged-in user session jobs here.
- Validate plist changes with `plutil -lint`.
- Installed LaunchDaemon plist files must be owned by `root:wheel` and have
  mode `0644`.
- After changing a loaded LaunchDaemon, use
  `sudo launchctl bootout system /Library/LaunchDaemons/<file>.plist` and then
  `sudo launchctl bootstrap system /Library/LaunchDaemons/<file>.plist` so
  launchd rereads the plist.
- Inspect loaded jobs with `sudo launchctl print system/<label>`.
- Keep LaunchDaemons narrow and quiet. Prefer one-shot setup jobs for system
  limits and privileged helpers; keep long-running user-facing monitors in
  `launchagents/` unless they require root.

## Verification

- For script changes, run the relevant CLI directly with representative inputs.
- For LaunchAgent changes, validate the source plist and inspect the loaded job
  with `launchctl print gui/$UID/<label>`.
- Keep verification output focused: report the command, exit status, and the
  behavior that proves the change.
