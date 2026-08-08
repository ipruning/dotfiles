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

`install` and `upgrade` leave the service stopped. An upgrade never restarts a
previously enabled service; verify the installation and start it explicitly. Run
`bag-mode help COMMAND` for the current command options and exit-code contract.

Version 3 uses one atomically published recovery obligation containing both the
captured values and controller identity. If the legacy `recovery-snapshot` file
exists, `upgrade` delegates restoration to the installed old controller, removes
the obsolete snapshot only after restoration succeeds, and remains stopped.
Direct `install` and `start` refuse to switch schemas.

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

## Notifications

Bag mode does not notify for routine start, lid, or clean-stop transitions.
Notifications are reserved for crashes, unsafe power or recovery states, and
the battery minimum that forces a stop. Configure any executable implementing
the generic notifier contract with `bag-mode notifier set PATH`; upgrades do
not remove an existing notifier.

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

After changing the module, run the isolated source checks before any operator-
authorized lifecycle work:

```zsh
modules/bag-mode/bag-mode-test
bash -n modules/bag-mode/bag-mode
```
