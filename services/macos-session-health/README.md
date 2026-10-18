# macos-session-health runbook

This collector watches a macOS user session for symptoms you would notice, such
as commands that fail to spawn or `syspolicyd` exhausting its resources. It
sends a phone notification only when a symptom persists. Every sample is
recorded in
`~/Library/Application Support/macos-session-health/health.sqlite3`, and logs go
to `~/Library/Logs/macos-session-health/`.

## Lifecycle

The single-file CLI manages three installed files: a small wrapper at
`~/.local/bin/macos-session-health`, a runtime copy under its Application
Support directory, and a LaunchAgent it generates. It requires Python 3.11 or
newer. Installation records the stable mise `python/latest` path when one
exists, so the daemon and the CLI do not depend on mise shims or a long-lived uv
script environment.

```zsh
services/macos-session-health/macos-session-health install
services/macos-session-health/macos-session-health install --apply
macos-session-health status --format json
```

`install`, `uninstall`, `compact`, and `notify-test` only report their targets
unless `--apply` is given. `uninstall --apply` removes the command wrapper, the
runtime copy, and the LaunchAgent. It keeps the SQLite state and the logs:

```zsh
macos-session-health uninstall
macos-session-health uninstall --apply
```

Install unloads the agent and then publishes each file atomically. It does not
roll back a partial update. If a step fails, install reports which files it
completed and the observed launchd state, keeps the agent unloaded when
possible, and tells the operator to inspect `status` and rerun `install --apply`.
Uninstall also keeps the removals that succeeded and asks for a rerun after a
failure. Running either command again converges to the requested state.

After a partial failure, the installed wrapper may be missing or incomplete.
Run status and retries from the repository copy at
`services/macos-session-health/macos-session-health`, and preview a repeated
install with `install` first.

## What notifies

The agent samples once a minute. Each sample marks every condition below as
`bad`, `ok`, or `unknown` (the observation could not be made). A condition
fires after the stated number of consecutive `bad` samples and resolves after
the stated number of consecutive `ok` samples. An `unknown` sample does not
advance or reset either count, so a slow or failed probe can neither raise an
alert nor clear one.

| Condition | Bad when | Fires after | Resolves after |
| --- | --- | --- | --- |
| `spawn_failed` | `true`, `bash`, `zsh`, or `/usr/bin/python3` fails or exceeds 5 s | 2 | 3 |
| `process_table_high` | processes reach 85% of `kern.maxproc` or `kern.maxprocperuid` | 3 | 3 |
| `file_table_high` | `kern.num_files` reaches 80% of `kern.maxfiles` | 3 | 3 |
| `syspolicyd_rss_high` | `syspolicyd` RSS reaches 1536 MiB | 3 | 3 |
| `syspolicyd_log_errors` | a 5-minute log scan finds errno 24 (too many open files) from `syspolicyd`, or at least 100 `SecStaticCode` failures | 2 scans | 2 scans |
| `collector_failing` | the collector raises an exception | 3 | 3 |

A firing condition sends one notification at the `active` interruption level.
Its message includes the latest fact and the incident command to run. Resolving
sends one `passive` recovery notification, and only if the alert itself was
delivered. Nothing repeats while a condition stays bad. Thresholds and the
interruption level have CLI options and `MACOS_SESSION_HEALTH_*` environment
variables. Run `macos-session-health --help` to list them.

Nothing else notifies. Routine `SecStaticCode` failures (up to about 15 per
10 minutes on a healthy host), slow `log show` queries, PID changes, zombies,
individual processes with many open files, and app-specific inventories are
not symptoms.

## Evidence

While any condition is bad, the collector records at most one evidence bundle
every 30 minutes: load average and boot time, the busiest processes by CPU,
process counts by command and by parent, zombies, the processes with the most
open files (`lsof`), and five minutes of LaunchServices, RunningBoard,
`syspolicyd`, and spawn log lines. Every sample also stores spawn-check timings,
process-table totals, kernel limits, and `syspolicyd` RSS. Each `syspolicyd` log
scan stores its match counts and up to 20 matched lines.

## Triage

Start with the incident report:

```zsh
macos-session-health incident --hours 6 --format markdown
macos-session-health status --format json
```

The report shows the newest snapshot time, the state of each condition, alert
and delivery history, collector exceptions, failed spawn checks, `syspolicyd`
samples and log matches, and the latest evidence bundle. Use JSON when another
program reads the report, and use `query --event NAME` or `events` for raw records:

```zsh
macos-session-health incident --hours 6 --format json
macos-session-health query --event condition --limit 30 --format json
macos-session-health events --format json
```

`query`, `events`, and `incident` open SQLite read-only. A missing database is
an error; these commands never create an empty one.

## Capture the next failure

Leave the LaunchAgent running. When an app bounces, a command cannot spawn, or
a notification arrives, note the local time, the app, what you did, and what you
saw before restarting anything. Then save the surrounding hour outside the
repository:

```zsh
dir="$HOME/Library/Logs/macos-session-health/incidents"
mkdir -p "$dir"
stamp=$(date +%Y%m%d-%H%M%S)
macos-session-health incident --hours 1 --limit 200 --format json > "$dir/session-$stamp.json"
macos-session-health incident --hours 1 --limit 200 --format markdown > "$dir/session-$stamp.md"
```

Check the report's newest snapshot time first, because a stopped collector
cannot diagnose its own outage. A failure shorter than one sample can escape
these checks. Before sharing an excerpt, review its local paths and system-log
content.

## Safety

Do not restart `syspolicyd` with `launchctl`; SIP blocks that path. During an
active incident, do not run repeated `spctl`, `codesign`, or high-frequency
`lsof` probes, because they add work to the failing service.

A higher maxfiles limit is not a root-cause fix. It reduces secondary launch
failures but does not stop `syspolicyd` RSS or FD growth. This tool never
terminates applications or system processes. Choose any recovery action
explicitly from the observed facts.

## Notification delivery

The single-file CLI contains its own brrr client. Credentials are looked up in
this order:
`BRRR_SECRET` in the environment, `BRRR_ENV_FILE`, `~/.config/brrr/env`,
`~/.config/notify/brrr.env`, and finally the exe.dev brrr proxy.

Each delivery makes one bounded HTTP attempt. A failed alert delivery is
retried at most every 10 minutes while the condition still fires. Each
delivery records its condition, transition, HTTP status or error, and
credential source as a `brrr_notification` event. `status --format json`
reports the last delivery, the list of firing conditions, and whether
notifications are configured. `mise run check` reads the same report.

Validate the payload and local credential lookup, then send:

```zsh
macos-session-health notify-test
macos-session-health notify-test --apply
```

`notify-test` uses the invoking shell's credentials. Installation does not copy
the shell's `BRRR_SECRET` or `BRRR_ENV_FILE` into the LaunchAgent. For the
installed agent, put the secret in one of the default files above (or use the
proxy), then check `status --format json`. That report ignores credential
overrides from the calling shell.

## Storage

Snapshots older than 14 days are deleted (`--retention-days` or
`MACOS_SESSION_HEALTH_RETENTION_DAYS`). To reclaim unused SQLite pages without
losing history, compact the database. `compact --apply` stops and restarts only
this LaunchAgent around `VACUUM`:

```zsh
macos-session-health compact --format json
macos-session-health compact --format json --apply
```

To compact an offline database without stopping the installed LaunchAgent,
pass the global `--db PATH` option before `compact`.

## Maintenance

After changing the collector, test it and read its output before reinstalling:

```zsh
services/macos-session-health/macos-session-health --version
services/macos-session-health/macos-session-health-test
services/macos-session-health/macos-session-health --db /tmp/msh.sqlite3 snapshot
services/macos-session-health/macos-session-health install --apply
macos-session-health status --format json
```

After the next scheduled sample, confirm that `status` reports a fresh
`last_snapshot_at` and that `incident --hours 1` lists the snapshot as
`ok` or explains why it is unhealthy.
