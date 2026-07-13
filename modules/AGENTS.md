# Module Guidelines

`modules/` contains independent user commands, shell fragments, templates, and
self-installing maintenance tools. Repository inspection logic belongs in
`scripts/`, not here.

## User commands

- Put user-facing commands in `modules/bin/`.
- Keep command-specific helpers beside their owner. Shared shell helpers under
  `modules/bin/_lib/` must have at least two real callers.
- New executable names use kebab-case. Imported Python helpers use `.py`;
  directly invoked commands use a working shebang and executable mode.
- Agent-facing output stays parseable. Send diagnostics to stderr and provide a
  JSON format when another program consumes the result.
- Runtime state and logs live outside the repository.

## Self-installing modules

A substantial standalone tool may live in `modules/<tool>/` when its executable
owns the command interface, installation, removal, and generated system
configuration. Keep its tests and runbook beside it. Do not add a second wrapper
under `modules/bin/`.

Generate host-specific launchd files during installation rather than tracking a
second plist source. Verify lifecycle changes through the module's public CLI,
including its dry-run installation, tests, installed status, and uninstall
path.

## Verification

Run an ordinary command through its public interface. Repository-wide Python
inspection changes use the tasks documented in the root `AGENTS.md`.

## Structural search cookbook

Use these read-only investigation commands for Python structure:

```sh
ast-grep run -p 'subprocess.$FUNC($$$ARGS)' -l python modules
ast-grep run -p 'subprocess.$FUNC($$$BEFORE, shell=True, $$$AFTER)' -l python modules
ast-grep run -p 'YAML($$$INIT).load($$$ARGS)' -l python modules
```

These are discovery commands, not lint gates. To enforce subprocess shell
policy, prefer Ruff's Bandit S602 rule. Keep text and cross-format configuration
checks in the existing domain checks; do not add `sgconfig.yml` or a persistent
ast-grep gate.
