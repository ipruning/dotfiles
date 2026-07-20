# macos-maxfiles runbook

Use this runbook when managing the machine-wide launchd `maxfiles` limit. The
single-file CLI installs itself and a generated LaunchDaemon; it does not depend
on a tracked plist.

## Lifecycle

Preview the exact target and paths before authorizing the system-wide change:

```zsh
modules/macos-maxfiles/macos-maxfiles install --dry-run
modules/macos-maxfiles/macos-maxfiles install
macos-maxfiles status --json
```

Installation requires sudo. Success means the executable and LaunchDaemon are
installed, the daemon is loaded, and `status` reports `limits_satisfied: true`.
The hard limit reported by launchd may be numeric or `unlimited`.

## Rollback and removal

Install and uninstall back up both managed files before changing them. A failed
transaction attempts to restore the files, prior loaded state, and prior
effective limits. If rollback itself fails, the diagnostic names a retained
backup directory; keep that directory until the host is repaired.

```zsh
macos-maxfiles uninstall --yes
```

Successful uninstall removes the executable and LaunchDaemon. The current
effective limit remains in the running system until the next reboot; uninstall
does not claim to lower it immediately.

## Maintenance

After changing the module, verify the generated plist, effective-limit readback,
transaction rollback, and removal path through the public suite:

```zsh
modules/macos-maxfiles/macos-maxfiles-test
modules/macos-maxfiles/macos-maxfiles install --dry-run
macos-maxfiles status --json
```
