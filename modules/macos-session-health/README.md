# macos-session-health runbook

Use this runbook when apps bounce in the Dock, open without a usable window, or
shell commands fail to spawn. The collector records user-session diagnostics in
`~/Library/Application Support/macos-session-health/health.sqlite3` and writes
logs under `~/Library/Logs/macos-session-health/`.

App-bundle checks default to `/Applications/ChatGPT.app`. Pass global
`--app PATH` before the subcommand to replace that selection; repeat the flag
to inspect multiple bundles. Empty paths are rejected before collection.

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

After a partial failure, use `modules/macos-session-health/macos-session-health`
from the repository for status and retries: the installed wrapper may be absent
or incomplete. Preview a repeated install with `install --dry-run` first.

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

`query`, `events`, `trend`, and `incident` open SQLite read-only. A missing
database is an error, not a reason to create an empty database.

`trustd` resource deltas track each user and executable separately. Changes in
which instance has the largest RSS do not indicate a restart. A PID change for
the same identity still emits `process_pid_changed`; RSS growth and limits are
checked for every sampled instance. The first sample after this upgrade creates
new per-instance baselines without comparing the previous aggregate baseline.

## Capture the next failure

Leave the LaunchAgent running. It samples once per minute by default, retains
14 days, and scans the previous ten minutes of targeted system logs every five
minutes. Error-level signals trigger a bounded broader log excerpt (at most once
per 30 minutes). `incident` includes raw matched log lines, spawn-check exit codes
and timing, Node REPL inventories, and notification decisions.

When an app bounces, audio fails, or a command cannot spawn, note the local time,
app, triggering action, and visible symptom before restarting it. From this
repository, preserve the surrounding hour:

```zsh
mkdir -p outputs
stamp=$(date +%Y%m%d-%H%M%S)
macos-session-health incident --hours 1 --limit 200 --format json > "outputs/session-$stamp.json"
macos-session-health incident --hours 1 --limit 200 --format markdown > "outputs/session-$stamp.md"
```

These commands only read the database. Check the report's newest snapshot time:
a stale collector cannot diagnose its own outage. A sub-minute failure without
a matching retained system log can escape these samples; `status=ok` does not
prove the user-visible app worked. Inspect `status --format json` and the
collector logs if the snapshots stopped. Share only relevant excerpts after
checking local paths and system-log content.

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

A warning is sent once per active issue (check, signal, and affected object).
Its severity increasing to error or critical sends immediately, even during the
warning cooldown. Unchanged issues remain in SQLite and do not repeat every ten
minutes. A completed recheck without that issue rearms it; skipped or failed
checks do not establish recovery. Failed deliveries do not acknowledge an issue.
The ten-minute cooldown applies to new warnings. The notification says
`status=warning` when the collector has warnings but no error; the snapshot's
`status=ok` still means no error-level failure was detected.

AudioComponentRegistrar is an on-demand Mach service with pressured exit.
An installed but idle service and its inactive/removed/unloaded lifecycle log
messages are diagnostic evidence, not alerts. Missing services, failed lookups,
and actual audio errors still alert. `codex_node_repl_many` is informational:
count alone does not establish a leak. Each snapshot records its PID, parent PID,
state, CPU, RSS, and elapsed time without process arguments. Process-table pressure,
spawn failures, and resource error thresholds retain their alerts.

`zombies_present` excludes one zombie per live
`sshd-session: <user> [postauth]` parent. Only the first observation or a count
above the successfully notified peak can trigger a push. The peak resets after a
successful process inventory observes zero, never on a skipped or failed probe.
Notifications never execute
recovery actions. Use the incident report to see emitted and skipped decisions.

The Skillshare guard immediately reports a missing executable, configuration,
configured source, or failed status query. It records the observed command
failure directly instead of maintaining a consecutive-failure state machine.

Codex 信任列表中的目录可以在项目删除后继续保留。目录不存在时，只记录
`codex_trusted_project_root` 的 `root_exists=false`，不产生健康告警或推送。
无需为消除通知删除 Codex 信任配置。仍存在的目录若 `.git` 无效，或信任配置
无法解析，仍会触发告警。

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

This dry-run uses the invoking shell's credentials. Installation does not
persist shell `BRRR_SECRET` or `BRRR_ENV_FILE` settings into the LaunchAgent.
For the installed agent, use a default credential file listed above (or the
proxy) and check `status --format json`: it ignores caller credential overrides
and includes the last recorded delivery result.

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
