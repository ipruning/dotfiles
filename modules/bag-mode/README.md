# bag-mode runbook

Use this runbook when a MacBook must keep its active session available with the
lid closed. Stopping bag mode restores the captured power and brightness state;
a stopped service leaves ordinary closed-lid sleep unchanged.

## Lifecycle

Install `brightness` through the host package manager, then validate and install
the module through its own CLI:

```zsh
modules/bag-mode/bag-mode doctor --strict --json
modules/bag-mode/bag-mode install --dry-run
modules/bag-mode/bag-mode install
bag-mode start
bag-mode status --json
bag-mode doctor --strict --json
```

`install` leaves the service stopped. Use `upgrade`, not another bare install,
when replacing an existing installation; it restores the prior running state
only when the service was enabled before the upgrade. Run
`bag-mode help COMMAND` for the current command options and exit-code contract.

## Restoration

`status` separates lifecycle recovery from pending brightness:

- `recovery_required` means the controller exited before restoring captured
  settings. Run `bag-mode recover`.
- `brightness_pending` means power settings are already restored, but the
  built-in display must return before brightness can be applied. Open the lid,
  then run `bag-mode recover`. Exit status 69 preserves this distinction for
  automation.

Do not remove recovery state to silence either condition. It is the material
the controller needs to restore the host.

## Removal

```zsh
bag-mode stop
bag-mode uninstall --yes
```

Uninstall stops the controller and restores captured settings before deleting
system files. It aborts and keeps recovery material when restoration fails or
brightness is still pending. A successful uninstall preserves user logs and
notifier configuration.

## Maintenance

After changing the module, exercise its public lifecycle before reinstalling:

```zsh
modules/bag-mode/bag-mode-test
modules/bag-mode/bag-mode install --dry-run
bag-mode status --json
bag-mode doctor --strict --json
```
