# macos-session-health Runbook

`macos-session-health` is a single-file CLI. It collects health data and owns
installation, removal, status reporting, and LaunchAgent generation. The
LaunchAgent runs the stable `~/.local/bin/macos-session-health` symlink; the
symlink points to this module's executable. The collector writes events to
SQLite and sends brrr notifications for a small allow-list of health signals.
SQLite data lives in `~/Library/Application Support/macos-session-health/health.sqlite3`;
logs live in `~/Library/Logs/macos-session-health/`.

## Terms

- **collector**: the `macos-session-health` process that gathers data.
- **collector run**: one pass through the configured checks; incident reports summarize collector runs in the selected time window.
- **LaunchAgent**: the launchd job that starts the collector.
- **event**: one row in the SQLite `events` table.
- **health signal**: an event with `event='health_signal'`; it has a signal name and severity.
- **incident report**: the output of `macos-session-health incident`.
- **notification**: a brrr message sent for an allow-listed health signal.
- **recovery**: the guarded `syspolicyd` restart flow in `macos-session-health recover`.
- **Unix signal**: a POSIX signal, such as TERM or KILL, sent to a process by `recover --signal`.

## Observed Failure Pattern

The collector watches this failure pattern:

- Apps bounce in the Dock or open with no usable window.
- Shell commands report fork, pty, or open failures.
- LaunchServices and app assessment report `Too many open files`.
- Music can report error `9405`.
- Restarting the Mac clears the symptoms.

In the observed incidents, the failing service was `syspolicyd`, not the shell.
When `syspolicyd` is unhealthy, Gatekeeper and static-code checks fail, and
unrelated apps look broken.

Observed facts from the 2026-06-19 incident:

- `syspolicyd` PID `516` reached about 4.8 GiB RSS.
- Unified logs repeated `UNIX error exception: 24`.
- Unified logs repeated `Failed to generate SecStaticCode ... error: 100024`.
- `spctl --assess` for VS Code and Codex reported `Too many open files`.
- `sudo kill -TERM 516` let launchd start a new `syspolicyd` PID.
- The new process started near 58 MiB RSS, then grew again while Codex Desktop
  was running.
- Reopening Codex Desktop produced a six-minute burst of 88,225
  `syspolicyd_assessment_failure` matches.
- Closing Codex Desktop stopped new matching log lines in the next observation
  window.

Codex Desktop is the primary trigger candidate from the 2026-06-19 observations.
VS Code and Music are affected clients unless later observations point elsewhere.

## Codex Diagnostics

The collector records the Codex facts needed to explain a `syspolicyd` incident:
Desktop version, non-secret config switches, helper process counts, `trustd`
resources, and Codex `code_sign_clone` size. It also records warning-only
config mismatch signals, such as a disabled bundled plugin with its helper still
running. The Codex config snapshot also classifies SkyComputerUseClient `notify`
paths as stable bundled paths, volatile `~/.codex/computer-use` paths, or other
paths.

The collector checks Codex trusted project roots at a low cadence. It only checks
direct roots from `~/.codex/config.toml`; it does not recursively scan all
workspaces. When a trusted root has a direct `.git`, the collector runs one
bounded `git rev-parse --git-dir --is-inside-work-tree` validation and records
missing roots or invalid `.git` shells as warning-only context.

Use `macos-session-health incident` for system launch diagnostics. Morning
reports and Feishu checks are separate workflows.

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
the failure. The collector keeps both probes disabled by default:

```text
--spctl-interval-minutes 0
--codesign-interval-minutes 0
```

Do not treat `maxfiles` as the root-cause fix. The LaunchDaemon raises the GUI
soft limit to reduce secondary launch failures, but a `syspolicyd` RSS or FD
failure can continue after the limit is higher.

Do not run a high-frequency `lsof` loop against `syspolicyd`. The collector
samples `syspolicyd` RSS and CPU every minute, but expensive FD sampling is
rate-limited:

```text
--fd-top-interval-minutes 5
--syspolicyd-lsof-interval-minutes 5
```

## Recovery

Start with the guarded recovery plan:

```zsh
macos-session-health recover
```

The default command is read-only. It prints the current `syspolicyd` PID, RSS,
CPU, and the manual recovery commands.

Close Codex Desktop only after the user confirms it is safe to close the app.
Do not kill Codex CLI sessions:

```zsh
pkill -TERM -f '^/Applications/Codex\.app/Contents/MacOS/Codex$'
sleep 5
pkill -KILL -f '^/Applications/Codex\.app/Contents/MacOS/Codex$' 2>/dev/null
```

After Codex Desktop is closed, execute the guarded recovery:

```zsh
macos-session-health recover --execute --assume-codex-desktop-closed
```

The command sends `TERM` to the current `syspolicyd` PID, waits, then prints the
replacement PID and RSS. It does not close Codex Desktop. The command inherits
the current terminal for `sudo`, so it can prompt for a password when needed.

The manual equivalent is:

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

If even direct Unix signal delivery fails with `Operation not permitted`, reboot is
the remaining clean recovery.

## Queries

Start triage with these commands:

```zsh
macos-session-health incident --hours 6 --format markdown
macos-session-health recover
launchctl print gui/$UID/com.alex.macos-session-health | sed -n '1,140p'
pgrep -x syspolicyd | xargs ps -o pid,ppid,stat,%cpu,rss,etime,comm= -p
```

These commands are for first-pass triage. Do not start with `spctl`, `codesign`,
or `sudo launchctl kickstart`.

Incident report:

```zsh
macos-session-health incident --hours 6 --format markdown
```

JSON report:

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

## brrr Notification Rules

The collector records every health signal in SQLite. It sends a brrr notification only
when one of these health signals appears:

- process spawning is failing;
- `syspolicyd_assessment_failure` reaches the `--brrr-syspolicyd-assessment-failure-count` threshold;
- `syspolicyd` RSS crossed the error threshold;
- `syspolicyd` RSS is growing quickly;
- Codex `code_sign_clone` is growing quickly;
- the collector itself crashed.

Config mismatch, Codex helper counts, trusted-root warnings, and `trustd`
warnings stay in SQLite and the incident report. They do not send brrr
notifications by themselves.

Each brrr notification uses `passive` interruption level and a global
10-minute cooldown. After any brrr notification, later matching health signals are
recorded but not sent until the cooldown expires. The title names the failure.
The body gives the key value, the likely app-launch impact, and the
`macos-session-health incident --hours 6 --format markdown` command.

`syspolicyd_assessment_failure` comes from unified-log assessment failures. The
collector treats low-volume matches as warning-only and promotes a scan to
error at `--syspolicyd-log-error-count 100`. `maxfiles_soft_low` is context, not
proof of cause.
The brrr notification threshold is separate: syspolicyd assessment-failure
notifications wait for `--brrr-syspolicyd-assessment-failure-count`.

The core passive unified-log scan is intentionally narrower than the wider Codex
diagnostic scan. Core syspolicyd and audio failure terms run every five minutes;
Codex-specific warning terms run less often:

```text
--passive-log-interval-minutes 5
--codex-passive-log-interval-minutes 30
```

RSS growth and `code_sign_clone` growth are health signals that can send passive
notifications. They do not execute recovery.

## Maintenance

After changing the collector:

```zsh
mise exec -- uv run python -m py_compile modules/macos-session-health/macos-session-health
modules/bin/macos-session-health --version
modules/bin/macos-session-health incident --hours 1 --limit 3 --format json \
  | python3 -m json.tool >/dev/null
modules/bin/macos-session-health recover --format json \
  | python3 -m json.tool >/dev/null
git diff --check
modules/bin/macos-session-health install
modules/bin/macos-session-health status --format json | python3 -m json.tool
```

`uninstall` stops the LaunchAgent and removes its plist and `~/.local/bin`
symlink. It preserves SQLite state and logs:

```zsh
macos-session-health uninstall
```

Keep `spctl` and `codesign` probes disabled unless deliberately testing a
healthy system.

After changing the maxfiles LaunchDaemon:

```zsh
macos-maxfiles install --dry-run
macos-maxfiles install
macos-maxfiles status --json
```
