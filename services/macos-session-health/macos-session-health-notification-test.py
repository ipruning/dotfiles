#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import os
import runpy
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

MODULE_PATH = Path(__file__).with_name("macos-session-health")


class ReadOnlyReportsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = runpy.run_path(str(MODULE_PATH))
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def cli(self, db: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(MODULE_PATH), "--db", str(db), *args],
            cwd=self.root,
            env={**os.environ, "HOME": str(self.root)},
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )

    def test_missing_database_is_not_created_by_reports(self) -> None:
        for command in ("query", "events", "incident"):
            with self.subTest(command=command):
                db = self.root / f"missing {command} #?.sqlite3"
                result = self.cli(db, command, "--format", "json")
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("unable to open database", result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertFalse(db.exists())

    def test_existing_reports_support_encoded_and_relative_paths(self) -> None:
        db = self.root / "reports with spaces #?" / "health #?.sqlite3"
        store = self.module["Store"](db, emit_stdout=False)
        try:
            for rss in (40.0, 1800.0):
                snapshot_id = store.create_snapshot("test")
                store.emit(snapshot_id, "syspolicyd_resource", pid="503", rss_mb=rss)
                store.emit(
                    snapshot_id,
                    "spawn_check",
                    name="true",
                    exit=1,
                    timeout=False,
                    stderr="fork failed",
                )
                store.emit(
                    snapshot_id,
                    "syspolicyd_log_match",
                    category="fd_exhausted",
                    line="syspolicyd[503:1] Too many open files",
                )
                store.emit(
                    snapshot_id,
                    "condition",
                    condition="spawn_failed",
                    state="bad",
                    value=1,
                    detail="启动检查失败：true 退出码 1",
                )
                store.emit(
                    snapshot_id,
                    "evidence_fd_top",
                    rows=[{"pid": "42", "comm": "sample", "count": 900}],
                )
                store.finish_snapshot(snapshot_id, "unhealthy")
        finally:
            store.close()
        before = db.read_bytes()
        for path in (db, db.relative_to(self.root)):
            with self.subTest(path=path):
                result = self.cli(
                    path, "query", "--event", "syspolicyd_resource", "--format", "json"
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    [row["rss_mb"] for row in json.loads(result.stdout)],
                    [1800.0, 40.0],
                )

                result = self.cli(path, "events", "--format", "json")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    {row["event"] for row in json.loads(result.stdout)},
                    {
                        "condition",
                        "evidence_fd_top",
                        "spawn_check",
                        "syspolicyd_log_match",
                        "syspolicyd_resource",
                    },
                )

                result = self.cli(path, "incident", "--format", "json")
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                summary = report["snapshot_summary"]
                self.assertEqual(
                    [summary[key] for key in ("total", "unhealthy", "error")],
                    [2, 2, 0],
                )
                conditions = {row["condition"]: row for row in report["conditions"]}
                self.assertEqual(conditions["spawn_failed"]["bad_samples"], 2)
                self.assertEqual(conditions["file_table_high"]["bad_samples"], 0)
                self.assertEqual(
                    report["failed_spawn_checks"][0]["stderr"], "fork failed"
                )
                self.assertEqual(
                    report["syspolicyd_log_matches"][0]["category"], "fd_exhausted"
                )
                self.assertEqual(report["latest_evidence"]["fd_top"][0]["count"], 900)

                markdown = self.cli(path, "incident", "--format", "markdown")
                self.assertEqual(markdown.returncode, 0, markdown.stderr)
                self.assertIn("Too many open files", markdown.stdout)
                self.assertIn("fork failed", markdown.stdout)
        self.assertEqual(db.read_bytes(), before)

    def test_read_connection_rejects_writes(self) -> None:
        db = self.root / "read only #?.sqlite3"
        with closing(sqlite3.connect(db)) as conn:
            conn.execute("CREATE TABLE sample (value INTEGER)")
        conn = self.module["open_read_db"](db)
        try:
            with self.assertRaisesRegex(sqlite3.OperationalError, "readonly"):
                conn.execute("INSERT INTO sample VALUES (1)")
        finally:
            conn.close()


class AlertLifecycleTest(unittest.TestCase):
    """The notification contract: only persistent symptoms reach the phone."""

    def setUp(self) -> None:
        self.module = runpy.run_path(str(MODULE_PATH))
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = self.module["Store"](
            Path(self.temp_dir.name) / "health.sqlite3", emit_stdout=False
        )
        self.args = SimpleNamespace(
            brrr_retry_minutes=10,
            brrr_thread_id="macos-session-health",
            brrr_interruption_level="active",
            brrr_open_url="",
            brrr_timeout=2,
        )
        self.payloads: list[dict[str, Any]] = []
        self.delivery_ok = True

        def deliver(payload: dict[str, Any], _timeout: float) -> dict[str, Any]:
            self.payloads.append(payload)
            return {
                "exit": 0 if self.delivery_ok else 1,
                "timeout": False,
                "duration_ms": 1,
                "auth_mode": "bearer",
                "credential_source": "test",
                "endpoint": "https://example.test/send",
                "http_status": 202 if self.delivery_ok else 503,
                "error": "" if self.delivery_ok else "HTTP 503",
            }

        self.module["update_alerts"].__globals__["deliver_brrr"] = deliver

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def observe(self, *states: str, condition: str = "spawn_failed") -> None:
        observation = self.module["observation"]
        for state in states:
            snapshot_id = self.store.create_snapshot("test")
            self.module["update_alerts"](
                self.store,
                snapshot_id,
                {condition: observation(state, 1, f"{condition} detail")},
                self.args,
            )

    def alert(self, condition: str = "spawn_failed") -> dict[str, Any]:
        return self.module["load_alert"](self.store, condition)

    def test_single_bad_sample_does_not_notify(self) -> None:
        self.observe("bad", "ok")
        self.assertEqual(self.payloads, [])

    def test_flapping_condition_never_notifies(self) -> None:
        # The old design re-armed on every clean recheck, so a probe hovering
        # around its threshold pushed again on each bad sample.
        self.observe(*["bad", "ok"] * 10)
        self.assertEqual(self.payloads, [])
        self.assertEqual(self.alert()["status"], "ok")

    def test_sustained_condition_notifies_once_then_recovers_once(self) -> None:
        self.observe("bad", "bad")
        self.assertEqual(len(self.payloads), 1)
        self.assertIn("macOS 无法正常启动进程", self.payloads[0]["title"])
        self.assertEqual(self.payloads[0]["interruption_level"], "active")
        self.assertIn("incident --hours 1", self.payloads[0]["message"])

        self.observe("bad", "bad", "bad", "unknown", "unknown", "ok", "ok")
        self.assertEqual(len(self.payloads), 1)
        self.assertEqual(self.alert()["status"], "firing")

        self.observe("ok")
        self.assertEqual(len(self.payloads), 2)
        self.assertIn("已恢复", self.payloads[1]["title"])
        self.assertEqual(self.payloads[1]["interruption_level"], "passive")
        self.assertEqual(self.alert()["status"], "ok")

    def test_unknown_observation_neither_advances_nor_resets(self) -> None:
        self.observe("bad", "unknown", "unknown")
        self.assertEqual(self.payloads, [])
        self.observe("bad")
        self.assertEqual(len(self.payloads), 1)

    def test_each_condition_uses_its_own_threshold(self) -> None:
        self.observe("bad", "bad", condition="syspolicyd_rss_high")
        self.assertEqual(self.payloads, [])
        self.observe("bad", condition="syspolicyd_rss_high")
        self.assertEqual(len(self.payloads), 1)
        self.assertEqual(self.alert("syspolicyd_rss_high")["status"], "firing")
        self.assertEqual(self.alert()["status"], "ok")

    def test_failed_delivery_retries_on_interval_and_recovery_stays_silent(
        self,
    ) -> None:
        self.delivery_ok = False
        self.observe("bad", "bad", "bad")
        self.assertEqual(len(self.payloads), 1)

        alert = self.alert()
        stale = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=11)
        alert["last_attempt_at"] = stale.isoformat().replace("+00:00", "Z")
        self.store.set_state("alert:spawn_failed", json.dumps(alert))
        self.delivery_ok = True
        self.observe("bad")
        self.assertEqual(len(self.payloads), 2)
        self.assertTrue(self.alert()["notified"])

    def test_recovery_after_undelivered_alert_sends_nothing(self) -> None:
        self.delivery_ok = False
        self.observe("bad", "bad", "ok", "ok", "ok")
        self.assertEqual(len(self.payloads), 1)
        self.assertEqual(self.alert()["status"], "ok")

    def test_collector_crashes_notify_after_three_consecutive_snapshots(
        self,
    ) -> None:
        snapshot = self.module["snapshot"]
        args = SimpleNamespace(**vars(self.args), retention_days=0)

        def crash(*_args: Any) -> Any:
            raise RuntimeError("probe exploded")

        with mock.patch.dict(snapshot.__globals__, {"collect_observations": crash}):
            for _ in range(3):
                with self.assertRaisesRegex(RuntimeError, "probe exploded"):
                    snapshot(args, self.store, "test")
        self.assertEqual(len(self.payloads), 1)
        self.assertIn("采集器连续崩溃", self.payloads[0]["title"])
        self.assertIn("probe exploded", self.payloads[0]["message"])
        statuses = self.store.conn.execute(
            "SELECT status FROM snapshots ORDER BY started_at"
        ).fetchall()
        self.assertEqual([row[0] for row in statuses], ["error"] * 3)


class ProbeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = runpy.run_path(str(MODULE_PATH))
        self.store = self.module["Store"](None, emit_stdout=False)
        self.sid = self.store.create_snapshot("test")

    def run_with(self, function: str, result: tuple[Any, ...], **kwargs: Any) -> Any:
        probe = self.module[function]
        with mock.patch.dict(
            probe.__globals__, {"run_command": lambda *_a, **_kw: result}
        ):
            return probe(self.store, self.sid, **kwargs)

    def test_spawn_timeout_is_bad(self) -> None:
        observed = self.run_with("probe_spawn", (124, "", "", True, 5000.0), timeout=5)
        self.assertEqual(observed["state"], "bad")
        self.assertIn("超时", observed["detail"])

    def test_process_and_file_tables_compare_against_kernel_limits(self) -> None:
        user = self.module["getpass"].getuser()
        limits = {
            "kern.maxproc": 100,
            "kern.maxprocperuid": 50,
            "kern.num_files": 79,
            "kern.maxfiles": 100,
        }
        rows = [{"user": user}] * 43 + [{"user": "root"}] * 10
        probe_process_table = self.module["probe_process_table"]
        self.assertEqual(probe_process_table(rows, limits, 85)["state"], "bad")
        self.assertEqual(probe_process_table(rows[:40], limits, 85)["state"], "ok")
        self.assertEqual(probe_process_table(None, limits, 85)["state"], "unknown")
        probe_file_table = self.module["probe_file_table"]
        self.assertEqual(probe_file_table(limits, 80)["state"], "ok")
        self.assertEqual(
            probe_file_table({**limits, "kern.num_files": 80}, 80)["state"], "bad"
        )

    def test_syspolicyd_rss_uses_the_largest_instance(self) -> None:
        probe = self.module["probe_syspolicyd_rss"]
        rows = [
            {
                "comm": "/usr/libexec/syspolicyd",
                "pid": "503",
                "stat": "Ss",
                "cpu_percent": 0.0,
                "rss_mb": 2000.0,
                "etime": "1",
            },
            {
                "comm": "/usr/bin/other",
                "pid": "9",
                "stat": "S",
                "cpu_percent": 0.0,
                "rss_mb": 9000.0,
                "etime": "1",
            },
        ]
        self.assertEqual(probe(self.store, self.sid, rows, 1536)["state"], "bad")
        self.assertEqual(
            probe(self.store, self.sid, rows[1:], 1536)["state"], "unknown"
        )

    def scan(self, output: str, *, timed_out: bool = False) -> dict[str, Any]:
        return self.run_with(
            "probe_syspolicyd_log",
            (124 if timed_out else 0, output, "", timed_out, 1.0),
            timeout=30,
            last_minutes=5,
            assessment_failure_limit=100,
            max_lines=5,
        )

    def test_syspolicyd_log_alerts_on_fd_exhaustion_not_routine_failures(
        self,
    ) -> None:
        routine = (
            "2026-10-11 E syspolicyd[503:1] Failed to generate SecStaticCode"
            " for <private> error: -67068\n"
        ) * 15
        self.assertEqual(self.scan(routine)["state"], "ok")
        self.assertEqual(self.scan(routine * 7)["state"], "bad")
        exhausted = "2026-10-11 E syspolicyd[503:1] UNIX error exception: 24\n"
        self.assertEqual(self.scan(exhausted)["state"], "bad")
        self.assertEqual(self.scan(exhausted, timed_out=True)["state"], "unknown")


class DeliveryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = runpy.run_path(str(MODULE_PATH))
        self.deliver = self.module["deliver_brrr"]
        self.globals = self.deliver.__globals__
        self.globals["brrr_configuration"] = lambda: {
            "configured": True,
            "auth_mode": "bearer",
            "endpoint": "https://example.test/send",
            "credential_source": "test",
            "secret": "secret",
        }

    def test_delivery_attempts_http_once(self) -> None:
        calls = 0

        def urlopen(*_args: Any, **_kwargs: Any) -> Any:
            nonlocal calls
            calls += 1
            raise urllib.error.URLError("offline")

        self.globals["urllib"].request.urlopen = urlopen
        result = self.deliver({"title": "t", "message": "m"}, 1)
        self.assertEqual(calls, 1)
        self.assertEqual(result["endpoint"], "https://example.test/send")
        self.assertEqual(result["auth_mode"], "bearer")
        self.assertEqual(result["error"], "offline")
        self.assertNotIn("attempts", result)

    def test_dry_run_does_not_send(self) -> None:
        with mock.patch.object(self.globals["urllib"].request, "urlopen") as urlopen:
            result = self.deliver({"title": "t"}, 1, dry_run=True)
        urlopen.assert_not_called()
        self.assertEqual(result["exit"], 0)
        self.assertEqual(result["payload"], {"title": "t"})


class LifecyclePartialProgressTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = runpy.run_path(str(MODULE_PATH))
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.runtime = root / "runtime"
        self.wrapper = root / "bin/macos-session-health"
        self.plist = root / "LaunchAgents/com.ipruning.macos-session-health.plist"
        self.wrapper.parent.mkdir(parents=True)
        self.plist.parent.mkdir(parents=True)
        self.marker = self.module["WRAPPER_MARKER"]
        self.wrapper.write_text(f"#!/bin/sh\n{self.marker}\nexit 0\n")
        self.runtime.write_text("old runtime\n")
        self.plist.write_text("old plist\n")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def lifecycle_globals(self) -> dict[str, Any]:
        return {
            "RUNTIME_CLI": self.runtime,
            "USER_BIN": self.wrapper,
            "LAUNCH_AGENT": self.plist,
            "DEFAULT_DB": Path(self.temp_dir.name) / "state/health.sqlite3",
            "LOG_DIR": Path(self.temp_dir.name) / "logs",
            "runtime_python": lambda: Path("/usr/bin/python3"),
            "launchd_job": mock.Mock(
                return_value=subprocess.CompletedProcess(["launchctl"], 1, "", "")
            ),
            "bootout_launch_agent": mock.Mock(),
        }

    def test_failed_install_stays_unloaded_and_rerun_converges(self) -> None:
        install = self.module["install_launch_agent"]
        globals_ = install.__globals__
        lifecycle = self.lifecycle_globals()
        lifecycle["bootstrap_launch_agent"] = mock.Mock(
            side_effect=self.module["CliError"]("boom")
        )
        with (
            mock.patch.object(globals_["sys"], "platform", "darwin"),
            mock.patch.dict(globals_, lifecycle),
        ):
            with self.assertRaisesRegex(
                self.module["CliError"],
                "LaunchAgent state=unloaded.*inspect with.*then rerun install",
            ):
                install()
            globals_["bootstrap_launch_agent"] = mock.Mock()
            self.assertEqual(install(), 0)
            globals_["bootstrap_launch_agent"].assert_called_once()

    def test_failed_uninstall_keeps_progress_and_rerun_converges(self) -> None:
        uninstall = self.module["uninstall_launch_agent"]
        globals_ = uninstall.__globals__
        lifecycle = self.lifecycle_globals()
        original_unlink = Path.unlink
        failed = False

        def fail_once(path: Path, *args: Any, **kwargs: Any) -> None:
            nonlocal failed
            if path == self.wrapper and not failed:
                failed = True
                raise OSError("injected")
            original_unlink(path, *args, **kwargs)

        with (
            mock.patch.object(globals_["sys"], "platform", "darwin"),
            mock.patch.dict(globals_, lifecycle),
            mock.patch.object(Path, "unlink", fail_once),
        ):
            with self.assertRaisesRegex(
                self.module["CliError"], "removed=plist.*rerun uninstall"
            ):
                uninstall()
            self.assertFalse(self.plist.exists())
            self.assertEqual(uninstall(), 0)
        self.assertFalse(self.wrapper.exists())
        self.assertFalse(self.runtime.exists())


if __name__ == "__main__":
    unittest.main()
