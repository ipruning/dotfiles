# CursorUIViewService watchdog runbook

This module mitigates unbounded memory growth in Apple's
`com.apple.TextInputUI.xpc.CursorUIViewService`. It does not disable the macOS
text-cursor UI and does not claim to fix the underlying Apple implementation.

The observed failure on macOS 26.6.1 left one service process alive for more
than three days with about a 9.4 GB physical footprint and over 8 GB swapped.
`ps` RSS substantially understated that footprint. Community reports describe
the same typing lag and non-responsive process on Sonoma and Sequoia, but Apple
has not published a root-cause statement or supported feature flag. The
[Apple Support thread](https://discussions.apple.com/thread/255668660) records
the recurring symptom; an [Apple Developer Forums
thread](https://developer.apple.com/forums/thread/764085) also contains a
user-reported UI-freeze risk when terminating the service. Neither source is an
official fix.

## Safety model

The installed LaunchAgent runs one short check every 30 seconds; it is not a
resident `KeepAlive` daemon. It monitors only unless installation explicitly
opts into automatic recycling. An automatic recycle requires all of these
conditions:

- the exact Apple executable has one process owned by the current user;
- `/usr/bin/footprint` reports at least 512 MiB in one check; and
- no recycle has been attempted in the previous five minutes.

Recovery uses the launchd-owned service target:

```text
user/<uid>/com.apple.TextInputUI.xpc.CursorUIViewService
```

It confirms launchd still owns the measured PID and repeats the footprint check
immediately before sending `SIGKILL` to that exact PID. It then verifies that
the old PID disappeared. If launchd starts a replacement immediately, it also
verifies the exact Apple executable path and replacement footprint. Failure is
logged and enters the same cooldown; it never uses a name-based PID loop.

Direct `SIGKILL` is necessary because macOS rejects `launchctl kickstart -k`
for this Apple XPC service while System Integrity Protection is enabled.
Automatic recycling remains opt-in because terminating the service may still
briefly disrupt or freeze the UI, and PID identity cannot be asserted
atomically between inspection and signaling. The undocumented global
FeatureFlags override is not used.

The Accessibility timeout probe from the legacy command remains deliberately
removed: one timeout is not sufficient authorization to recycle a service, and
an unattended LaunchAgent may have different TCC behavior from an interactive
shell.

## Lifecycle

Inspect the live process and preview installation before changing the host:

```zsh
modules/cursoruiviewservice-watchdog/cursoruiviewservice-watchdog check --json
modules/cursoruiviewservice-watchdog/cursoruiviewservice-watchdog install --json
modules/cursoruiviewservice-watchdog/cursoruiviewservice-watchdog install --auto-recycle --json
```

Install and verify the user LaunchAgent:

```zsh
modules/cursoruiviewservice-watchdog/cursoruiviewservice-watchdog install --auto-recycle --apply
cursoruiviewservice-watchdog status --json
```

Manual recycling previews by default and bypasses the automatic threshold and
cooldown gates only with explicit application:

```zsh
cursoruiviewservice-watchdog recycle --json
cursoruiviewservice-watchdog recycle --apply --json
```

Removal also previews by default. Apply it to remove the executable, runtime
copy, and LaunchAgent while retaining history:

```zsh
cursoruiviewservice-watchdog uninstall --json
cursoruiviewservice-watchdog uninstall --apply
```

Runtime state lives under
`~/Library/Application Support/cursoruiviewservice-watchdog/`; launchd stdout
and stderr live under `~/Library/Logs/cursoruiviewservice-watchdog/`.

## Removal condition

This is a bounded workaround for an operating-system-owned failure mode; the
public reports do not establish Apple's root cause. Remove it only after a
later macOS release keeps a fresh `CursorUIViewService` below 512 MiB
through at least seven days of normal input-source and Caps Lock use, without
typing lag or a non-responsive process. Recheck with `check --json`, uninstall
the LaunchAgent, then delete this module and its `mise run test-modules` entry.

## Verification

```zsh
modules/cursoruiviewservice-watchdog/cursoruiviewservice-watchdog-test
modules/cursoruiviewservice-watchdog/cursoruiviewservice-watchdog install --json
mise run verify
```
