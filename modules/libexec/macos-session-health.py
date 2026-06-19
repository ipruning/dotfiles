# /// script
# requires-python = ">=3.13"
# ///

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import glob
import hashlib
import json
import os
import platform
import re
import resource
import shlex
import socket
import sqlite3
import subprocess
import sys
import time
import tomllib
import uuid
from pathlib import Path
from typing import Any


VERSION = "0.5.0"
DEFAULT_DB = (
    Path.home()
    / "Library"
    / "Application Support"
    / "macos-session-health"
    / "health.sqlite3"
)
DEFAULT_APP = "/Applications/Visual Studio Code.app"
CODEX_APP = Path("/Applications/Codex.app")
CODEX_CONFIG = Path.home() / ".codex" / "config.toml"
CODEX_CHROME_NATIVE_HOSTS = Path.home() / ".codex" / "chrome-native-hosts-v2.json"
CODEX_CHROME_EXTENSION_ID = "hehggadaopoacecdllhhajmbjkdcmajg"
RESOURCE_ERROR_RE = re.compile(
    r"too many open files|resource temporarily unavailable|fork|forkpty|cannot allocate memory|unable to spawn",
    re.IGNORECASE,
)
KNOWN_EVENTS = {
    "app_assess",
    "app_assess_skipped",
    "app_bundle",
    "app_codesign_verify",
    "app_codesign_verify_skipped",
    "brrr_notification",
    "brrr_notification_skipped",
    "code_sign_clone_delta",
    "code_sign_clone_status",
    "command_process_count",
    "codex_config_snapshot",
    "codex_process_summary",
    "fd_top",
    "health_signal",
    "launch_service",
    "limits",
    "log_excerpt_collecting",
    "log_excerpt_skipped",
    "macos_log_excerpt",
    "macos_passive_log_match",
    "macos_passive_log_scan",
    "parent_process_count",
    "periodic_probe_skipped",
    "process_cpu_top",
    "process_lsof_path_count",
    "process_lsof_summary",
    "process_resource",
    "process_resource_delta",
    "process_summary",
    "retention_prune",
    "snapshot_begin",
    "snapshot_end",
    "spawn_check",
    "system_context",
    "user_process_count",
    "zombie",
}
SYSPOLICY_LABEL = "com.apple.security.syspolicy"
AUDIO_COMPONENT_REGISTRAR_LABEL = "com.apple.audio.AudioComponentRegistrar"
SEVERITY_RANK = {
    "warning": 1,
    "error": 2,
    "critical": 3,
}


class CliError(Exception):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def logfmt_quote(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{text}"'


def print_error(message: str, **data: Any) -> None:
    parts = [f"error={logfmt_quote(message)}"]
    parts.extend(f"{key}={logfmt_quote(value)}" for key, value in data.items())
    print(" ".join(parts), file=sys.stderr)


def print_records(records: list[dict[str, Any]], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(records, ensure_ascii=False))
        return
    for record in records:
        print(" ".join(f"{key}={logfmt_quote(value)}" for key, value in record.items()))


def open_read_db(db_path: Path) -> sqlite3.Connection:
    try:
        conn = sqlite3.connect(db_path)
    except sqlite3.Error as exc:
        raise CliError("unable to open database") from exc
    conn.row_factory = sqlite3.Row
    return conn


def run_command(
    args: list[str],
    *,
    timeout: float,
    input_text: str | None = None,
) -> tuple[int, str, str, bool, float]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            args,
            input=input_text,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        duration_ms = (time.monotonic() - started) * 1000
        return completed.returncode, completed.stdout, completed.stderr, False, duration_ms
    except subprocess.TimeoutExpired as exc:
        duration_ms = (time.monotonic() - started) * 1000
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return 124, stdout, stderr, True, duration_ms
    except OSError as exc:
        duration_ms = (time.monotonic() - started) * 1000
        return 127, "", f"{type(exc).__name__}: {exc}", False, duration_ms


def run_interactive_command(args: list[str], *, timeout: float) -> tuple[int, bool, float, str]:
    started = time.monotonic()
    try:
        completed = subprocess.run(args, timeout=timeout, check=False)
        duration_ms = (time.monotonic() - started) * 1000
        return completed.returncode, False, duration_ms, ""
    except subprocess.TimeoutExpired:
        duration_ms = (time.monotonic() - started) * 1000
        return 124, True, duration_ms, "command timed out"
    except OSError as exc:
        duration_ms = (time.monotonic() - started) * 1000
        return 127, False, duration_ms, f"{type(exc).__name__}: {exc}"


class Store:
    def __init__(self, db_path: Path | None, emit_stdout: bool = True) -> None:
        self.db_path = db_path
        self.emit_stdout = emit_stdout
        self.conn: sqlite3.Connection | None = None
        self.current_signals: list[dict[str, Any]] = []
        if db_path is not None:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(db_path)
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA busy_timeout=5000")
            self.conn.execute("PRAGMA foreign_keys=ON")
            self._init_schema()

    def _init_schema(self) -> None:
        assert self.conn is not None
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
              id TEXT PRIMARY KEY,
              started_at TEXT NOT NULL,
              ended_at TEXT,
              hostname TEXT NOT NULL,
              username TEXT NOT NULL,
              pid INTEGER NOT NULL,
              mode TEXT NOT NULL,
              app_paths_json TEXT NOT NULL,
              status TEXT
            );

            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              snapshot_id TEXT NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
              ts TEXT NOT NULL,
              event TEXT NOT NULL,
              severity TEXT,
              data_json TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_events_snapshot ON events(snapshot_id);
            CREATE INDEX IF NOT EXISTS idx_events_event_ts ON events(event, ts);
            CREATE INDEX IF NOT EXISTS idx_events_severity_ts ON events(severity, ts);

            CREATE TABLE IF NOT EXISTS state (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def create_snapshot(self, mode: str, app_paths: list[str]) -> str:
        snapshot_id = str(uuid.uuid4())
        if self.conn is not None:
            self.conn.execute(
                """
                INSERT INTO snapshots
                  (id, started_at, hostname, username, pid, mode, app_paths_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    utc_now(),
                    socket.gethostname(),
                    getpass.getuser(),
                    os.getpid(),
                    mode,
                    json.dumps(app_paths),
                ),
            )
            self.conn.commit()
        self.current_signals = []
        return snapshot_id

    def finish_snapshot(self, snapshot_id: str, status: str) -> None:
        if self.conn is None:
            return
        self.conn.execute(
            "UPDATE snapshots SET ended_at = ?, status = ? WHERE id = ?",
            (utc_now(), status, snapshot_id),
        )
        self.conn.commit()

    def prune(self, retention_days: int | None) -> int:
        if self.conn is None or retention_days is None or retention_days <= 0:
            return 0
        cutoff = (
            dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=retention_days)
        ).isoformat(timespec="seconds").replace("+00:00", "Z")
        cursor = self.conn.execute("DELETE FROM snapshots WHERE started_at < ?", (cutoff,))
        self.conn.commit()
        return cursor.rowcount

    def get_state(self, key: str) -> str | None:
        if self.conn is None:
            return None
        row = self.conn.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row[0])

    def set_state(self, key: str, value: str) -> None:
        if self.conn is None:
            return
        self.conn.execute(
            """
            INSERT INTO state (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value, utc_now()),
        )
        self.conn.commit()

    def emit(self, snapshot_id: str, event: str, severity: str | None = None, **data: Any) -> None:
        ts = utc_now()
        if event == "health_signal":
            signal = {"severity": severity}
            signal.update(data)
            self.current_signals.append(signal)
        if self.emit_stdout:
            parts = [f"ts={logfmt_quote(ts)}", f"event={logfmt_quote(event)}"]
            if severity is not None:
                parts.append(f"severity={logfmt_quote(severity)}")
            for key, value in data.items():
                parts.append(f"{key}={logfmt_quote(value)}")
            print(" ".join(parts), flush=True)

        if self.conn is not None:
            self.conn.execute(
                """
                INSERT INTO events (snapshot_id, ts, event, severity, data_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (snapshot_id, ts, event, severity, json.dumps(data, ensure_ascii=False)),
            )
            self.conn.commit()

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()


def parse_launchctl_limit(output: str, resource_name: str) -> tuple[str, str]:
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == resource_name:
            return parts[1], parts[2]
    return "", ""


def parse_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_launchctl_print(output: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in output.splitlines():
        if not line.startswith("\t") or line.startswith("\t\t"):
            continue
        stripped = line.strip()
        if " = " not in stripped:
            continue
        key, value = stripped.split(" = ", 1)
        if key in {"active count", "path", "type", "state", "program", "runs", "pid", "last exit code"}:
            parsed[key.replace(" ", "_")] = value
    return parsed


def plugin_enabled(config: dict[str, Any], plugin_name: str) -> bool | None:
    plugins = config.get("plugins")
    if not isinstance(plugins, dict):
        return None
    plugin = plugins.get(plugin_name)
    if not isinstance(plugin, dict):
        return None
    enabled = plugin.get("enabled")
    return enabled if isinstance(enabled, bool) else None


def candidate_code_sign_clone_paths() -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()

    tmpdir = os.getenv("TMPDIR")
    if tmpdir:
        candidate = Path(tmpdir).expanduser().resolve().parent / "X" / "com.openai.codex.code_sign_clone"
        paths.append(candidate)

    for raw_path in glob.glob("/var/folders/*/*/X/com.openai.codex.code_sign_clone"):
        paths.append(Path(raw_path))

    unique: list[Path] = []
    for path in paths:
        key = str(path.resolve(strict=False))
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def codex_process_role(command: str) -> str:
    if command.startswith("/Applications/Codex.app/Contents/MacOS/Codex"):
        return "codex_main"
    if "/Applications/Codex.app/Contents/Resources/codex app-server" in command:
        return "codex_app_server"
    if "/Codex (Service).app/Contents/MacOS/Codex (Service)" in command:
        return "codex_service"
    if "/Codex (Renderer).app/Contents/MacOS/Codex (Renderer)" in command:
        return "codex_renderer"
    if "/browser_crashpad_handler" in command and "Codex" in command:
        return "codex_crashpad"
    if "/Applications/Codex.app/Contents/Resources/cua_node/bin/node_repl" in command:
        return "codex_node_repl"
    if "SkyComputerUseClient" in command and " mcp" in command:
        return "codex_sky_computer_use"
    if "extension-host" in command and f"chrome-extension://{CODEX_CHROME_EXTENSION_ID}/" in command:
        return "codex_chrome_extension_host"
    return ""


def syspolicyd_status(timeout: float) -> dict[str, Any]:
    pgrep_code, pgrep_out, pgrep_err, pgrep_timed_out, pgrep_ms = run_command(
        ["pgrep", "-x", "syspolicyd"],
        timeout=timeout,
    )
    pids = [line.strip() for line in pgrep_out.splitlines() if line.strip()]
    pid = pids[0] if pids else ""
    status: dict[str, Any] = {
        "pid": pid,
        "pids": pids,
        "pgrep_exit": pgrep_code,
        "pgrep_timeout": pgrep_timed_out,
        "pgrep_duration_ms": round(pgrep_ms, 1),
        "pgrep_error": pgrep_err.strip(),
    }
    if not pid:
        return status

    ps_code, ps_out, ps_err, ps_timed_out, ps_ms = run_command(
        ["ps", "-p", pid, "-o", "pid=,ppid=,stat=,%cpu=,rss=,etime=,comm="],
        timeout=timeout,
    )
    status.update(
        {
            "ps_exit": ps_code,
            "ps_timeout": ps_timed_out,
            "ps_duration_ms": round(ps_ms, 1),
            "ps_error": ps_err.strip(),
        }
    )
    parts = ps_out.strip().split(None, 6)
    if len(parts) >= 7:
        parsed_pid, ppid, stat, cpu, rss, etime, comm = parts
        rss_kb = parse_int(rss)
        status.update(
            {
                "pid": parsed_pid,
                "ppid": ppid,
                "stat": stat,
                "cpu_percent": parse_float(cpu),
                "rss_kb": rss_kb,
                "rss_mb": round(rss_kb / 1024, 1) if rss_kb is not None else None,
                "etime": etime,
                "comm": comm,
            }
        )
    elif ps_out.strip():
        status["ps_row"] = ps_out.strip()
    return status


def render_recovery_markdown(report: dict[str, Any]) -> str:
    before = report.get("before") or {}
    after = report.get("after") or {}
    commands = report.get("manual_commands") or []
    lines = [
        "# macos-session-health Recovery Plan",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- action: `{report['action']}`",
        f"- execute: `{report['execute']}`",
        f"- confirmed_codex_desktop_closed: `{report['confirmed_codex_desktop_closed']}`",
        "",
        "## syspolicyd Before",
        "",
        (
            f"- pid={before.get('pid', '')} cpu_percent={before.get('cpu_percent', '')} "
            f"rss_mb={before.get('rss_mb', '')} etime={before.get('etime', '')} "
            f"stat={before.get('stat', '')}"
        ),
    ]
    if after:
        lines.extend(
            [
                "",
                "## syspolicyd After",
                "",
                (
                    f"- pid={after.get('pid', '')} cpu_percent={after.get('cpu_percent', '')} "
                    f"rss_mb={after.get('rss_mb', '')} etime={after.get('etime', '')} "
                    f"stat={after.get('stat', '')}"
                ),
            ]
        )
    if report.get("error"):
        lines.extend(["", "## Error", "", f"- {report['error']}"])
    if commands:
        lines.extend(["", "## Manual Commands", ""])
        lines.append("```zsh")
        lines.extend(commands)
        lines.append("```")
    if report.get("notes"):
        lines.extend(["", "## Notes", ""])
        lines.extend(f"- {note}" for note in report["notes"])
    return "\n".join(lines)


def recover_syspolicyd(args: argparse.Namespace) -> int:
    before = syspolicyd_status(args.command_timeout)
    commands = [
        "pkill -TERM -f '^/Applications/Codex\\.app/Contents/MacOS/Codex$'",
        "sleep 5",
        "old=\"$(pgrep -x syspolicyd)\"",
        "sudo kill -TERM \"$old\"",
        "sleep 5",
        "pgrep -x syspolicyd | xargs ps -o pid,ppid,stat,%cpu,rss,etime,comm= -p",
    ]
    report: dict[str, Any] = {
        "generated_at": utc_now(),
        "action": "restart_syspolicyd",
        "execute": args.execute,
        "confirmed_codex_desktop_closed": args.assume_codex_desktop_closed,
        "before": before,
        "manual_commands": commands,
        "notes": [
            "Close Codex Desktop before restarting syspolicyd; otherwise Codex can refill the failure state.",
            "This command never closes Codex Desktop itself.",
            "Use --execute only after confirming Codex Desktop is closed or safe to close.",
        ],
    }

    if not before.get("pid"):
        report["error"] = "syspolicyd pid not found"
        print_recovery_report(report, args.format)
        return 1

    if not args.execute:
        print_recovery_report(report, args.format)
        return 0

    if not args.assume_codex_desktop_closed:
        report["error"] = "refusing to execute without --assume-codex-desktop-closed"
        print_recovery_report(report, args.format)
        return 2

    pid = str(before["pid"])
    code, timed_out, duration_ms, error = run_interactive_command(
        ["sudo", "kill", f"-{args.signal}", pid],
        timeout=args.command_timeout,
    )
    report["kill"] = {
        "signal": args.signal,
        "pid": pid,
        "exit": code,
        "timeout": timed_out,
        "duration_ms": round(duration_ms, 1),
        "error": error,
    }
    time.sleep(args.wait_seconds)
    report["after"] = syspolicyd_status(args.command_timeout)
    print_recovery_report(report, args.format)
    return 0 if code == 0 and not timed_out else 1


def print_recovery_report(report: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(report, ensure_ascii=False))
        return
    print(render_recovery_markdown(report))


def collect_launch_service(
    store: Store,
    snapshot_id: str,
    service: str,
    timeout: float,
    *,
    warn_if_missing: bool = True,
    warn_if_not_running: bool = True,
) -> dict[str, Any]:
    code, out, err, timed_out, duration_ms = run_command(
        ["launchctl", "print", service],
        timeout=timeout,
    )
    fields = parse_launchctl_print(out) if code == 0 and not timed_out else {}
    found = code == 0 and not timed_out and bool(fields)
    state = fields.get("state", "")
    data: dict[str, Any] = {
        "service": service,
        "found": found,
        "exit": code,
        "timeout": timed_out,
        "duration_ms": round(duration_ms, 1),
        "state": state,
        "pid": fields.get("pid", ""),
        "runs": fields.get("runs", ""),
        "active_count": fields.get("active_count", ""),
        "type": fields.get("type", ""),
        "path": fields.get("path", ""),
        "program": fields.get("program", ""),
        "last_exit_code": fields.get("last_exit_code", ""),
        "error": err.strip(),
    }
    store.emit(snapshot_id, "launch_service", **data)

    if not found and warn_if_missing:
        store.emit(
            snapshot_id,
            "health_signal",
            "warning",
            signal="launch_service_missing",
            service=service,
            value=code,
            detail=err.strip() or "launchctl did not return service details",
        )
    elif warn_if_not_running and state and state != "running":
        store.emit(
            snapshot_id,
            "health_signal",
            "warning",
            signal="launch_service_not_running",
            service=service,
            value=state,
            detail="launchd service exists but is not running",
        )
    return data


def collect_process_resource(
    store: Store,
    snapshot_id: str,
    pid: str | int | None,
    *,
    role: str,
    service: str,
    timeout: float,
    cpu_warn: float | None = None,
    rss_warn_mb: float | None = None,
) -> dict[str, Any] | None:
    if pid in (None, ""):
        return None
    pid_text = str(pid)
    code, out, err, timed_out, duration_ms = run_command(
        ["ps", "-p", pid_text, "-o", "pid=,ppid=,user=,stat=,%cpu=,%mem=,rss=,etime=,comm="],
        timeout=timeout,
    )
    if code != 0 or timed_out or not out.strip():
        store.emit(
            snapshot_id,
            "process_resource",
            role=role,
            service=service,
            pid=pid_text,
            exit=code,
            timeout=timed_out,
            duration_ms=round(duration_ms, 1),
            error=err.strip() or "ps returned no process row",
        )
        return None

    parts = out.strip().split(None, 8)
    if len(parts) < 9:
        store.emit(
            snapshot_id,
            "process_resource",
            role=role,
            service=service,
            pid=pid_text,
            exit=code,
            timeout=timed_out,
            duration_ms=round(duration_ms, 1),
            error="unable to parse ps row",
            row=out.strip(),
        )
        return None

    parsed_pid, ppid, user, stat, cpu, mem, rss, etime, comm = parts
    cpu_value = parse_float(cpu)
    rss_kb = parse_int(rss)
    rss_mb = round(rss_kb / 1024, 1) if rss_kb is not None else None
    resource_data: dict[str, Any] = {
        "role": role,
        "service": service,
        "pid": parsed_pid,
        "ppid": ppid,
        "user": user,
        "stat": stat,
        "cpu_percent": cpu,
        "mem_percent": mem,
        "rss_kb": rss,
        "rss_mb": rss_mb if rss_mb is not None else "",
        "etime": etime,
        "comm": comm,
        "exit": code,
        "timeout": timed_out,
        "duration_ms": round(duration_ms, 1),
    }
    store.emit(
        snapshot_id,
        "process_resource",
        **resource_data,
    )
    if cpu_warn is not None and cpu_value is not None and cpu_value >= cpu_warn:
        store.emit(
            snapshot_id,
            "health_signal",
            "warning",
            signal="process_cpu_high",
            role=role,
            service=service,
            pid=parsed_pid,
            value=cpu_value,
            detail="process CPU percent exceeded threshold",
        )
    if rss_warn_mb is not None and rss_mb is not None and rss_mb >= rss_warn_mb:
        store.emit(
            snapshot_id,
            "health_signal",
            "warning",
            signal="process_rss_high",
            role=role,
            service=service,
            pid=parsed_pid,
            value=rss_mb,
            detail="process RSS exceeded threshold",
        )
    return resource_data


def collect_process_resource_delta(
    store: Store,
    snapshot_id: str,
    resource_data: dict[str, Any] | None,
    *,
    role: str,
    rss_growth_warn_mb_per_minute: float | None = None,
    rss_error_mb: float | None = None,
) -> None:
    if store.conn is None or not resource_data:
        return

    pid = str(resource_data.get("pid") or "")
    rss_mb = parse_float(str(resource_data.get("rss_mb") or ""))
    if not pid or rss_mb is None:
        return

    state_key = f"last_process_resource:{role}"
    previous_raw = store.get_state(state_key)
    now = dt.datetime.now(dt.timezone.utc)
    current_state = {
        "ts": utc_now(),
        "pid": pid,
        "rss_mb": rss_mb,
    }

    if previous_raw:
        try:
            previous = json.loads(previous_raw)
            previous_ts = dt.datetime.fromisoformat(str(previous["ts"]).replace("Z", "+00:00"))
            previous_pid = str(previous.get("pid") or "")
            previous_rss = float(previous.get("rss_mb"))
            elapsed_seconds = max((now - previous_ts).total_seconds(), 1)
            rss_delta_mb = round(rss_mb - previous_rss, 1)
            rss_growth_mb_per_minute = round((rss_mb - previous_rss) / elapsed_seconds * 60, 1)
            same_pid = previous_pid == pid
            store.emit(
                snapshot_id,
                "process_resource_delta",
                role=role,
                pid=pid,
                previous_pid=previous_pid,
                pid_changed=not same_pid,
                rss_mb=rss_mb,
                previous_rss_mb=previous_rss,
                rss_delta_mb=rss_delta_mb,
                rss_growth_mb_per_minute=rss_growth_mb_per_minute,
                elapsed_seconds=round(elapsed_seconds, 1),
            )
            if not same_pid:
                store.emit(
                    snapshot_id,
                    "health_signal",
                    "warning",
                    signal="process_pid_changed",
                    role=role,
                    pid=pid,
                    value=previous_pid,
                    detail="monitored process pid changed since previous snapshot",
                )
            elif (
                rss_growth_warn_mb_per_minute is not None
                and rss_growth_mb_per_minute >= rss_growth_warn_mb_per_minute
            ):
                store.emit(
                    snapshot_id,
                    "health_signal",
                    "warning",
                    signal="process_rss_growth_high",
                    role=role,
                    pid=pid,
                    value=rss_growth_mb_per_minute,
                    detail="process RSS is growing quickly",
                )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass

    if rss_error_mb is not None and rss_mb >= rss_error_mb:
        store.emit(
            snapshot_id,
            "health_signal",
            "error",
            signal="process_rss_error",
            role=role,
            pid=pid,
            value=rss_mb,
            detail="process RSS exceeded error threshold",
        )

    store.set_state(state_key, json.dumps(current_state, sort_keys=True))


def collect_process_lsof(
    store: Store,
    snapshot_id: str,
    pid: str | int | None,
    *,
    role: str,
    service: str,
    timeout: float,
    fd_warn: int,
    path_warn: int,
    top_n: int,
) -> None:
    if pid in (None, ""):
        return
    pid_text = str(pid)
    code, out, err, timed_out, duration_ms = run_command(
        ["lsof", "-nP", "-F", "pcftn", "-p", pid_text],
        timeout=timeout,
    )
    if code != 0 or timed_out or not out.strip():
        store.emit(
            snapshot_id,
            "process_lsof_summary",
            role=role,
            service=service,
            pid=pid_text,
            count=0,
            path_distinct=0,
            accessible=False,
            exit=code,
            timeout=timed_out,
            duration_ms=round(duration_ms, 1),
            error=err.strip() or "lsof returned no rows; this is expected for many root-owned system daemons",
        )
        return

    fd_count = 0
    path_counts: dict[str, int] = {}
    current_name = ""
    command = ""
    for raw_line in out.splitlines():
        if not raw_line:
            continue
        tag = raw_line[0]
        value = raw_line[1:]
        if tag == "c":
            command = value
        elif tag == "f":
            fd_count += 1
            current_name = ""
        elif tag == "n":
            current_name = value
            if current_name:
                path_counts[current_name] = path_counts.get(current_name, 0) + 1

    store.emit(
        snapshot_id,
        "process_lsof_summary",
        role=role,
        service=service,
        pid=pid_text,
        comm=command,
        count=fd_count,
        path_distinct=len(path_counts),
        accessible=True,
        exit=code,
        timeout=timed_out,
        duration_ms=round(duration_ms, 1),
    )
    if fd_count >= fd_warn:
        store.emit(
            snapshot_id,
            "health_signal",
            "warning",
            signal="process_fd_count_high",
            role=role,
            service=service,
            pid=pid_text,
            value=fd_count,
        )

    for path, count in sorted(path_counts.items(), key=lambda item: item[1], reverse=True)[:top_n]:
        store.emit(
            snapshot_id,
            "process_lsof_path_count",
            role=role,
            service=service,
            pid=pid_text,
            count=count,
            path=path,
        )
        if count >= path_warn:
            store.emit(
                snapshot_id,
                "health_signal",
                "warning",
                signal="process_fd_path_repeated",
                role=role,
                service=service,
                pid=pid_text,
                value=count,
                path=path,
            )


def collect_syspolicyd_health(
    store: Store,
    snapshot_id: str,
    args: argparse.Namespace,
) -> None:
    service = f"system/{SYSPOLICY_LABEL}"
    service_data = collect_launch_service(
        store,
        snapshot_id,
        service,
        args.command_timeout,
        warn_if_missing=True,
        warn_if_not_running=True,
    )
    pid = service_data.get("pid")
    resource_data = collect_process_resource(
        store,
        snapshot_id,
        pid,
        role="syspolicyd",
        service=service,
        timeout=args.command_timeout,
        cpu_warn=args.syspolicyd_cpu_warn,
        rss_warn_mb=args.syspolicyd_rss_warn_mb,
    )
    collect_process_resource_delta(
        store,
        snapshot_id,
        resource_data,
        role="syspolicyd",
        rss_growth_warn_mb_per_minute=args.syspolicyd_rss_growth_warn_mb_per_minute,
        rss_error_mb=args.syspolicyd_rss_error_mb,
    )
    collect_process_lsof(
        store,
        snapshot_id,
        pid,
        role="syspolicyd",
        service=service,
        timeout=args.lsof_timeout,
        fd_warn=args.syspolicyd_fd_warn,
        path_warn=args.syspolicyd_path_warn,
        top_n=args.top,
    )


def collect_audio_registrar_health(
    store: Store,
    snapshot_id: str,
    args: argparse.Namespace,
) -> None:
    services = [
        f"system/{AUDIO_COMPONENT_REGISTRAR_LABEL}",
        f"gui/{os.getuid()}/{AUDIO_COMPONENT_REGISTRAR_LABEL}",
    ]
    for service in services:
        service_data = collect_launch_service(
            store,
            snapshot_id,
            service,
            args.command_timeout,
            warn_if_missing=True,
            warn_if_not_running=True,
        )
        collect_process_resource(
            store,
            snapshot_id,
            service_data.get("pid"),
            role="audio_component_registrar",
            service=service,
            timeout=args.command_timeout,
        )


def read_plist_value(plist_path: Path, key: str, timeout: float) -> str:
    code, out, _err, timed_out, _duration_ms = run_command(
        ["plutil", "-extract", key, "raw", "-o", "-", str(plist_path)],
        timeout=timeout,
    )
    return out.strip() if code == 0 and not timed_out else ""


def collect_codex_config_snapshot(
    store: Store,
    snapshot_id: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    config_path = args.codex_config.expanduser()
    info_plist = args.codex_app.expanduser() / "Contents" / "Info.plist"
    app_path = args.codex_app.expanduser()
    app_version = ""
    app_build = ""
    if info_plist.exists():
        app_version = read_plist_value(info_plist, "CFBundleShortVersionString", args.command_timeout)
        app_build = read_plist_value(info_plist, "CFBundleVersion", args.command_timeout)

    data: dict[str, Any] = {}
    parse_error = ""
    if config_path.exists():
        try:
            data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            parse_error = f"{type(exc).__name__}: {exc}"

    notify = data.get("notify") if isinstance(data, dict) else None
    notify_items = notify if isinstance(notify, list) else []
    notify_uses_sky = any("SkyComputerUseClient" in str(item) for item in notify_items)

    computer_use_enabled = plugin_enabled(data, "computer-use@openai-bundled")
    chrome_enabled = plugin_enabled(data, "chrome@openai-bundled")

    native_hosts_path = args.codex_chrome_native_hosts.expanduser()
    native_host_parse_error = ""
    native_host_extension_present = False
    if native_hosts_path.exists():
        try:
            native_hosts_text = native_hosts_path.read_text(encoding="utf-8")
            json.loads(native_hosts_text)
            native_host_extension_present = CODEX_CHROME_EXTENSION_ID in native_hosts_text
        except (OSError, json.JSONDecodeError) as exc:
            native_host_parse_error = f"{type(exc).__name__}: {exc}"

    snapshot = {
        "app_path": str(app_path),
        "app_exists": app_path.exists(),
        "info_plist_exists": info_plist.exists(),
        "app_version": app_version,
        "app_build": app_build,
        "config_path": str(config_path),
        "config_exists": config_path.exists(),
        "config_parse_ok": config_path.exists() and not parse_error,
        "config_error": parse_error,
        "notify_uses_sky_computer_use": notify_uses_sky,
        "plugin_computer_use_enabled": computer_use_enabled if computer_use_enabled is not None else "",
        "plugin_chrome_enabled": chrome_enabled if chrome_enabled is not None else "",
        "chrome_native_hosts_path": str(native_hosts_path),
        "chrome_native_hosts_exists": native_hosts_path.exists(),
        "chrome_native_hosts_parse_ok": native_hosts_path.exists() and not native_host_parse_error,
        "chrome_native_hosts_error": native_host_parse_error,
        "chrome_native_extension_id_present": native_host_extension_present,
    }
    store.emit(snapshot_id, "codex_config_snapshot", **snapshot)

    if parse_error:
        store.emit(
            snapshot_id,
            "health_signal",
            "warning",
            signal="codex_config_parse_failed",
            value=1,
            detail=parse_error,
        )
    if native_host_parse_error:
        store.emit(
            snapshot_id,
            "health_signal",
            "warning",
            signal="codex_chrome_native_hosts_parse_failed",
            value=1,
            detail=native_host_parse_error,
        )
    if computer_use_enabled is False and notify_uses_sky:
        store.emit(
            snapshot_id,
            "health_signal",
            "warning",
            signal="codex_computer_use_notify_configured",
            value=1,
            detail="Codex notify still points to SkyComputerUseClient while the bundled computer-use plugin is disabled",
        )
    return snapshot


def collect_codex_process_summary(
    store: Store,
    snapshot_id: str,
    args: argparse.Namespace,
    codex_config: dict[str, Any],
) -> dict[str, Any]:
    code, out, err, timed_out, duration_ms = run_command(
        ["ps", "axww", "-o", "command="],
        timeout=args.command_timeout,
    )
    if code != 0 or timed_out:
        store.emit(
            snapshot_id,
            "codex_process_summary",
            exit=code,
            timeout=timed_out,
            duration_ms=round(duration_ms, 1),
            error=err.strip(),
        )
        store.emit(
            snapshot_id,
            "health_signal",
            "warning",
            signal="codex_process_summary_failed",
            value=code,
            timeout=timed_out,
            detail=err.strip() or "ps did not finish before timeout",
        )
        return {}

    role_counts: dict[str, int] = {}
    for command in out.splitlines():
        role = codex_process_role(command)
        if not role:
            continue
        role_counts[role] = role_counts.get(role, 0) + 1

    def count(role: str) -> int:
        return role_counts.get(role, 0)

    process_summary = {
        "exit": code,
        "timeout": timed_out,
        "duration_ms": round(duration_ms, 1),
        "codex_main_count": count("codex_main"),
        "codex_app_server_count": count("codex_app_server"),
        "codex_service_count": count("codex_service"),
        "codex_renderer_count": count("codex_renderer"),
        "codex_crashpad_count": count("codex_crashpad"),
        "node_repl_count": count("codex_node_repl"),
        "sky_computer_use_count": count("codex_sky_computer_use"),
        "chrome_extension_host_count": count("codex_chrome_extension_host"),
    }
    store.emit(snapshot_id, "codex_process_summary", **process_summary)

    computer_use_enabled = codex_config.get("plugin_computer_use_enabled")
    chrome_enabled = codex_config.get("plugin_chrome_enabled")
    if computer_use_enabled is False and count("codex_sky_computer_use") > 0:
        store.emit(
            snapshot_id,
            "health_signal",
            "warning",
            signal="codex_disabled_computer_use_process_running",
            value=count("codex_sky_computer_use"),
            detail="SkyComputerUseClient is running while the bundled computer-use plugin is disabled",
        )
    if chrome_enabled is False and count("codex_chrome_extension_host") > 0:
        store.emit(
            snapshot_id,
            "health_signal",
            "warning",
            signal="codex_disabled_chrome_process_running",
            value=count("codex_chrome_extension_host"),
            detail="Codex Chrome extension host is running while the bundled chrome plugin is disabled",
        )
    if count("codex_node_repl") >= args.codex_node_repl_warn:
        store.emit(
            snapshot_id,
            "health_signal",
            "warning",
            signal="codex_node_repl_many",
            value=count("codex_node_repl"),
            detail="Codex app-server has many node_repl child processes",
        )
    return process_summary


def collect_trustd_health(
    store: Store,
    snapshot_id: str,
    args: argparse.Namespace,
) -> None:
    code, out, err, timed_out, _duration_ms = run_command(["pgrep", "-x", "trustd"], timeout=args.command_timeout)
    pids = [line.strip() for line in out.splitlines() if line.strip()]
    if timed_out:
        store.emit(
            snapshot_id,
            "health_signal",
            "warning",
            signal="trustd_pgrep_timeout",
            value=code,
            detail=err.strip() or "pgrep trustd did not finish before timeout",
        )
        return

    resources: list[dict[str, Any]] = []
    for pid in pids:
        resource_data = collect_process_resource(
            store,
            snapshot_id,
            pid,
            role="trustd",
            service="process/trustd",
            timeout=args.command_timeout,
            cpu_warn=args.trustd_cpu_warn,
            rss_warn_mb=args.trustd_rss_warn_mb,
        )
        if resource_data:
            resources.append(resource_data)

    if not resources:
        return
    largest = max(
        resources,
        key=lambda item: parse_float(str(item.get("rss_mb") or "")) or 0,
    )
    collect_process_resource_delta(
        store,
        snapshot_id,
        largest,
        role="trustd",
        rss_growth_warn_mb_per_minute=args.trustd_rss_growth_warn_mb_per_minute,
        rss_error_mb=args.trustd_rss_error_mb,
    )


def collect_code_sign_clone_status(
    store: Store,
    snapshot_id: str,
    args: argparse.Namespace,
) -> None:
    for path in candidate_code_sign_clone_paths():
        exists = path.exists()
        status: dict[str, Any] = {
            "path": str(path),
            "exists": exists,
        }
        if not exists:
            store.emit(snapshot_id, "code_sign_clone_status", **status)
            continue

        code, out, err, timed_out, _duration_ms = run_command(
            ["du", "-sk", str(path)],
            timeout=args.code_sign_clone_timeout,
        )
        size_kb: int | None = None
        if code == 0 and not timed_out and out.strip():
            size_kb = parse_int(out.split()[0])
        size_mb = round(size_kb / 1024, 1) if size_kb is not None else ""
        status.update(
            {
                "size_mb": size_mb,
                "du_timeout": timed_out,
                "du_error": err.strip(),
            }
        )
        store.emit(snapshot_id, "code_sign_clone_status", **status)

        if timed_out:
            store.emit(
                snapshot_id,
                "health_signal",
                "warning",
                signal="code_sign_clone_du_timeout",
                value=code,
                detail=f"du timed out for {path}",
            )
            continue

        if not isinstance(size_mb, float):
            continue
        if size_mb >= args.code_sign_clone_warn_mb:
            store.emit(
                snapshot_id,
                "health_signal",
                "warning",
                signal="code_sign_clone_size_high",
                value=size_mb,
                detail=f"Codex code_sign_clone is {size_mb} MiB",
            )

        if store.conn is None:
            continue
        state_key = f"last_code_sign_clone_status:{path}"
        previous_raw = store.get_state(state_key)
        current = {"ts": utc_now(), "size_mb": size_mb}
        if previous_raw:
            try:
                previous = json.loads(previous_raw)
                previous_ts = dt.datetime.fromisoformat(str(previous["ts"]).replace("Z", "+00:00"))
                previous_size = float(previous.get("size_mb"))
                now = dt.datetime.now(dt.timezone.utc)
                elapsed_seconds = max((now - previous_ts).total_seconds(), 1)
                delta_mb = round(size_mb - previous_size, 1)
                growth = round((size_mb - previous_size) / elapsed_seconds * 60, 1)
                store.emit(
                    snapshot_id,
                    "code_sign_clone_delta",
                    path=str(path),
                    size_mb=size_mb,
                    previous_size_mb=previous_size,
                    delta_mb=delta_mb,
                    growth_mb_per_minute=growth,
                    elapsed_seconds=round(elapsed_seconds, 1),
                )
                if growth >= args.code_sign_clone_growth_warn_mb_per_minute:
                    store.emit(
                        snapshot_id,
                        "health_signal",
                        "warning",
                        signal="code_sign_clone_growth_high",
                        value=growth,
                        detail="Codex code_sign_clone is growing quickly",
                    )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                pass
        store.set_state(state_key, json.dumps(current, sort_keys=True))


def collect_limits(store: Store, snapshot_id: str, timeout: float) -> None:
    maxproc_code, maxproc_out, maxproc_err, maxproc_timeout, maxproc_ms = run_command(
        ["launchctl", "limit", "maxproc"], timeout=timeout
    )
    maxfiles_code, maxfiles_out, maxfiles_err, maxfiles_timeout, maxfiles_ms = run_command(
        ["launchctl", "limit", "maxfiles"], timeout=timeout
    )
    sysctl_code, sysctl_out, sysctl_err, sysctl_timeout, sysctl_ms = run_command(
        ["sysctl", "-n", "kern.maxproc", "kern.maxprocperuid", "kern.maxfiles", "kern.maxfilesperproc"],
        timeout=timeout,
    )

    maxproc_soft, maxproc_hard = parse_launchctl_limit(maxproc_out, "maxproc")
    maxfiles_soft, maxfiles_hard = parse_launchctl_limit(maxfiles_out, "maxfiles")
    sys_values = sysctl_out.split()
    nofile_soft, nofile_hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    nproc_soft, nproc_hard = resource.getrlimit(resource.RLIMIT_NPROC)

    store.emit(
        snapshot_id,
        "limits",
        maxproc_soft=maxproc_soft,
        maxproc_hard=maxproc_hard,
        maxproc_exit=maxproc_code,
        maxproc_timeout=maxproc_timeout,
        maxproc_duration_ms=round(maxproc_ms, 1),
        maxproc_error=maxproc_err.strip(),
        maxfiles_soft=maxfiles_soft,
        maxfiles_hard=maxfiles_hard,
        maxfiles_exit=maxfiles_code,
        maxfiles_timeout=maxfiles_timeout,
        maxfiles_duration_ms=round(maxfiles_ms, 1),
        maxfiles_error=maxfiles_err.strip(),
        kern_maxproc=sys_values[0] if len(sys_values) > 0 else "",
        kern_maxprocperuid=sys_values[1] if len(sys_values) > 1 else "",
        kern_maxfiles=sys_values[2] if len(sys_values) > 2 else "",
        kern_maxfilesperproc=sys_values[3] if len(sys_values) > 3 else "",
        sysctl_exit=sysctl_code,
        sysctl_timeout=sysctl_timeout,
        sysctl_duration_ms=round(sysctl_ms, 1),
        sysctl_error=sysctl_err.strip(),
        rlimit_nofile_soft=nofile_soft,
        rlimit_nofile_hard=nofile_hard,
        rlimit_nproc_soft=nproc_soft,
        rlimit_nproc_hard=nproc_hard,
    )

    soft = parse_int(maxfiles_soft)
    if soft is not None and soft <= 1024:
        store.emit(
            snapshot_id,
            "health_signal",
            "warning",
            signal="maxfiles_soft_low",
            value=soft,
            detail="GUI launchd maxfiles soft limit is low",
        )


def collect_system_context(store: Store, snapshot_id: str, timeout: float) -> None:
    sw_code, sw_out, sw_err, sw_timeout, sw_ms = run_command(["sw_vers"], timeout=timeout)
    boot_code, boot_out, boot_err, boot_timeout, boot_ms = run_command(
        ["sysctl", "-n", "kern.boottime"], timeout=timeout
    )
    loadavg = os.getloadavg()
    store.emit(
        snapshot_id,
        "system_context",
        hostname=socket.gethostname(),
        username=getpass.getuser(),
        pid=os.getpid(),
        python=sys.version.split()[0],
        executable=sys.executable,
        platform=platform.platform(),
        machine=platform.machine(),
        loadavg_1=round(loadavg[0], 2),
        loadavg_5=round(loadavg[1], 2),
        loadavg_15=round(loadavg[2], 2),
        sw_vers=sw_out.strip(),
        sw_vers_exit=sw_code,
        sw_vers_timeout=sw_timeout,
        sw_vers_duration_ms=round(sw_ms, 1),
        sw_vers_error=sw_err.strip(),
        boottime=boot_out.strip(),
        boottime_exit=boot_code,
        boottime_timeout=boot_timeout,
        boottime_duration_ms=round(boot_ms, 1),
        boottime_error=boot_err.strip(),
    )


def collect_process_counts(store: Store, snapshot_id: str, top_n: int, timeout: float) -> None:
    code, out, err, timed_out, duration_ms = run_command(
        ["ps", "-axo", "user=,ppid=,pid=,stat=,comm="], timeout=timeout
    )
    if code != 0 or timed_out:
        store.emit(
            snapshot_id,
            "health_signal",
            "error",
            signal="ps_failed",
            value=code,
            timeout=timed_out,
            duration_ms=round(duration_ms, 1),
            detail=err.strip(),
        )
        return

    user_counts: dict[str, int] = {}
    command_counts: dict[str, int] = {}
    parent_counts: dict[str, int] = {}
    zombies: list[tuple[str, str, str, str]] = []
    total = 0
    current_user = getpass.getuser()
    current_user_total = 0

    for line in out.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        user, ppid, pid, stat, comm = parts
        total += 1
        if user == current_user:
            current_user_total += 1
        user_counts[user] = user_counts.get(user, 0) + 1
        command_counts[comm] = command_counts.get(comm, 0) + 1
        parent_counts[ppid] = parent_counts.get(ppid, 0) + 1
        if "Z" in stat:
            zombies.append((stat, ppid, pid, comm))

    store.emit(
        snapshot_id,
        "process_summary",
        total=total,
        user=current_user,
        user_total=current_user_total,
        zombie_total=len(zombies),
        ps_duration_ms=round(duration_ms, 1),
    )
    if zombies:
        store.emit(
            snapshot_id,
            "health_signal",
            "warning",
            signal="zombies_present",
            value=len(zombies),
            detail="zombie processes exist",
        )

    for user, count in sorted(user_counts.items(), key=lambda item: item[1], reverse=True)[:top_n]:
        store.emit(snapshot_id, "user_process_count", count=count, user=user)

    for comm, count in sorted(command_counts.items(), key=lambda item: item[1], reverse=True)[:top_n]:
        store.emit(snapshot_id, "command_process_count", count=count, comm=comm)

    for ppid, count in sorted(parent_counts.items(), key=lambda item: item[1], reverse=True)[:top_n]:
        parent_comm = ""
        if ppid != "0":
            parent_code, parent_out, _, _, _ = run_command(["ps", "-p", ppid, "-o", "comm="], timeout=1)
            if parent_code == 0:
                parent_comm = parent_out.strip()
        store.emit(snapshot_id, "parent_process_count", count=count, ppid=ppid, parent_comm=parent_comm)

    for stat, ppid, pid, comm in zombies[:top_n]:
        store.emit(snapshot_id, "zombie", stat=stat, ppid=ppid, pid=pid, comm=comm)


def collect_fd_top(store: Store, snapshot_id: str, top_n: int, fd_warn: int, timeout: float) -> None:
    code, out, err, timed_out, duration_ms = run_command(["lsof", "-nP"], timeout=timeout)
    if code != 0 or timed_out:
        store.emit(
            snapshot_id,
            "health_signal",
            "error",
            signal="lsof_failed" if not timed_out else "lsof_timeout",
            value=code,
            timeout=timed_out,
            duration_ms=round(duration_ms, 1),
            detail=err.strip() or "lsof did not finish before timeout",
        )
        return

    counts: dict[str, tuple[int, str]] = {}
    fd_pattern = re.compile(r"^\d+[A-Za-z]*$")
    for line in out.splitlines()[1:]:
        parts = line.split(None, 8)
        if len(parts) < 5:
            continue
        command, pid, _user, fd = parts[:4]
        if not fd_pattern.match(fd):
            continue
        current_count, current_command = counts.get(pid, (0, command))
        counts[pid] = (current_count + 1, current_command)

    for pid, (count, short_comm) in sorted(counts.items(), key=lambda item: item[1][0], reverse=True)[:top_n]:
        comm = short_comm
        ps_code, ps_out, _, _, _ = run_command(["ps", "-p", pid, "-o", "comm="], timeout=1)
        if ps_code == 0 and ps_out.strip():
            comm = ps_out.strip()
        store.emit(
            snapshot_id,
            "fd_top",
            count=count,
            pid=pid,
            short_comm=short_comm,
            comm=comm,
            lsof_duration_ms=round(duration_ms, 1),
        )
        if count >= fd_warn:
            store.emit(
                snapshot_id,
                "health_signal",
                "warning",
                signal="fd_count_high",
                value=count,
                pid=pid,
                comm=comm,
            )


def collect_cpu_top(store: Store, snapshot_id: str, top_n: int, timeout: float) -> None:
    code, out, err, timed_out, duration_ms = run_command(
        ["ps", "-axo", "pid=,ppid=,stat=,%cpu=,rss=,etime=,comm="],
        timeout=timeout,
    )
    if code != 0 or timed_out:
        store.emit(
            snapshot_id,
            "health_signal",
            "warning",
            signal="cpu_top_failed" if not timed_out else "cpu_top_timeout",
            value=code,
            timeout=timed_out,
            duration_ms=round(duration_ms, 1),
            detail=err.strip() or "ps cpu top did not finish before timeout",
        )
        return

    rows: list[dict[str, Any]] = []
    for line in out.splitlines():
        parts = line.split(None, 6)
        if len(parts) < 7:
            continue
        pid, ppid, stat, cpu, rss, etime, comm = parts
        cpu_value = parse_float(cpu)
        rss_kb = parse_int(rss)
        if cpu_value is None:
            continue
        rows.append(
            {
                "pid": pid,
                "ppid": ppid,
                "stat": stat,
                "cpu_percent": cpu_value,
                "rss_mb": round(rss_kb / 1024, 1) if rss_kb is not None else "",
                "etime": etime,
                "comm": comm,
            }
        )

    for row in sorted(rows, key=lambda item: item["cpu_percent"], reverse=True)[:top_n]:
        parent_comm = ""
        ppid = str(row["ppid"])
        if ppid != "0":
            parent_code, parent_out, _, _, _ = run_command(["ps", "-p", ppid, "-o", "comm="], timeout=1)
            if parent_code == 0:
                parent_comm = parent_out.strip()
        store.emit(
            snapshot_id,
            "process_cpu_top",
            pid=row["pid"],
            ppid=row["ppid"],
            parent_comm=parent_comm,
            stat=row["stat"],
            cpu_percent=row["cpu_percent"],
            rss_mb=row["rss_mb"],
            etime=row["etime"],
            comm=row["comm"],
            ps_duration_ms=round(duration_ms, 1),
        )


def collect_spawn_check(store: Store, snapshot_id: str, timeout: float) -> bool:
    checks = [
        ("true", ["/usr/bin/true"]),
        ("bash_colon", ["/bin/bash", "-c", ":"]),
        ("zsh_colon", ["/bin/zsh", "-c", ":"]),
        ("python_import_sqlite", [sys.executable, "-c", "import sqlite3"]),
    ]
    ok = True
    for name, command in checks:
        code, out, err, timed_out, duration_ms = run_command(command, timeout=timeout)
        store.emit(
            snapshot_id,
            "spawn_check",
            name=name,
            command=shlex.join(command),
            exit=code,
            timeout=timed_out,
            duration_ms=round(duration_ms, 1),
            stdout=out.strip(),
            stderr=err.strip(),
        )
        if code != 0 or timed_out:
            ok = False
            store.emit(
                snapshot_id,
                "health_signal",
                "critical",
                signal="spawn_failed",
                value=code,
                name=name,
                timeout=timed_out,
                detail=err.strip() or out.strip() or "spawn check failed",
            )
    return ok


def collect_app_assess(
    store: Store,
    snapshot_id: str,
    app_paths: list[str],
    timeout: float,
    *,
    run_codesign: bool,
    run_spctl: bool,
) -> bool:
    ok = True
    for app in app_paths:
        path = Path(app).expanduser()
        if not path.exists():
            store.emit(snapshot_id, "app_bundle", app=str(path), exit=66, output="app path does not exist")
            store.emit(
                snapshot_id,
                "health_signal",
                "warning",
                signal="app_missing",
                value=66,
                app=str(path),
                detail="app path does not exist",
            )
            ok = False
            continue

        info_plist = path / "Contents" / "Info.plist"
        if not info_plist.exists():
            store.emit(snapshot_id, "app_bundle", app=str(path), exit=65, output="Contents/Info.plist missing")
            store.emit(
                snapshot_id,
                "health_signal",
                "error",
                signal="app_bundle_invalid",
                value=65,
                app=str(path),
                detail="Contents/Info.plist missing",
            )
            ok = False
            continue

        exe_code, exe_out, exe_err, exe_timed_out, exe_ms = run_command(
            ["plutil", "-extract", "CFBundleExecutable", "raw", "-o", "-", str(info_plist)],
            timeout=timeout,
        )
        executable_name = exe_out.strip()
        executable_path = path / "Contents" / "MacOS" / executable_name
        bundle_ok = exe_code == 0 and bool(executable_name) and executable_path.exists()
        store.emit(
            snapshot_id,
            "app_bundle",
            app=str(path),
            exit=0 if bundle_ok else exe_code or 67,
            timeout=exe_timed_out,
            duration_ms=round(exe_ms, 1),
            executable=executable_name,
            executable_exists=executable_path.exists() if executable_name else False,
            output=(exe_out + exe_err).strip(),
        )
        if not bundle_ok:
            ok = False
            store.emit(
                snapshot_id,
                "health_signal",
                "error",
                signal="app_bundle_invalid",
                value=exe_code,
                app=str(path),
                timeout=exe_timed_out,
                detail=(exe_err or exe_out).strip() or "bundle executable is missing",
            )
            continue

        if run_codesign:
            sign_code, sign_out, sign_err, sign_timed_out, sign_ms = run_command(
                ["codesign", "--verify", "--verbose=2", str(path)],
                timeout=timeout,
            )
            sign_output = (sign_out + sign_err).strip()
            store.emit(
                snapshot_id,
                "app_codesign_verify",
                app=str(path),
                exit=sign_code,
                timeout=sign_timed_out,
                duration_ms=round(sign_ms, 1),
                output=sign_output,
            )
            if sign_timed_out or RESOURCE_ERROR_RE.search(sign_output):
                ok = False
                store.emit(
                    snapshot_id,
                    "health_signal",
                    "error",
                    signal="app_codesign_resource_failure" if not sign_timed_out else "app_codesign_timeout",
                    value=sign_code,
                    app=str(path),
                    timeout=sign_timed_out,
                    detail=sign_output or "codesign did not finish before timeout",
                )
        else:
            store.emit(snapshot_id, "app_codesign_verify_skipped", app=str(path), reason="periodic_probe_interval")

        if run_spctl:
            code, out, err, timed_out, duration_ms = run_command(
                ["spctl", "--assess", "--type", "execute", "--verbose=4", str(path)],
                timeout=timeout,
            )
            output = (out + err).strip()
            store.emit(
                snapshot_id,
                "app_assess",
                app=str(path),
                exit=code,
                timeout=timed_out,
                duration_ms=round(duration_ms, 1),
                output=output,
            )
            if timed_out or RESOURCE_ERROR_RE.search(output):
                ok = False
                store.emit(
                    snapshot_id,
                    "health_signal",
                    "error",
                    signal="app_assess_resource_failure" if not timed_out else "app_assess_timeout",
                    value=code,
                    app=str(path),
                    timeout=timed_out,
                    detail=output or "spctl did not finish before timeout",
                )
        else:
            store.emit(snapshot_id, "app_assess_skipped", app=str(path), reason="periodic_probe_interval")
    return ok


def collect_macos_log_excerpt(
    store: Store,
    snapshot_id: str,
    app_paths: list[str],
    timeout: float,
    max_lines: int,
) -> None:
    app_terms = []
    for app in app_paths:
        name = Path(app).stem
        if name:
            app_terms.append(name)
    app_predicate = " OR ".join(f'eventMessage CONTAINS[c] "{term}"' for term in app_terms)
    predicate = (
        'process == "launchservicesd" OR process == "lsd" OR '
        'process == "runningboardd" OR eventMessage CONTAINS[c] "LSOpen" OR '
        'eventMessage CONTAINS[c] "spawn"'
    )
    if app_predicate:
        predicate = f"{predicate} OR {app_predicate}"

    code, out, err, timed_out, duration_ms = run_command(
        ["/usr/bin/log", "show", "--last", "5m", "--style", "compact", "--predicate", predicate],
        timeout=timeout,
    )
    lines = (out + err).splitlines()
    for line in lines[-max_lines:]:
        store.emit(
            snapshot_id,
            "macos_log_excerpt",
            line=line,
            exit=code,
            timeout=timed_out,
            duration_ms=round(duration_ms, 1),
        )
    if timed_out:
        store.emit(
            snapshot_id,
            "health_signal",
            "warning",
            signal="macos_log_timeout",
            value=code,
            detail="log show did not finish before timeout",
        )


def classify_passive_log_line(line: str) -> tuple[str, str] | None:
    lower = line.lower()
    if re.search(r"\slog\[\d+:", lower):
        return None
    if (
        "syspolicyd[" in lower
        and (
            "unix error exception: 24" in lower
            or "too many open files" in lower
            or "failed to generate secstaticcode" in lower
        )
    ):
        return "syspolicyd_assessment_failure", "error"
    if (
        ("syspolicyd[" in lower or "trustd[" in lower)
        and ("application-groups" in lower or "entitlement" in lower)
        and ("codex" in lower or "openai" in lower or "com.openai.sky" in lower)
    ):
        return "codex_entitlement_log_warning", "warning"
    if (
        ("syspolicyd[" in lower or "trustd[" in lower)
        and "extension-host" in lower
        and ("codex" in lower or "openai" in lower or CODEX_CHROME_EXTENSION_ID in lower)
    ):
        return "codex_extension_host_log_warning", "warning"
    if (
        ("syspolicyd[" in lower or "trustd[" in lower)
        and ("skycomputeruseclient" in lower or "codex computer use" in lower or "com.openai.sky" in lower)
    ):
        return "codex_computer_use_log_warning", "warning"
    if "devicecheck" in lower and ("codex" in lower or "openai" in lower):
        return "codex_devicecheck_log_warning", "warning"
    if "code_sign_clone" in lower and ("codex" in lower or "openai" in lower):
        return "codex_code_sign_clone_log_warning", "warning"
    if "-9405" in lower and "music" in lower:
        return "music_audio_9405", "error"
    if "failed lookup: name = com.apple.audio.audiocomponentregistrar" in lower:
        return "audio_registrar_lookup_failed", "error"
    if "removing service: com.apple.audio.audiocomponentregistrar" in lower:
        return "audio_registrar_removed", "warning"
    if "service inactive: com.apple.audio.audiocomponentregistrar" in lower:
        return "audio_registrar_inactive", "warning"
    if (
        "audiocomponentregistrar" in lower
        and "failed to check-in, peer may have been unloaded" in lower
    ):
        return "audio_registrar_unloaded", "warning"
    return None


def collect_passive_log_signals(
    store: Store,
    snapshot_id: str,
    timeout: float,
    max_lines: int,
    last_minutes: int,
    syspolicyd_log_error_count: int,
) -> bool:
    predicate = (
        'eventMessage CONTAINS[c] "UNIX error exception: 24" OR '
        'eventMessage CONTAINS[c] "Too many open files" OR '
        'eventMessage CONTAINS[c] "Failed to generate SecStaticCode" OR '
        '(eventMessage CONTAINS[c] "application-groups" AND '
        '(eventMessage CONTAINS[c] "Codex" OR eventMessage CONTAINS[c] "OpenAI" OR '
        'eventMessage CONTAINS[c] "com.openai.sky")) OR '
        '(eventMessage CONTAINS[c] "entitlement" AND '
        '(eventMessage CONTAINS[c] "Codex" OR eventMessage CONTAINS[c] "OpenAI" OR '
        'eventMessage CONTAINS[c] "com.openai.sky")) OR '
        '(eventMessage CONTAINS[c] "DeviceCheck" AND '
        '(eventMessage CONTAINS[c] "Codex" OR eventMessage CONTAINS[c] "OpenAI")) OR '
        '(eventMessage CONTAINS[c] "extension-host" AND '
        '(eventMessage CONTAINS[c] "Codex" OR eventMessage CONTAINS[c] "OpenAI" OR '
        f'eventMessage CONTAINS[c] "{CODEX_CHROME_EXTENSION_ID}")) OR '
        'eventMessage CONTAINS[c] "SkyComputerUseClient" OR '
        'eventMessage CONTAINS[c] "Codex Computer Use" OR '
        'eventMessage CONTAINS[c] "com.openai.sky" OR '
        '(eventMessage CONTAINS[c] "code_sign_clone" AND '
        '(eventMessage CONTAINS[c] "Codex" OR eventMessage CONTAINS[c] "OpenAI")) OR '
        'eventMessage CONTAINS[c] "OpenOutputUnit() failed! status:-9405" OR '
        'eventMessage CONTAINS[c] "SetupLocalAudioDevice() failed! status=-9405" OR '
        'eventMessage CONTAINS[c] "failed lookup: name = com.apple.audio.AudioComponentRegistrar" OR '
        'eventMessage CONTAINS[c] "removing service: com.apple.audio.AudioComponentRegistrar" OR '
        'eventMessage CONTAINS[c] "service inactive: com.apple.audio.AudioComponentRegistrar" OR '
        '(eventMessage CONTAINS[c] "AudioComponentRegistrar" AND '
        'eventMessage CONTAINS[c] "Failed to check-in, peer may have been unloaded")'
    )
    code, out, err, timed_out, duration_ms = run_command(
        [
            "/usr/bin/log",
            "show",
            "--last",
            f"{last_minutes}m",
            "--style",
            "compact",
            "--predicate",
            predicate,
        ],
        timeout=timeout,
    )
    raw_lines = (out + err).splitlines()
    matches: list[tuple[str, str, str]] = []
    category_counts: dict[tuple[str, str], int] = {}
    for line in raw_lines:
        classified = classify_passive_log_line(line)
        if classified is None:
            continue
        category, severity = classified
        matches.append((category, severity, line))
        key = (category, severity)
        category_counts[key] = category_counts.get(key, 0) + 1

    store.emit(
        snapshot_id,
        "macos_passive_log_scan",
        exit=code,
        timeout=timed_out,
        duration_ms=round(duration_ms, 1),
        last_minutes=last_minutes,
        raw_lines=len(raw_lines),
        matches=len(matches),
        predicate=predicate,
    )
    if timed_out:
        store.emit(
            snapshot_id,
            "health_signal",
            "warning",
            signal="macos_passive_log_timeout",
            value=code,
            detail="passive log scan did not finish before timeout",
        )

    for category, severity, line in matches[-max_lines:]:
        store.emit(
            snapshot_id,
            "macos_passive_log_match",
            severity,
            category=category,
            line=line,
            exit=code,
            timeout=timed_out,
            duration_ms=round(duration_ms, 1),
        )

    ok = True
    for (category, severity), count in sorted(category_counts.items()):
        signal_severity = severity
        detail = f"matched {count} macOS unified log line(s) in the last {last_minutes} minute(s)"
        if category == "syspolicyd_assessment_failure" and count < syspolicyd_log_error_count:
            signal_severity = "warning"
            detail = f"{detail}; below error threshold {syspolicyd_log_error_count}"
        if signal_severity == "error":
            ok = False
        store.emit(
            snapshot_id,
            "health_signal",
            signal_severity,
            signal=category,
            value=count,
            detail=detail,
        )
    return ok


def signal_fingerprint(signals: list[dict[str, Any]]) -> str:
    normalized = []
    for signal in signals:
        normalized.append(
            {
                "severity": signal.get("severity"),
                "signal": signal.get("signal"),
                "value": signal.get("value"),
                "name": signal.get("name"),
                "pid": signal.get("pid"),
                "comm": signal.get("comm"),
                "app": signal.get("app"),
            }
        )
    encoded = json.dumps(sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True)), sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def strongest_signal(signals: list[dict[str, Any]], signal_name: str, *, role: str = "") -> dict[str, Any] | None:
    matches = [
        signal
        for signal in signals
        if signal.get("signal") == signal_name and (not role or signal.get("role") == role)
    ]
    if not matches:
        return None
    return max(matches, key=lambda item: parse_float(str(item.get("value") or "")) or 0)


def build_brrr_incident(signals: list[dict[str, Any]], snapshot_id: str, status: str) -> dict[str, Any] | None:
    spawn_failed = strongest_signal(signals, "spawn_failed")
    syspolicyd_assessment_failure = strongest_signal(signals, "syspolicyd_assessment_failure")
    syspolicyd_rss_error = strongest_signal(signals, "process_rss_error", role="syspolicyd")
    collector_exception = strongest_signal(signals, "collector_exception")

    if spawn_failed:
        title = "macOS 无法正常启动进程"
        summary = "简单 spawn 检查失败，新的 app 或 shell 命令可能会打不开。"
        primary = spawn_failed
        kind = "spawn_failed"
    elif (
        syspolicyd_assessment_failure
        and (parse_float(str(syspolicyd_assessment_failure.get("value") or "")) or 0) >= 1000
    ):
        count = syspolicyd_assessment_failure.get("value", "")
        title = "Gatekeeper 正在大量失败"
        summary = f"最近日志里有 {count} 条 syspolicyd assessment 失败，app 启动可能受影响。"
        primary = syspolicyd_assessment_failure
        kind = "syspolicyd_assessment_failure"
    elif syspolicyd_rss_error:
        rss = syspolicyd_rss_error.get("value", "")
        title = "syspolicyd 内存异常增长"
        summary = f"syspolicyd RSS 已到 {rss} MiB，Gatekeeper 评估可能开始拖慢或失败。"
        primary = syspolicyd_rss_error
        kind = "syspolicyd_rss_error"
    elif collector_exception:
        title = "macOS 监控采集器异常"
        summary = "macos-session-health 自身采集失败，需要查看本机日志。"
        primary = collector_exception
        kind = "collector_exception"
    else:
        return None

    context: list[str] = []
    if syspolicyd_assessment_failure and syspolicyd_assessment_failure is not primary:
        context.append(f"syspolicyd_assessment_failure={syspolicyd_assessment_failure.get('value', '')}")
    if syspolicyd_rss_error and syspolicyd_rss_error is not primary:
        context.append(f"syspolicyd_rss_mb={syspolicyd_rss_error.get('value', '')}")
    if spawn_failed and spawn_failed is not primary:
        context.append(f"spawn_failed={spawn_failed.get('name', '') or spawn_failed.get('value', '')}")

    message_lines = [
        summary,
        f"状态：{status}。",
    ]
    if context:
        message_lines.append("同时看到：" + "，".join(context) + "。")
    message_lines.extend(
        [
            "建议：先看 `macos-session-health incident --hours 6 --format markdown`。",
            f"snapshot={snapshot_id}",
        ]
    )
    return {
        "kind": kind,
        "title": title,
        "message": "\n".join(message_lines),
        "primary_signal": primary.get("signal", ""),
        "primary_value": primary.get("value", ""),
    }


def signal_meets_min_severity(signal: dict[str, Any], min_severity: str) -> bool:
    severity = str(signal.get("severity") or "")
    return SEVERITY_RANK.get(severity, 0) >= SEVERITY_RANK[min_severity]


def should_send_brrr_notification(
    store: Store,
    snapshot_id: str,
    cooldown_minutes: int,
) -> bool:
    if store.conn is None:
        return True

    last_sent_at = store.get_state("last_brrr_notification_sent_at")
    now = dt.datetime.now(dt.timezone.utc)
    cooldown_elapsed = True

    if last_sent_at:
        try:
            last = dt.datetime.fromisoformat(last_sent_at.replace("Z", "+00:00"))
            cooldown_elapsed = now - last >= dt.timedelta(minutes=cooldown_minutes)
        except ValueError:
            cooldown_elapsed = True

    if not cooldown_elapsed:
        store.emit(
            snapshot_id,
            "brrr_notification_skipped",
            reason="cooldown_active",
            cooldown_minutes=cooldown_minutes,
            last_sent_at=last_sent_at or "",
        )
        return False

    store.set_state("last_brrr_notification_sent_at", utc_now())
    return True


def maybe_send_brrr_notification(
    store: Store,
    snapshot_id: str,
    args: argparse.Namespace,
    status: str,
) -> None:
    if not args.brrr_helper:
        return

    helper = Path(args.brrr_helper).expanduser()
    incident = build_brrr_incident(store.current_signals, snapshot_id, status)
    if incident is None:
        return

    if not helper.exists():
        store.emit(
            snapshot_id,
            "brrr_notification",
            "warning",
            exit=66,
            helper=str(helper),
            status=status,
            sent=False,
            error="brrr helper does not exist",
        )
        return

    if not should_send_brrr_notification(
        store,
        snapshot_id,
        args.brrr_notify_cooldown_minutes,
    ):
        return

    command = [
        str(helper),
        "--title",
        str(incident["title"]),
        "--message",
        str(incident["message"]),
        "--thread-id",
        args.brrr_thread_id,
        "--interruption-level",
        args.brrr_interruption_level,
    ]
    if args.brrr_open_url:
        command.extend(["--open-url", args.brrr_open_url])

    code, out, err, timed_out, duration_ms = run_command(
        command,
        timeout=args.brrr_timeout,
    )
    store.emit(
        snapshot_id,
        "brrr_notification",
        None if code == 0 and not timed_out else "warning",
        exit=code,
        timeout=timed_out,
        duration_ms=round(duration_ms, 1),
        helper=str(helper),
        status=status,
        title=incident["title"],
        incident_kind=incident["kind"],
        primary_signal=incident["primary_signal"],
        primary_value=incident["primary_value"],
        thread_id=args.brrr_thread_id,
        interruption_level=args.brrr_interruption_level,
        sent=code == 0 and not timed_out,
        stdout=out.strip(),
        stderr=err.strip(),
    )


def should_collect_log_excerpt(
    store: Store,
    snapshot_id: str,
    cooldown_minutes: int,
) -> bool:
    if store.conn is None:
        return True

    fingerprint = signal_fingerprint(store.current_signals)
    last_fingerprint = store.get_state("last_log_excerpt_signal_fingerprint")
    last_collected_at = store.get_state("last_log_excerpt_collected_at")
    now = dt.datetime.now(dt.timezone.utc)
    cooldown_elapsed = True

    if last_collected_at:
        try:
            last = dt.datetime.fromisoformat(last_collected_at.replace("Z", "+00:00"))
            cooldown_elapsed = now - last >= dt.timedelta(minutes=cooldown_minutes)
        except ValueError:
            cooldown_elapsed = True

    if fingerprint != last_fingerprint:
        reason = "signal_fingerprint_changed"
    elif cooldown_elapsed:
        reason = "cooldown_elapsed"
    else:
        store.emit(
            snapshot_id,
            "log_excerpt_skipped",
            reason="cooldown_active",
            cooldown_minutes=cooldown_minutes,
            signal_fingerprint=fingerprint,
            last_collected_at=last_collected_at or "",
        )
        return False

    store.set_state("last_log_excerpt_signal_fingerprint", fingerprint)
    store.set_state("last_log_excerpt_collected_at", utc_now())
    store.emit(
        snapshot_id,
        "log_excerpt_collecting",
        reason=reason,
        cooldown_minutes=cooldown_minutes,
        signal_fingerprint=fingerprint,
    )
    return True


def should_run_periodic_probe(
    store: Store,
    snapshot_id: str,
    key: str,
    interval_minutes: int,
) -> bool:
    if interval_minutes <= 0:
        store.emit(snapshot_id, "periodic_probe_skipped", probe=key, reason="disabled")
        return False
    if store.conn is None:
        return True

    state_key = f"last_probe_at:{key}"
    last_probe_at = store.get_state(state_key)
    now = dt.datetime.now(dt.timezone.utc)
    if last_probe_at:
        try:
            last = dt.datetime.fromisoformat(last_probe_at.replace("Z", "+00:00"))
            if now - last < dt.timedelta(minutes=interval_minutes):
                store.emit(
                    snapshot_id,
                    "periodic_probe_skipped",
                    probe=key,
                    reason="interval_active",
                    interval_minutes=interval_minutes,
                    last_probe_at=last_probe_at,
                )
                return False
        except ValueError:
            pass

    store.set_state(state_key, utc_now())
    return True


def snapshot(args: argparse.Namespace, store: Store, mode: str) -> str:
    snapshot_id = store.create_snapshot(mode, args.app)
    status = "ok"
    store.emit(
        snapshot_id,
        "snapshot_begin",
        sid=snapshot_id,
        mode=mode,
        db=str(args.db) if args.db else "",
        app_paths=json.dumps(args.app),
    )
    try:
        deleted = store.prune(args.retention_days)
        if deleted:
            store.emit(
                snapshot_id,
                "retention_prune",
                retention_days=args.retention_days,
                deleted_snapshots=deleted,
            )
        collect_system_context(store, snapshot_id, args.command_timeout)
        collect_limits(store, snapshot_id, args.command_timeout)
        collect_process_counts(store, snapshot_id, args.top, args.command_timeout)
        collect_cpu_top(store, snapshot_id, args.top, args.command_timeout)
        collect_fd_top(store, snapshot_id, args.top, args.fd_warn, args.lsof_timeout)
        codex_config = collect_codex_config_snapshot(store, snapshot_id, args)
        collect_codex_process_summary(store, snapshot_id, args, codex_config)
        collect_code_sign_clone_status(store, snapshot_id, args)
        collect_syspolicyd_health(store, snapshot_id, args)
        collect_trustd_health(store, snapshot_id, args)
        collect_audio_registrar_health(store, snapshot_id, args)
        passive_log_ok = True
        run_passive_log = should_run_periodic_probe(
            store,
            snapshot_id,
            "passive_log_scan",
            args.passive_log_interval_minutes,
        )
        if run_passive_log:
            passive_log_ok = collect_passive_log_signals(
                store,
                snapshot_id,
                args.log_timeout,
                args.passive_log_lines,
                args.passive_log_last_minutes,
                args.syspolicyd_log_error_count,
            )
        spawn_ok = collect_spawn_check(store, snapshot_id, args.spawn_check_timeout)
        run_spctl = should_run_periodic_probe(
            store,
            snapshot_id,
            "spctl_app_assess",
            args.spctl_interval_minutes,
        )
        run_codesign = should_run_periodic_probe(
            store,
            snapshot_id,
            "codesign_app_verify",
            args.codesign_interval_minutes,
        )
        app_ok = collect_app_assess(
            store,
            snapshot_id,
            args.app,
            args.app_assess_timeout,
            run_codesign=run_codesign,
            run_spctl=run_spctl,
        )
        signal_unhealthy = any(
            signal_meets_min_severity(signal, "error") for signal in store.current_signals
        )
        if signal_unhealthy or not spawn_ok or not app_ok or not passive_log_ok:
            status = "unhealthy"
            if (not spawn_ok or not app_ok) and args.collect_log_excerpt and should_collect_log_excerpt(
                store,
                snapshot_id,
                args.log_excerpt_cooldown_minutes,
            ):
                collect_macos_log_excerpt(
                    store,
                    snapshot_id,
                    args.app,
                    args.log_timeout,
                    args.log_lines,
                )
        maybe_send_brrr_notification(store, snapshot_id, args, status)
        store.emit(snapshot_id, "snapshot_end", sid=snapshot_id, status=status)
    except Exception as exc:
        status = "error"
        store.emit(
            snapshot_id,
            "health_signal",
            "critical",
            signal="collector_exception",
            value=type(exc).__name__,
            detail=str(exc),
        )
        store.emit(snapshot_id, "snapshot_end", sid=snapshot_id, status=status)
        raise
    finally:
        store.finish_snapshot(snapshot_id, status)
    return status


def fetch_event_names(conn: sqlite3.Connection) -> set[str]:
    try:
        rows = conn.execute("SELECT DISTINCT event FROM events ORDER BY event").fetchall()
    except sqlite3.Error as exc:
        raise CliError("unable to read events") from exc
    return {str(row[0]) for row in rows}


def query(
    db_path: Path,
    limit: int,
    event: str | None,
    signals_only: bool,
    output_format: str,
) -> int:
    conn = open_read_db(db_path)
    available_events = fetch_event_names(conn)
    if event and event not in KNOWN_EVENTS and event not in available_events:
        known = sorted(KNOWN_EVENTS | available_events)
        raise CliError(f"unknown event: {event}. Known events: {', '.join(known)}")

    where = []
    params: list[Any] = []
    if event:
        where.append("event = ?")
        params.append(event)
    if signals_only:
        where.append("event = 'health_signal'")
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    try:
        rows = conn.execute(
            f"""
            SELECT e.ts, e.event, e.severity, e.data_json, s.status, s.id AS snapshot_id
            FROM events e
            JOIN snapshots s ON s.id = e.snapshot_id
            {where_sql}
            ORDER BY e.id DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
    except sqlite3.Error as exc:
        raise CliError("unable to query events") from exc
    records: list[dict[str, Any]] = []
    for row in rows:
        data = json.loads(row["data_json"])
        record = {
            "ts": row["ts"],
            "event": row["event"],
            "severity": row["severity"] or "",
            "snapshot_status": row["status"] or "",
            "snapshot_id": row["snapshot_id"],
        }
        record.update(data)
        records.append(record)
    conn.close()
    print_records(records, output_format)
    return 0


def events(db_path: Path, output_format: str) -> int:
    conn = open_read_db(db_path)
    event_names = fetch_event_names(conn)
    conn.close()
    records = [{"event": event} for event in sorted(event_names)]
    print_records(records, output_format)
    return 0


def event_identity(event: str, data: dict[str, Any]) -> str:
    if event == "fd_top":
        return f"pid={data.get('pid', '')} comm={data.get('comm') or data.get('short_comm', '')}"
    if event == "process_lsof_summary":
        return f"role={data.get('role', '')} service={data.get('service', '')} pid={data.get('pid', '')}"
    if event == "process_lsof_path_count":
        return f"role={data.get('role', '')} service={data.get('service', '')} path={data.get('path', '')}"
    if event == "command_process_count":
        return f"comm={data.get('comm', '')}"
    if event == "parent_process_count":
        return f"ppid={data.get('ppid', '')} parent_comm={data.get('parent_comm', '')}"
    if event == "user_process_count":
        return f"user={data.get('user', '')}"
    return json.dumps(data, sort_keys=True, ensure_ascii=False)


def trend(db_path: Path, hours: float, limit: int, event: str, output_format: str) -> int:
    cutoff = (
        dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    ).isoformat(timespec="seconds").replace("+00:00", "Z")
    conn = open_read_db(db_path)
    try:
        rows = conn.execute(
            """
            SELECT e.ts, e.event, e.data_json, s.status, s.id AS snapshot_id
            FROM events e
            JOIN snapshots s ON s.id = e.snapshot_id
            WHERE e.event = ? AND e.ts >= ?
            ORDER BY e.id ASC
            """,
            (event, cutoff),
        ).fetchall()
    except sqlite3.Error as exc:
        raise CliError("unable to query trend") from exc
    conn.close()

    series: dict[str, list[tuple[str, int, str, str]]] = {}
    for row in rows:
        data = json.loads(row["data_json"])
        raw_count = data.get("count")
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            continue
        key = event_identity(event, data)
        series.setdefault(key, []).append(
            (row["ts"], count, row["status"] or "", row["snapshot_id"])
        )

    ranked = []
    for key, samples in series.items():
        if not samples:
            continue
        first_ts, first_count, _, _ = samples[0]
        last_ts, last_count, last_status, last_snapshot_id = samples[-1]
        max_count = max(sample[1] for sample in samples)
        min_count = min(sample[1] for sample in samples)
        ranked.append(
            {
                "identity": key,
                "first": first_count,
                "last": last_count,
                "delta": last_count - first_count,
                "max": max_count,
                "min": min_count,
                "samples": len(samples),
                "first_ts": first_ts,
                "last_ts": last_ts,
                "last_status": last_status,
                "last_snapshot_id": last_snapshot_id,
            }
        )

    ranked.sort(key=lambda item: (item["delta"], item["max"], item["last"]), reverse=True)
    records = []
    for item in ranked[:limit]:
        record = {"event": event}
        record.update(item)
        records.append(record)
    print_records(records, output_format)
    return 0


def load_recent_events(
    conn: sqlite3.Connection,
    *,
    cutoff: str,
    event: str,
    limit: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT e.ts, e.event, e.severity, e.data_json, s.status, s.id AS snapshot_id
        FROM events e
        JOIN snapshots s ON s.id = e.snapshot_id
        WHERE e.event = ? AND e.ts >= ?
        ORDER BY e.id DESC
        LIMIT ?
        """,
        (event, cutoff, limit),
    ).fetchall()
    records: list[dict[str, Any]] = []
    for row in rows:
        data = json.loads(row["data_json"])
        record = {
            "ts": row["ts"],
            "event": row["event"],
            "severity": row["severity"] or "",
            "snapshot_status": row["status"] or "",
            "snapshot_id": row["snapshot_id"],
        }
        record.update(data)
        records.append(record)
    return records


def load_latest_events(
    conn: sqlite3.Connection,
    *,
    event: str,
    limit: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT e.ts, e.event, e.severity, e.data_json, s.status, s.id AS snapshot_id
        FROM events e
        JOIN snapshots s ON s.id = e.snapshot_id
        WHERE e.event = ?
        ORDER BY e.id DESC
        LIMIT ?
        """,
        (event, limit),
    ).fetchall()
    records: list[dict[str, Any]] = []
    for row in rows:
        data = json.loads(row["data_json"])
        record = {
            "ts": row["ts"],
            "event": row["event"],
            "severity": row["severity"] or "",
            "snapshot_status": row["status"] or "",
            "snapshot_id": row["snapshot_id"],
        }
        record.update(data)
        records.append(record)
    return records


def latest_snapshot_id_for_event(records: list[dict[str, Any]]) -> str:
    return records[0]["snapshot_id"] if records else ""


def compact_record(record: dict[str, Any], keys: list[str]) -> str:
    parts = []
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            parts.append(f"{key}={value}")
    return " ".join(parts)


def render_incident_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# macos-session-health Incident Report",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- db: `{report['db']}`",
        f"- window_hours: `{report['window_hours']}`",
        "- runbook: `modules/bin/macos-session-health.md`",
        "",
        "## Snapshot Summary",
        "",
        f"- total: `{report['snapshot_summary']['total']}`",
        f"- unhealthy: `{report['snapshot_summary']['unhealthy']}`",
        f"- error: `{report['snapshot_summary']['error']}`",
        "",
        "## Signal Counts",
        "",
    ]
    if report["signal_counts"]:
        lines.append("| signal | severity | count | first | last | max_value |")
        lines.append("| --- | --- | ---: | --- | --- | ---: |")
        for row in report["signal_counts"]:
            lines.append(
                "| {signal} | {severity} | {count} | {first_ts} | {last_ts} | {max_value} |".format(
                    **row
                )
            )
    else:
        lines.append("No health signals in window.")

    lines.extend(["", "## Recent Health Signals", ""])
    for record in report["recent_health_signals"]:
        lines.append(
            f"- `{record['ts']}` `{record.get('severity', '')}` "
            + compact_record(record, ["signal", "value", "role", "pid", "app", "detail"])
        )
    if not report["recent_health_signals"]:
        lines.append("No recent health signals.")

    lines.extend(["", "## syspolicyd Resources", ""])
    for record in report["syspolicyd_resources"]:
        lines.append(
            f"- `{record['ts']}` "
            + compact_record(record, ["pid", "cpu_percent", "rss_mb", "etime", "stat"])
        )
    if not report["syspolicyd_resources"]:
        lines.append("No syspolicyd resource samples.")

    lines.extend(["", "## syspolicyd Deltas", ""])
    for record in report["syspolicyd_deltas"]:
        lines.append(
            f"- `{record['ts']}` "
            + compact_record(
                record,
                [
                    "pid",
                    "previous_pid",
                    "pid_changed",
                    "rss_mb",
                    "previous_rss_mb",
                    "rss_delta_mb",
                    "rss_growth_mb_per_minute",
                ],
            )
        )
    if not report["syspolicyd_deltas"]:
        lines.append("No syspolicyd delta samples.")

    lines.extend(["", "## Codex Diagnostics", ""])
    config = report.get("latest_codex_config") or {}
    if config:
        lines.append(
            "- config "
            + compact_record(
                config,
                [
                    "ts",
                    "app_version",
                    "app_build",
                    "plugin_computer_use_enabled",
                    "plugin_chrome_enabled",
                    "notify_uses_sky_computer_use",
                    "chrome_native_extension_id_present",
                ],
            )
        )
    else:
        lines.append("- config unavailable")

    process_summary = report.get("latest_codex_process_summary") or {}
    if process_summary:
        lines.append(
            "- processes "
            + compact_record(
                process_summary,
                [
                    "ts",
                    "codex_main_count",
                    "codex_app_server_count",
                    "node_repl_count",
                    "sky_computer_use_count",
                    "chrome_extension_host_count",
                    "codex_service_count",
                    "codex_renderer_count",
                ],
            )
        )
    else:
        lines.append("- processes unavailable")

    for record in report["code_sign_clone_status"]:
        lines.append(
            f"- code_sign_clone `{record['ts']}` "
            + compact_record(record, ["exists", "size_mb", "du_timeout", "path"])
        )
    if not report["code_sign_clone_status"]:
        lines.append("- code_sign_clone unavailable")
    for record in report["code_sign_clone_delta"]:
        lines.append(
            f"- code_sign_clone_delta `{record['ts']}` "
            + compact_record(record, ["size_mb", "previous_size_mb", "delta_mb", "growth_mb_per_minute"])
        )

    for record in report["trustd_resources"]:
        lines.append(
            f"- trustd `{record['ts']}` "
            + compact_record(record, ["pid", "cpu_percent", "rss_mb", "etime", "stat"])
        )
    if not report["trustd_resources"]:
        lines.append("- trustd resource samples unavailable")

    if report["codex_diagnostic_signals"]:
        lines.append("")
        lines.append("Recent Codex diagnostic signals:")
        for record in report["codex_diagnostic_signals"]:
            lines.append(
                f"- `{record['ts']}` `{record.get('severity', '')}` "
                + compact_record(record, ["signal", "value", "role", "pid", "detail"])
            )

    lines.extend(["", "## Passive Log Scans", ""])
    for record in report["passive_log_scans"]:
        lines.append(
            f"- `{record['ts']}` "
            + compact_record(record, ["matches", "raw_lines", "last_minutes", "duration_ms", "timeout"])
        )
    if not report["passive_log_scans"]:
        lines.append("No passive log scans.")

    lines.extend(["", "## brrr Notification History", ""])
    for record in report["brrr_events"]:
        lines.append(
            f"- `{record['ts']}` `{record['event']}` "
            + compact_record(
                record,
                [
                    "sent",
                    "reason",
                    "status",
                    "incident_kind",
                    "primary_signal",
                    "primary_value",
                    "last_sent_at",
                ],
            )
        )
    if not report["brrr_events"]:
        lines.append("No brrr events.")

    lines.extend(["", "## Latest CPU Top", ""])
    for record in report["latest_cpu_top"]:
        lines.append(
            f"- `{record['ts']}` "
            + compact_record(record, ["cpu_percent", "pid", "ppid", "rss_mb", "comm", "parent_comm"])
        )
    if not report["latest_cpu_top"]:
        lines.append("No CPU top samples.")

    lines.extend(["", "## Latest FD Top", ""])
    for record in report["latest_fd_top"]:
        lines.append(
            f"- `{record['ts']}` "
            + compact_record(record, ["count", "pid", "comm", "short_comm"])
        )
    if not report["latest_fd_top"]:
        lines.append("No FD top samples.")

    lines.extend(["", "## Findings", ""])
    lines.extend(report["findings"])
    lines.append("")
    return "\n".join(lines)


def incident_report(db_path: Path, hours: float, limit: int, output_format: str) -> int:
    cutoff = (
        dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    ).isoformat(timespec="seconds").replace("+00:00", "Z")
    conn = open_read_db(db_path)
    try:
        summary_row = conn.execute(
            """
            SELECT
              count(*) AS total,
              sum(status = 'unhealthy') AS unhealthy,
              sum(status = 'error') AS error
            FROM snapshots
            WHERE started_at >= ?
            """,
            (cutoff,),
        ).fetchone()
        signal_rows = conn.execute(
            """
            SELECT
              json_extract(data_json, '$.signal') AS signal,
              coalesce(severity, '') AS severity,
              count(*) AS count,
              min(ts) AS first_ts,
              max(ts) AS last_ts,
              max(cast(json_extract(data_json, '$.value') AS REAL)) AS max_value
            FROM events
            WHERE event = 'health_signal' AND ts >= ?
            GROUP BY signal, severity
            ORDER BY count DESC, last_ts DESC
            """,
            (cutoff,),
        ).fetchall()
        recent_snapshots = conn.execute(
            """
            SELECT id, started_at, ended_at, status, mode
            FROM snapshots
            WHERE started_at >= ?
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (cutoff, limit),
        ).fetchall()

        recent_health_signals = load_recent_events(
            conn, cutoff=cutoff, event="health_signal", limit=limit
        )
        process_resources = load_recent_events(
            conn, cutoff=cutoff, event="process_resource", limit=limit * 4
        )
        syspolicyd_resources = [
            record for record in process_resources if record.get("role") == "syspolicyd"
        ][:limit]
        trustd_resources = [
            record for record in process_resources if record.get("role") == "trustd"
        ][:limit]
        syspolicyd_deltas = load_recent_events(
            conn, cutoff=cutoff, event="process_resource_delta", limit=limit * 4
        )
        syspolicyd_deltas = [
            record for record in syspolicyd_deltas if record.get("role") == "syspolicyd"
        ][:limit]
        latest_codex_config_records = load_latest_events(
            conn, event="codex_config_snapshot", limit=1
        )
        latest_codex_process_summary_records = load_latest_events(
            conn, event="codex_process_summary", limit=1
        )
        code_sign_clone_status = load_recent_events(
            conn, cutoff=cutoff, event="code_sign_clone_status", limit=limit
        )
        code_sign_clone_delta = load_recent_events(
            conn, cutoff=cutoff, event="code_sign_clone_delta", limit=limit
        )
        passive_log_scans = load_recent_events(
            conn, cutoff=cutoff, event="macos_passive_log_scan", limit=limit
        )
        codex_diagnostic_signal_candidates = load_recent_events(
            conn, cutoff=cutoff, event="health_signal", limit=max(limit * 8, 80)
        )
        brrr_events = [
            *load_recent_events(conn, cutoff=cutoff, event="brrr_notification", limit=limit),
            *load_recent_events(conn, cutoff=cutoff, event="brrr_notification_skipped", limit=limit),
        ]
        brrr_events.sort(key=lambda item: item["ts"], reverse=True)
        brrr_events = brrr_events[:limit]
        latest_sample_limit = max(limit * 8, 100)
        latest_cpu_records = load_latest_events(conn, event="process_cpu_top", limit=latest_sample_limit)
        latest_cpu_snapshot = latest_snapshot_id_for_event(latest_cpu_records)
        latest_cpu_top = [
            record for record in latest_cpu_records if record["snapshot_id"] == latest_cpu_snapshot
        ][:limit]
        latest_cpu_top.sort(
            key=lambda item: parse_float(str(item.get("cpu_percent") or "")) or 0,
            reverse=True,
        )
        latest_fd_records = load_latest_events(conn, event="fd_top", limit=latest_sample_limit)
        latest_fd_snapshot = latest_snapshot_id_for_event(latest_fd_records)
        latest_fd_top = [
            record for record in latest_fd_records if record["snapshot_id"] == latest_fd_snapshot
        ][:limit]
        latest_fd_top.sort(
            key=lambda item: parse_int(str(item.get("count") or "")) or 0,
            reverse=True,
        )
    except sqlite3.Error as exc:
        conn.close()
        raise CliError("unable to build incident report") from exc
    conn.close()

    signal_counts = []
    for row in signal_rows:
        signal_counts.append(
            {
                "signal": row["signal"] or "",
                "severity": row["severity"] or "",
                "count": int(row["count"] or 0),
                "first_ts": row["first_ts"] or "",
                "last_ts": row["last_ts"] or "",
                "max_value": round(float(row["max_value"]), 1) if row["max_value"] is not None else "",
            }
        )

    snapshot_summary = {
        "total": int(summary_row["total"] or 0),
        "unhealthy": int(summary_row["unhealthy"] or 0),
        "error": int(summary_row["error"] or 0),
    }
    syspolicyd_assessment_failure_rows = [
        row for row in signal_counts if row["signal"] == "syspolicyd_assessment_failure"
    ]
    rss_error_rows = [
        row for row in signal_counts if row["signal"] == "process_rss_error"
    ]
    findings = [
        "- Treat `syspolicyd_assessment_failure` as the strongest sign that Gatekeeper/static-code checks are failing.",
        "- Treat `maxfiles_soft_low` as context, not proof of cause.",
        "- Keep `spctl` and `codesign` probes disabled during an active incident.",
    ]
    if syspolicyd_assessment_failure_rows:
        total_assessment_failures = sum(int(row["count"] or 0) for row in syspolicyd_assessment_failure_rows)
        max_assessment_failures = max(
            parse_float(str(row["max_value"] or "")) or 0 for row in syspolicyd_assessment_failure_rows
        )
        findings.append(
            f"- Window contains `{total_assessment_failures}` syspolicyd assessment failure signal(s); "
            f"max_value=`{round(max_assessment_failures, 1)}`."
        )
    if rss_error_rows:
        total_rss_error = sum(int(row["count"] or 0) for row in rss_error_rows)
        max_rss_error = max(
            parse_float(str(row["max_value"] or "")) or 0 for row in rss_error_rows
        )
        findings.append(
            f"- Window contains `{total_rss_error}` RSS error signal(s); max_value=`{round(max_rss_error, 1)}` MiB."
        )
    latest_codex_config = latest_codex_config_records[0] if latest_codex_config_records else {}
    latest_codex_process_summary = (
        latest_codex_process_summary_records[0] if latest_codex_process_summary_records else {}
    )
    codex_diagnostic_signal_prefixes = (
        "codex_",
        "code_sign_clone",
        "trustd_",
    )
    codex_diagnostic_signals = [
        record
        for record in codex_diagnostic_signal_candidates
        if str(record.get("signal") or "").startswith(codex_diagnostic_signal_prefixes)
        or str(record.get("role") or "").startswith("trustd")
    ][:limit]

    if latest_codex_process_summary:
        sky_count = parse_int(str(latest_codex_process_summary.get("sky_computer_use_count") or "0")) or 0
        chrome_host_count = parse_int(
            str(latest_codex_process_summary.get("chrome_extension_host_count") or "0")
        ) or 0
        node_repl_count = parse_int(str(latest_codex_process_summary.get("node_repl_count") or "0")) or 0
        if sky_count:
            findings.append(
                f"- Latest Codex process snapshot: SkyComputerUseClient count=`{sky_count}`."
            )
        if chrome_host_count:
            findings.append(
                f"- Latest Codex process snapshot: Chrome extension host count=`{chrome_host_count}`."
            )
        if node_repl_count:
            findings.append(
                f"- Latest Codex process snapshot: node_repl child count=`{node_repl_count}`."
            )
    if latest_codex_config:
        if latest_codex_config.get("plugin_computer_use_enabled") is False and latest_codex_config.get(
            "notify_uses_sky_computer_use"
        ):
            findings.append(
                "- Codex config disables the bundled computer-use plugin, but notify still points to SkyComputerUseClient."
            )
        if latest_codex_config.get("plugin_chrome_enabled") is False and latest_codex_config.get(
            "chrome_native_extension_id_present"
        ):
            findings.append(
                "- Codex config disables the bundled chrome plugin, but the Chrome native-host registry still references the Codex extension."
            )
    if code_sign_clone_status:
        largest_clone = max(
            code_sign_clone_status,
            key=lambda item: parse_float(str(item.get("size_mb") or "")) or 0,
        )
        size = largest_clone.get("size_mb")
        if size not in (None, ""):
            findings.append(f"- Latest code_sign_clone size is `{size}` MiB.")

    report = {
        "generated_at": utc_now(),
        "db": str(db_path),
        "window_hours": hours,
        "snapshot_summary": snapshot_summary,
        "recent_snapshots": [
            {
                "id": row["id"],
                "started_at": row["started_at"],
                "ended_at": row["ended_at"] or "",
                "status": row["status"] or "",
                "mode": row["mode"],
            }
            for row in recent_snapshots
        ],
        "signal_counts": signal_counts,
        "recent_health_signals": recent_health_signals,
        "syspolicyd_resources": syspolicyd_resources,
        "syspolicyd_deltas": syspolicyd_deltas,
        "latest_codex_config": latest_codex_config,
        "latest_codex_process_summary": latest_codex_process_summary,
        "code_sign_clone_status": code_sign_clone_status,
        "code_sign_clone_delta": code_sign_clone_delta,
        "trustd_resources": trustd_resources,
        "codex_diagnostic_signals": codex_diagnostic_signals,
        "passive_log_scans": passive_log_scans,
        "brrr_events": brrr_events,
        "latest_cpu_top": latest_cpu_top,
        "latest_fd_top": latest_fd_top,
        "findings": findings,
    }

    if output_format == "json":
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(render_incident_markdown(report))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="macos-session-health",
        description="Monitor macOS user-session spawn, FD, and app-launch health.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  macos-session-health query --signals --limit 20
  macos-session-health query --format json --event health_signal --limit 5
  macos-session-health trend --hours 6 --event fd_top --limit 20
  macos-session-health incident --hours 6 --format markdown
  macos-session-health recover
  macos-session-health events --format json

See modules/bin/macos-session-health.md for the syspolicyd incident runbook.
""",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"SQLite path. Default: {DEFAULT_DB}")
    parser.add_argument("--no-db", action="store_true", help="Only emit stdout; do not write SQLite.")
    parser.add_argument("--quiet", action="store_true", help="Write SQLite without stdout logfmt output.")
    parser.add_argument("--top", type=int, default=int(os.getenv("MACOS_SESSION_HEALTH_TOP", "25")))
    parser.add_argument("--fd-warn", type=int, default=int(os.getenv("MACOS_SESSION_HEALTH_FD_WARN", "1024")))
    parser.add_argument(
        "--codex-app",
        type=Path,
        default=Path(os.getenv("MACOS_SESSION_HEALTH_CODEX_APP", str(CODEX_APP))),
        help="Codex Desktop app bundle path used for Codex diagnostics.",
    )
    parser.add_argument(
        "--codex-config",
        type=Path,
        default=Path(os.getenv("MACOS_SESSION_HEALTH_CODEX_CONFIG", str(CODEX_CONFIG))),
        help="Codex config.toml path used for non-secret Codex diagnostics.",
    )
    parser.add_argument(
        "--codex-chrome-native-hosts",
        type=Path,
        default=Path(
            os.getenv(
                "MACOS_SESSION_HEALTH_CODEX_CHROME_NATIVE_HOSTS",
                str(CODEX_CHROME_NATIVE_HOSTS),
            )
        ),
        help="Codex Chrome native-host registry path.",
    )
    parser.add_argument(
        "--codex-node-repl-warn",
        type=int,
        default=int(os.getenv("MACOS_SESSION_HEALTH_CODEX_NODE_REPL_WARN", "20")),
        help="Warn when Codex app-server has at least this many node_repl children.",
    )
    parser.add_argument(
        "--syspolicyd-fd-warn",
        type=int,
        default=int(os.getenv("MACOS_SESSION_HEALTH_SYSPOLICYD_FD_WARN", "2048")),
        help="Warn when visible syspolicyd FD count reaches this value.",
    )
    parser.add_argument(
        "--syspolicyd-path-warn",
        type=int,
        default=int(os.getenv("MACOS_SESSION_HEALTH_SYSPOLICYD_PATH_WARN", "512")),
        help="Warn when syspolicyd has this many visible FDs to one path.",
    )
    parser.add_argument(
        "--syspolicyd-cpu-warn",
        type=float,
        default=float(os.getenv("MACOS_SESSION_HEALTH_SYSPOLICYD_CPU_WARN", "80")),
        help="Warn when syspolicyd CPU percent reaches this value in ps output.",
    )
    parser.add_argument(
        "--syspolicyd-rss-warn-mb",
        type=float,
        default=float(os.getenv("MACOS_SESSION_HEALTH_SYSPOLICYD_RSS_WARN_MB", "1536")),
        help="Warn when syspolicyd RSS reaches this many MiB.",
    )
    parser.add_argument(
        "--syspolicyd-rss-error-mb",
        type=float,
        default=float(os.getenv("MACOS_SESSION_HEALTH_SYSPOLICYD_RSS_ERROR_MB", "2048")),
        help="Error when syspolicyd RSS reaches this many MiB.",
    )
    parser.add_argument(
        "--syspolicyd-rss-growth-warn-mb-per-minute",
        type=float,
        default=float(os.getenv("MACOS_SESSION_HEALTH_SYSPOLICYD_RSS_GROWTH_WARN_MB_PER_MINUTE", "128")),
        help="Warn when syspolicyd RSS grows this many MiB per minute between snapshots.",
    )
    parser.add_argument(
        "--syspolicyd-log-error-count",
        type=int,
        default=int(os.getenv("MACOS_SESSION_HEALTH_SYSPOLICYD_LOG_ERROR_COUNT", "100")),
        help="Treat syspolicyd assessment-failure log scans below this match count as warning-only.",
    )
    parser.add_argument(
        "--trustd-cpu-warn",
        type=float,
        default=float(os.getenv("MACOS_SESSION_HEALTH_TRUSTD_CPU_WARN", "80")),
        help="Warn when any trustd CPU percent reaches this value in ps output.",
    )
    parser.add_argument(
        "--trustd-rss-warn-mb",
        type=float,
        default=float(os.getenv("MACOS_SESSION_HEALTH_TRUSTD_RSS_WARN_MB", "1024")),
        help="Warn when any trustd RSS reaches this many MiB.",
    )
    parser.add_argument(
        "--trustd-rss-error-mb",
        type=float,
        default=float(os.getenv("MACOS_SESSION_HEALTH_TRUSTD_RSS_ERROR_MB", "2048")),
        help="Error when the largest trustd RSS reaches this many MiB.",
    )
    parser.add_argument(
        "--trustd-rss-growth-warn-mb-per-minute",
        type=float,
        default=float(os.getenv("MACOS_SESSION_HEALTH_TRUSTD_RSS_GROWTH_WARN_MB_PER_MINUTE", "128")),
        help="Warn when the largest trustd RSS grows this many MiB per minute.",
    )
    parser.add_argument(
        "--code-sign-clone-warn-mb",
        type=float,
        default=float(os.getenv("MACOS_SESSION_HEALTH_CODE_SIGN_CLONE_WARN_MB", "1024")),
        help="Warn when Codex code_sign_clone reaches this many MiB.",
    )
    parser.add_argument(
        "--code-sign-clone-growth-warn-mb-per-minute",
        type=float,
        default=float(os.getenv("MACOS_SESSION_HEALTH_CODE_SIGN_CLONE_GROWTH_WARN_MB_PER_MINUTE", "512")),
        help="Warn when Codex code_sign_clone grows this many MiB per minute.",
    )
    parser.add_argument(
        "--code-sign-clone-timeout",
        type=float,
        default=float(os.getenv("MACOS_SESSION_HEALTH_CODE_SIGN_CLONE_TIMEOUT", "3")),
        help="Timeout for measuring Codex code_sign_clone size with du.",
    )
    parser.add_argument("--app", action="append", default=[], help="App bundle to include in bundle and optional signing probes. Repeatable.")
    parser.add_argument("--command-timeout", type=float, default=5)
    parser.add_argument("--lsof-timeout", type=float, default=float(os.getenv("MACOS_SESSION_HEALTH_LSOF_TIMEOUT", "8")))
    parser.add_argument(
        "--app-assess-timeout",
        type=float,
        default=float(os.getenv("MACOS_SESSION_HEALTH_APP_ASSESS_TIMEOUT", "8")),
    )
    parser.add_argument(
        "--spawn-check-timeout",
        dest="spawn_check_timeout",
        type=float,
        default=5,
        help="Timeout in seconds for each spawn check command.",
    )
    parser.add_argument(
        "--spctl-interval-minutes",
        type=int,
        default=int(os.getenv("MACOS_SESSION_HEALTH_SPCTL_INTERVAL_MINUTES", "0")),
        help="Run spctl app assessment at most this often. Set 0 to disable.",
    )
    parser.add_argument(
        "--codesign-interval-minutes",
        type=int,
        default=int(os.getenv("MACOS_SESSION_HEALTH_CODESIGN_INTERVAL_MINUTES", "0")),
        help="Run codesign app verification at most this often. Set 0 to disable.",
    )
    parser.add_argument("--collect-log-excerpt", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--log-timeout", type=float, default=6)
    parser.add_argument("--log-lines", type=int, default=80)
    parser.add_argument(
        "--passive-log-interval-minutes",
        type=int,
        default=int(os.getenv("MACOS_SESSION_HEALTH_PASSIVE_LOG_INTERVAL_MINUTES", "5")),
        help="Run targeted passive unified-log scan at most this often. Set 0 to disable.",
    )
    parser.add_argument(
        "--passive-log-last-minutes",
        type=int,
        default=int(os.getenv("MACOS_SESSION_HEALTH_PASSIVE_LOG_LAST_MINUTES", "6")),
        help="Look back this many minutes during each targeted passive unified-log scan.",
    )
    parser.add_argument(
        "--passive-log-lines",
        type=int,
        default=int(os.getenv("MACOS_SESSION_HEALTH_PASSIVE_LOG_LINES", "80")),
        help="Store at most this many matched passive unified-log lines per scan.",
    )
    parser.add_argument(
        "--log-excerpt-cooldown-minutes",
        type=int,
        default=int(os.getenv("MACOS_SESSION_HEALTH_LOG_COOLDOWN_MINUTES", "30")),
        help="When unhealthy signals repeat, collect macOS log excerpts at most this often.",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=int(os.getenv("MACOS_SESSION_HEALTH_RETENTION_DAYS", "14")),
        help="Delete snapshots older than this many days. Set 0 to disable.",
    )
    parser.add_argument(
        "--brrr-helper",
        type=Path,
        default=os.getenv("MACOS_SESSION_HEALTH_BRRR_HELPER"),
        help="Optional brrr sender helper path. Sends notifications only for matching incident signals.",
    )
    parser.add_argument(
        "--brrr-notify-cooldown-minutes",
        type=int,
        default=int(os.getenv("MACOS_SESSION_HEALTH_BRRR_COOLDOWN_MINUTES", "120")),
        help="Suppress all later brrr notifications for this many minutes after one notification is sent.",
    )
    parser.add_argument(
        "--brrr-thread-id",
        default=os.getenv("MACOS_SESSION_HEALTH_BRRR_THREAD_ID", "macos-session-health"),
        help="brrr thread_id for grouped notifications.",
    )
    parser.add_argument(
        "--brrr-interruption-level",
        choices=["passive", "active", "time-sensitive", "critical"],
        default=os.getenv("MACOS_SESSION_HEALTH_BRRR_INTERRUPTION_LEVEL", "passive"),
        help="brrr interruption level for health notifications.",
    )
    parser.add_argument(
        "--brrr-open-url",
        default=os.getenv("MACOS_SESSION_HEALTH_BRRR_OPEN_URL", ""),
        help="Optional brrr open_url.",
    )
    parser.add_argument(
        "--brrr-timeout",
        type=float,
        default=float(os.getenv("MACOS_SESSION_HEALTH_BRRR_TIMEOUT", "10")),
        help="Timeout in seconds for the brrr helper.",
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser(
        "snapshot",
        help="Collect one snapshot.",
        description="Collect one snapshot. Global options before the subcommand control collection behavior.",
    )

    watch = subparsers.add_parser("watch", help="Collect snapshots forever.")
    watch.add_argument("--interval", type=float, default=float(os.getenv("MACOS_SESSION_HEALTH_INTERVAL", "60")))

    query_parser = subparsers.add_parser("query", help="Print recent SQLite events.")
    query_parser.add_argument("--limit", type=int, default=50)
    query_parser.add_argument("--event", help="Event name to filter. Use `events` to list known names.")
    query_parser.add_argument("--signals", action="store_true")
    query_parser.add_argument("--format", choices=["logfmt", "json"], default="logfmt")

    events_parser = subparsers.add_parser("events", help="List event names present in SQLite.")
    events_parser.add_argument("--format", choices=["logfmt", "json"], default="logfmt")

    trend_parser = subparsers.add_parser("trend", help="Show growth trends from recent SQLite samples.")
    trend_parser.add_argument("--hours", type=float, default=6)
    trend_parser.add_argument("--limit", type=int, default=20)
    trend_parser.add_argument(
        "--event",
        choices=[
            "fd_top",
            "process_lsof_summary",
            "process_lsof_path_count",
            "command_process_count",
            "parent_process_count",
            "user_process_count",
        ],
        default="fd_top",
    )
    trend_parser.add_argument("--format", choices=["logfmt", "json"], default="logfmt")

    incident_parser = subparsers.add_parser(
        "incident",
        help="Print a recent incident report from SQLite diagnostics.",
    )
    incident_parser.add_argument("--hours", type=float, default=6)
    incident_parser.add_argument("--limit", type=int, default=20)
    incident_parser.add_argument("--format", choices=["markdown", "json"], default="markdown")

    recover_parser = subparsers.add_parser(
        "recover",
        help="Print or execute the guarded syspolicyd recovery plan.",
    )
    recover_parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    recover_parser.add_argument(
        "--execute",
        action="store_true",
        help="Restart syspolicyd with sudo kill. Refuses to run without --assume-codex-desktop-closed.",
    )
    recover_parser.add_argument(
        "--assume-codex-desktop-closed",
        action="store_true",
        help="Confirm Codex Desktop is closed or safe to leave closed during recovery.",
    )
    recover_parser.add_argument(
        "--signal",
        choices=["TERM", "KILL"],
        default="TERM",
        help="Signal used with sudo kill when --execute is set.",
    )
    recover_parser.add_argument(
        "--wait-seconds",
        type=float,
        default=5,
        help="Seconds to wait after signaling syspolicyd before reading the new status.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.command = args.command or "snapshot"
    if not args.app:
        args.app = [DEFAULT_APP]

    if args.command == "query":
        if args.no_db:
            parser.error("query requires SQLite; remove --no-db")
        try:
            return query(args.db, args.limit, args.event, args.signals, args.format)
        except CliError as exc:
            print_error(str(exc), db=args.db)
            return 1

    if args.command == "events":
        if args.no_db:
            parser.error("events requires SQLite; remove --no-db")
        try:
            return events(args.db, args.format)
        except CliError as exc:
            print_error(str(exc), db=args.db)
            return 1

    if args.command == "trend":
        if args.no_db:
            parser.error("trend requires SQLite; remove --no-db")
        try:
            return trend(args.db, args.hours, args.limit, args.event, args.format)
        except CliError as exc:
            print_error(str(exc), db=args.db)
            return 1

    if args.command == "incident":
        if args.no_db:
            parser.error("incident requires SQLite; remove --no-db")
        try:
            return incident_report(args.db, args.hours, args.limit, args.format)
        except CliError as exc:
            print_error(str(exc), db=args.db)
            return 1

    if args.command == "recover":
        return recover_syspolicyd(args)

    store = Store(None if args.no_db else args.db, emit_stdout=not args.quiet)
    try:
        if args.command == "snapshot":
            status = snapshot(args, store, "snapshot")
            return 0 if status == "ok" else 1
        if args.command == "watch":
            while True:
                snapshot(args, store, "watch")
                time.sleep(args.interval)
        parser.error(f"unknown command: {args.command}")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
