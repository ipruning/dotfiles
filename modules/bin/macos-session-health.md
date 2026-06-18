# macos-session-health Runbook

`macos-session-health` records macOS user-session launch health into SQLite and
sends brrr alerts for high-severity signals. Runtime data belongs in
`~/Library/Application Support/macos-session-health/health.sqlite3`; logs belong
in `~/Library/Logs/macos-session-health/`.

## Incident Pattern

The failure pattern this monitor is built for:

- Apps bounce in the Dock or open with no usable window.
- Shell commands report fork, pty, or open failures.
- LaunchServices and app assessment report `Too many open files`.
- Music can report error `9405`.
- Restarting the Mac clears the symptoms.

The important service is usually `syspolicyd`, not the shell. When `syspolicyd`
is unhealthy, Gatekeeper and static-code checks fail, and unrelated apps look
broken.

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

Treat Codex Desktop as the current primary trigger candidate. Treat VS Code and
Music as affected clients unless new evidence says otherwise.

## Do Not Do This

Do not try to restart system `syspolicyd` with launchctl:

```zsh
sudo launchctl kickstart -k system/com.apple.security.syspolicy
```

SIP blocks that operation:

```text
Operation not permitted while System Integrity Protection is engaged
```

Do not run repeated `spctl` or `codesign` probes during an active incident.
They ask `syspolicyd` to do more work and can amplify the failure. The
LaunchAgent keeps both probes disabled by default:

```text
--spctl-interval-minutes 0
--codesign-interval-minutes 0
```

Do not fix this by raising `maxfiles` first. A low GUI soft limit is useful
context, but raising it can delay visible symptoms while the leak continues.

## Recovery

First close Codex Desktop, without killing Codex CLI sessions:

```zsh
pkill -TERM -f '^/Applications/Codex\.app/Contents/MacOS/Codex$'
sleep 5
pkill -KILL -f '^/Applications/Codex\.app/Contents/MacOS/Codex$' 2>/dev/null
```

Then ask launchd to replace the unhealthy `syspolicyd` by terminating the
process:

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

For the next AI or a fresh shell, start here:

```zsh
macos-session-health incident --hours 6 --format markdown
launchctl print gui/$UID/com.alex.macos-session-health | sed -n '1,140p'
pgrep -x syspolicyd | xargs ps -o pid,ppid,stat,%cpu,rss,etime,comm= -p
```

This is enough for first-pass triage. Do not start with `spctl`, `codesign`, or
`sudo launchctl kickstart`.

AI-ready incident packet:

```zsh
macos-session-health incident --hours 6 --format markdown
```

Machine-readable packet:

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

Current important signals:

- `syspolicyd_fd_pressure`: unified logs show `syspolicyd` FD or static-code
  failures.
- `process_rss_high`: `syspolicyd` crossed the warning RSS threshold.
- `process_rss_runaway`: `syspolicyd` crossed the error RSS threshold.
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
