# macos-session-health Runbook

`macos-session-health` records macOS user-session launch health in SQLite and
sends brrr alerts for high-severity signals. Runtime data belongs in
`~/Library/Application Support/macos-session-health/health.sqlite3`; logs belong
in `~/Library/Logs/macos-session-health/`.

## Incident Pattern

`macos-session-health` watches this failure pattern:

- Apps bounce in the Dock or open with no usable window.
- Shell commands report fork, pty, or open failures.
- LaunchServices and app assessment report `Too many open files`.
- Music can report error `9405`.
- Restarting the Mac clears the symptoms.

In the observed incidents, the failing service was `syspolicyd`, not the shell.
When `syspolicyd` is unhealthy, Gatekeeper and static-code checks fail, and
unrelated apps look broken.

Evidence from the 2026-06-19 incident:

- `syspolicyd` PID `516` reached about 4.8 GiB RSS.
- Unified logs repeated `UNIX error exception: 24`.
- Unified logs repeated `Failed to generate SecStaticCode ... error: 100024`.
- `spctl --assess` for VS Code and Codex reported `Too many open files`.
- `sudo kill -TERM 516` let launchd start a new `syspolicyd` PID.
- The new process started near 58 MiB RSS, then grew again while Codex Desktop
  was running.
- Reopening Codex Desktop produced a six-minute burst of 88,225
  `syspolicyd_fd_pressure` matches.
- Closing Codex Desktop stopped new matching log lines in the next observation
  window.

Treat Codex Desktop as the primary trigger candidate from the 2026-06-19
evidence. Treat VS Code and Music as affected clients unless new evidence says
otherwise.

## Risky Actions

Do not restart the system `syspolicyd` service with launchctl:

```zsh
sudo launchctl kickstart -k system/com.apple.security.syspolicy
```

SIP blocks that operation:

```text
Operation not permitted while System Integrity Protection is engaged
```

Do not run repeated `spctl` or `codesign` active assessment probes during an
active incident. These probes ask `syspolicyd` to do more work and can amplify
the failure. The LaunchAgent keeps both probes disabled by default:

```text
--spctl-interval-minutes 0
--codesign-interval-minutes 0
```

Do not treat `maxfiles` as the root-cause fix. The LaunchDaemon raises the GUI
soft limit to reduce secondary launch failures, but a `syspolicyd` RSS or FD
runaway can continue after the limit is higher.

## Recovery

Close Codex Desktop only after the user confirms it is safe to close the app.
Do not kill Codex CLI sessions:

```zsh
pkill -TERM -f '^/Applications/Codex\.app/Contents/MacOS/Codex$'
sleep 5
pkill -KILL -f '^/Applications/Codex\.app/Contents/MacOS/Codex$' 2>/dev/null
```

Terminate the unhealthy `syspolicyd` process. launchd starts the replacement:

```zsh
old="$(pgrep -x syspolicyd)"
echo "old syspolicyd pid=$old"

sudo kill -TERM "$old"
sleep 5

pgrep -x syspolicyd | xargs ps -o pid,ppid,stat,%cpu,rss,etime,comm= -p
```

If `pgrep` is briefly empty, wait a few seconds and check again. An empty
intermediate value is not itself a failed recovery.

Successful recovery looks like this:

- `launchctl print system/com.apple.security.syspolicy` shows `runs` increased.
- The PID changed.
- RSS dropped from GiB scale back to MiB scale.
- Recent unified logs stop producing `UNIX error exception: 24` and
  `Failed to generate SecStaticCode`.

If `sudo kill -TERM` does not replace the process, try `KILL` once:

```zsh
sudo kill -KILL "$old"
sleep 5
pgrep -x syspolicyd | xargs ps -o pid,ppid,stat,%cpu,rss,etime,comm= -p
```

If even direct signal delivery fails with `Operation not permitted`, reboot is
the remaining clean recovery.

## Queries

Start triage with these commands:

```zsh
macos-session-health incident --hours 6 --format markdown
launchctl print gui/$UID/com.alex.macos-session-health | sed -n '1,140p'
pgrep -x syspolicyd | xargs ps -o pid,ppid,stat,%cpu,rss,etime,comm= -p
```

These commands provide first-pass triage evidence. Do not start with `spctl`,
`codesign`, or `sudo launchctl kickstart`.

Incident report:

```zsh
macos-session-health incident --hours 6 --format markdown
```

Machine-readable report:

```zsh
macos-session-health incident --hours 6 --format json
```

Recent health signals:

```zsh
macos-session-health query --signals --limit 30
```

Recent `syspolicyd` resource samples:

```zsh
sqlite3 "$HOME/Library/Application Support/macos-session-health/health.sqlite3" \
  "select ts, data_json from events where event='process_resource' and data_json like '%syspolicyd%' order by id desc limit 20;"
```

Recent `syspolicyd` deltas:

```zsh
sqlite3 "$HOME/Library/Application Support/macos-session-health/health.sqlite3" \
  "select ts, data_json from events where event='process_resource_delta' order by id desc limit 20;"
```

CPU top at the time of an incident:

```zsh
sqlite3 "$HOME/Library/Application Support/macos-session-health/health.sqlite3" \
  "select ts, data_json from events where event='process_cpu_top' order by id desc limit 40;"
```

Recent brrr notification decisions:

```zsh
sqlite3 "$HOME/Library/Application Support/macos-session-health/health.sqlite3" \
  "select ts, event, data_json from events where event like 'brrr%' order by id desc limit 20;"
```

## Alert Semantics

The LaunchAgent sends brrr notifications only for `error` or `critical` health
signals. It uses `active` interruption level and a 30-minute cooldown.

The notification fingerprint includes the signal type and the value bucket. A
small repeated `syspolicyd_fd_pressure` signal should stay quiet during
cooldown, but a jump from tens of matches to tens of thousands of matches should
produce a distinct alert.

Health signals:

- `syspolicyd_fd_pressure`: unified logs show `syspolicyd` FD or static-code
  failures. Low-volume matches are warning-only by default; the LaunchAgent
  promotes a scan to error at `--syspolicyd-log-error-count 100`.
- `process_rss_high`: `syspolicyd` crossed the warning RSS threshold.
- `process_rss_runaway`: `syspolicyd` crossed the error RSS threshold. The
  LaunchAgent uses `--syspolicyd-rss-error-mb 2048`.
- `process_rss_growth_high`: `syspolicyd` RSS grew too fast between snapshots.
- `process_pid_changed`: monitored process restarted.
- `spawn_failed`: simple process spawning failed.
- `maxfiles_soft_low`: GUI `maxfiles` soft limit is low.

`maxfiles_soft_low` is context, not proof of cause.

## Monitor Maintenance

After changing the script or plist:

```zsh
mise exec -- uv run python -m py_compile modules/libexec/macos-session-health.py
modules/bin/macos-session-health --version
modules/bin/macos-session-health incident --hours 1 --limit 3 --format json \
  | python3 -m json.tool >/dev/null
plutil -lint modules/launchagents/com.alex.macos-session-health.plist
git diff --check
install -m 644 modules/launchagents/com.alex.macos-session-health.plist \
  "$HOME/Library/LaunchAgents/com.alex.macos-session-health.plist"
launchctl bootout gui/$UID "$HOME/Library/LaunchAgents/com.alex.macos-session-health.plist" 2>/dev/null || true
launchctl bootstrap gui/$UID "$HOME/Library/LaunchAgents/com.alex.macos-session-health.plist"
launchctl print gui/$UID/com.alex.macos-session-health
```

Keep `spctl` and `codesign` probes disabled unless deliberately testing a
healthy system.

After changing the maxfiles LaunchDaemon:

```zsh
plutil -lint modules/launchdaemons/com.alex.limit.maxfiles.plist
sudo install -o root -g wheel -m 644 \
  modules/launchdaemons/com.alex.limit.maxfiles.plist \
  /Library/LaunchDaemons/com.alex.limit.maxfiles.plist
sudo launchctl bootout system /Library/LaunchDaemons/com.alex.limit.maxfiles.plist 2>/dev/null || true
sudo launchctl bootstrap system /Library/LaunchDaemons/com.alex.limit.maxfiles.plist
sudo launchctl print system/com.alex.limit.maxfiles
launchctl limit maxfiles
```
