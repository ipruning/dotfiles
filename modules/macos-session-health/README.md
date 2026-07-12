# macos-session-health runbook

Use this runbook when apps bounce in the Dock, open without a usable window, or
shell commands fail to spawn. The collector records user-session diagnostics in
`~/Library/Application Support/macos-session-health/health.sqlite3` and writes
logs under `~/Library/Logs/macos-session-health/`.

## Lifecycle

The single-file CLI owns its `~/.local/bin/macos-session-health` symlink and
generated LaunchAgent.

```zsh
modules/macos-session-health/macos-session-health install
macos-session-health status --format json
```

`uninstall` removes the command symlink and LaunchAgent but preserves SQLite
state and logs:

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

The CLI never closes ChatGPT Desktop. Confirm that it is safe to close before
executing recovery, and do not terminate unrelated Codex CLI sessions.

## Recovery

`recover` without `--execute` is read-only. After ChatGPT Desktop is closed or
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
signals. They are cooldown-limited, recorded in SQLite, and never execute
recovery. Use the incident report to see both emitted and suppressed decisions.

## Maintenance

After changing the collector, validate its command interface and read-only
outputs before reinstalling it:

```zsh
modules/macos-session-health/macos-session-health --version
modules/macos-session-health/macos-session-health incident --hours 1 --limit 3 --format json
modules/macos-session-health/macos-session-health recover --format json
git diff --check
modules/macos-session-health/macos-session-health install
macos-session-health status --format json
```

Wait for a new persisted collector run, then confirm its `snapshot_end` status
is `ok` in the incident report.
