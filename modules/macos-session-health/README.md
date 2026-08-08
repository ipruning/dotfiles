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

Install publishes each file atomically after unloading the agent. It does not
roll back a partial update: a failure reports completed files, keeps the agent
unloaded when possible, reports the observed launchd state, and directs the
operator to inspect status and `rerun install`. Uninstall likewise keeps
successful removals and directs the operator to `rerun uninstall` after a
failure. Repeating either command converges the requested state.

## Triage

Start with the incident report and direct process facts:

```zsh
macos-session-health incident --hours 6 --format markdown
pgrep -x syspolicyd | xargs ps -o pid,ppid,stat,%cpu,rss,etime,comm= -p
```

The incident report separates collector runs, health signals, process
resources, passive log matches, and notification decisions. It reports those
facts without deriving a recovery plan. The operator or investigating agent
should interpret them in the context of the current failure.

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
launch failures but does not stop `syspolicyd` RSS or FD growth. This tool does
not terminate applications or system processes; any recovery action must be
chosen explicitly from the observed facts.

## Notifications

Notifications are passive alerts for current warning-or-higher health
signals. The single-file CLI contains its own brrr client; it does not execute a
Skillshare-managed sender. An explicit `BRRR_SECRET` from the environment,
`BRRR_ENV_FILE`, `~/.config/brrr/env`, or `~/.config/notify/brrr.env` takes
precedence over the exe.dev brrr proxy. Notifications identify the host and
summarize impact and action without embedding snapshot IDs or raw signal fields.

When the collector has current health signals, it sends a generic summary with
the snapshot status, sorted signal names, and the exact incident-report
command. One successful-send timestamp enforces the configured minimum
interval. Failed deliveries do not advance it. No signal means no alert;
the tool does not emit a clear-state alert. Notifications never execute
recovery actions. Use the incident report to see emitted and skipped decisions.

The Skillshare guard immediately reports a missing executable, configuration,
configured source, or failed status query. It records the observed command
failure directly instead of maintaining a consecutive-failure state machine.

Each push makes one bounded HTTP attempt with no repeated attempt or second channel. A
failure event records endpoint, authentication mode, HTTP/timeout/error facts,
and the exact `notify-test --dry-run` and incident checks. Notification-channel
health remains a SQLite signal and `mise run check` finding, but is not sent
through the channel already known to be unhealthy. `status --format json` is
the authoritative delivery-health report.

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
git diff --check
modules/macos-session-health/macos-session-health install
macos-session-health status --format json
```

Wait for a new persisted collector run, then confirm its `snapshot_end` status
is `ok` in the incident report.
