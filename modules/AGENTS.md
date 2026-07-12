# Module Guidelines

## Scope

`modules/` stores source files: executable commands, self-installing tools,
command helpers, shell config fragments, Mackup config, and templates. Keep
runtime state and generated local files outside this tree
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
- Do not expose a self-installing module through `modules/bin/`; its installed
  path is the command interface. Run the module source directly only for its
  first installation or an upgrade.
- Generate host-specific plist files during installation. Do not keep another
  plist source file when the executable is already the sole owner of its
  lifecycle.

## Verification

- For script changes, run the relevant CLI directly with representative inputs.
- For self-installing module lifecycle changes, run its test when present,
  validate the dry run, and verify installed `status` after installation.
- Keep verification output focused: report the command, exit status, and the
  behavior that proves the change.
