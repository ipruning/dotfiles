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

## Verification

- For script changes, run the relevant CLI directly with representative inputs.
- For LaunchAgent changes, validate the source plist and inspect the loaded job
  with `launchctl print gui/$UID/<label>`.
- Keep verification output focused: report the command, exit status, and the
  behavior that proves the change.
