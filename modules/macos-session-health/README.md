# macos-session-health runbook

Use this runbook when apps bounce in the Dock, open without a usable window, or
shell commands fail to spawn. The collector records user-session diagnostics in
`~/Library/Application Support/macos-session-health/health.sqlite3` and writes
logs under `~/Library/Logs/macos-session-health/`.

## Lifecycle

The single-file CLI owns a small wrapper at `~/.local/bin/macos-session-health`,
a runtime copy under its Application Support directory, and its generated
LaunchAgent. It requires Python 3.11 or newer. Installation records the stable
mise `python/latest` path when available, so the daemon and CLI do not depend on
mise shims or a long-lived uv script environment.

```zsh
modules/macos-session-health/macos-session-health install --dry-run
modules/macos-session-health/macos-session-health install
macos-session-health status --format json
```

`uninstall` removes the command wrapper, runtime copy, and LaunchAgent but
preserves SQLite state and logs:

```zsh
macos-session-health uninstall
```

## Triage

Start with the incident report and a read-only recovery plan:

```zsh
macos-session-health incident --hours 6 --format markdown
macos-session-health recover
pgrep -x syspolicyd | xargs ps -o pid,ppid,stat,%cpu,rss,etime,comm= -p
```

The incident report separates collector runs, health signals, process
resources, passive log matches, and notification decisions. Treat repeated
`syspolicyd_assessment_failure` events together with rising `syspolicyd`
resources as evidence that Gatekeeper or static-code checks are failing.
`maxfiles_soft_low` is context, not proof of the cause.

Use JSON when another command will consume the report:

```zsh
macos-session-health incident --hours 6 --format json
macos-session-health query --signals --limit 30 --format json
macos-session-health events --format json
```

## Safety

Do not restart `syspolicyd` with `launchctl`; SIP blocks that path. Do not run
repeated `spctl`, `codesign`, or high-frequency `lsof` probes during an active
incident because they add work to the failing service. Active `spctl` and
`codesign` probes remain disabled by default.

Do not treat a higher maxfiles limit as the root-cause fix. It reduces secondary
launch failures but does not stop `syspolicyd` RSS or FD growth.

The executable recovery path never closes Codex Desktop. Its read-only report
includes a separate manual command that closes the app; do not copy or run that
command until closing the app is safe. The
`--assume-codex-desktop-closed` flag confirms that precondition but does not
close the app. Do not terminate unrelated Codex CLI sessions.

## Recovery

`recover` without `--execute` is read-only. After Codex Desktop is closed or
confirmed safe to leave closed, execute the guarded restart:

```zsh
macos-session-health recover --execute --assume-codex-desktop-closed
```

Successful recovery has all of these properties:

- the `syspolicyd` PID changes;
- RSS returns from abnormal growth to its normal MiB-scale baseline;
- recent resource and passive-log signals stop increasing;
- app and shell launches work again.

If TERM does not replace the process, retry once with the CLI's KILL option:

```zsh
macos-session-health recover --execute --assume-codex-desktop-closed --signal KILL
```

If macOS rejects direct signal delivery, reboot is the remaining clean recovery.

## Notifications

Notifications are passive alerts for a narrow set of launch-impacting health
signals. The single-file CLI contains its own brrr client; it does not execute a
Skillshare-managed sender. An explicit `BRRR_SECRET` from the environment,
`BRRR_ENV_FILE`, `~/.config/brrr/env`, or `~/.config/notify/brrr.env` takes
precedence over the exe.dev brrr proxy. Notifications identify the host and
summarize impact and action without embedding snapshot IDs or raw signal fields.

The SQLite state machine sends an onset, a changed incident, and one recovery.
It suppresses an unchanged incident regardless of sample count, and records
cooldown or incident-state changes only after successful delivery. Failed onset
and recovery deliveries remain eligible for the next run. Notifications never
execute recovery actions. Use the incident report to see both emitted and
suppressed decisions.

When a push delivery exhausts its retries or brrr is unconfigured, the CLI
posts the same title and message as a local macOS notification through
`osascript` as a last resort, at most once every four hours. `status` additionally reports
`last_snapshot_at`, `last_snapshot_status`, and
`consecutive_delivery_failures` (counting the last 24 hours), which `mise run check` in the dotfiles
repository consumes to detect a silently dead agent or a dead push channel.

Validate the payload and local credential lookup without sending:

```zsh
macos-session-health notify-test --dry-run
```

Process inventories are stored as one aggregate event per inventory instead of
one row per process. Snapshot retention applies to both formats; use the
collector's `--retention-days` option or
`MACOS_SESSION_HEALTH_RETENTION_DAYS` to change its current default. Existing
detailed rows age out normally.

After a storage-format upgrade, reclaim unused SQLite pages without losing
history. The command stops and restarts only this LaunchAgent around `VACUUM`:

```zsh
macos-session-health compact --format json
```

Pass global `--db PATH` before `compact` to compact an offline database without
stopping the installed LaunchAgent.

## Maintenance

After changing the collector, validate its command interface and read-only
outputs before reinstalling it:

```zsh
modules/macos-session-health/macos-session-health --version
modules/macos-session-health/macos-session-health-test
modules/macos-session-health/macos-session-health incident --hours 1 --limit 3 --format json
modules/macos-session-health/macos-session-health recover --format json
git diff --check
modules/macos-session-health/macos-session-health install
macos-session-health status --format json
```

Wait for a new persisted collector run, then confirm its `snapshot_end` status
is `ok` in the incident report.
