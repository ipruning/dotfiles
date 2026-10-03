#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
        for command in ("query", "events", "trend", "incident"):
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
            for count in (3, 8):
                snapshot_id = store.create_snapshot("test", [])
                store.emit(snapshot_id, "fd_top", pid=42, comm="sample", count=count)
                store.emit(
                    snapshot_id,
                    "health_signal",
                    "warning",
                    signal="test_signal",
                    value=count,
                )
                store.finish_snapshot(snapshot_id, "unhealthy")
        finally:
            store.close()
        before = db.read_bytes()
        for path in (db, db.relative_to(self.root)):
            with self.subTest(path=path):
                result = self.cli(path, "query", "--event", "fd_top", "--format", "json")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual([row["count"] for row in json.loads(result.stdout)], [8, 3])

                result = self.cli(path, "events", "--format", "json")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    {row["event"] for row in json.loads(result.stdout)},
                    {"fd_top", "health_signal"},
                )

                result = self.cli(path, "trend", "--format", "json")
                self.assertEqual(result.returncode, 0, result.stderr)
                rows = json.loads(result.stdout)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["identity"], "pid=42 comm=sample")
                self.assertEqual(
                    [rows[0][key] for key in ("first", "last", "delta", "samples")],
                    [3, 8, 5, 2],
                )

                result = self.cli(path, "incident", "--format", "json")
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(
                    report["snapshot_summary"], {"total": 2, "unhealthy": 2, "error": 0}
                )
                self.assertEqual(report["signal_counts"][0]["signal"], "test_signal")
                self.assertEqual(report["signal_counts"][0]["count"], 2)
                self.assertEqual(report["latest_fd_top"][0]["count"], 8)
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

    def test_empty_app_is_rejected_before_collection_state(self) -> None:
        for command in ("snapshot", "watch"):
            for value in ("", "   "):
                with self.subTest(command=command, value=value):
                    db = self.root / "must not exist" / "health.sqlite3"
                    result = self.cli(
                        db, "--app", "/Applications/ChatGPT.app", "--app", value, command
                    )
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("--app requires a non-empty", result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertFalse(db.parent.exists())

    def test_default_and_explicit_apps_reach_bundle_collector(self) -> None:
        # Isolate unrelated host probes and notifications, not argument handling,
        # Store, or the app-bundle collector being tested.
        main = self.module["main"]
        globals_ = main.__globals__
        expected_defaults = ["/Applications/ChatGPT.app"]
        for explicit in ([], [str(self.root / "Missing app.app")]):
            with self.subTest(explicit=explicit):
                db = self.root / "apps.sqlite3"
                collected: list[str] = []

                def bundle_snapshot(args: argparse.Namespace, store: Any, mode: str) -> str:
                    collected.extend(args.app)
                    snapshot_id = store.create_snapshot(mode, args.app)
                    self.module["collect_app_assess"](
                        store, snapshot_id, args.app, 1, run_codesign=False, run_spctl=False
                    )
                    store.finish_snapshot(snapshot_id, "ok")
                    return "ok"

                argv = [str(MODULE_PATH), "--db", str(db), "--quiet"]
                for app in explicit:
                    argv.extend(["--app", app])
                with (
                    mock.patch.object(sys, "argv", argv + ["snapshot"]),
                    mock.patch.dict(globals_, {"snapshot": bundle_snapshot}),
                ):
                    self.assertEqual(main(), 0)
                self.assertEqual(collected, explicit or expected_defaults)
                with closing(sqlite3.connect(db)) as conn:
                    bundles = [
                        json.loads(row[0])["app"]
                        for row in conn.execute(
                            "SELECT data_json FROM events WHERE event = 'app_bundle'"
                        )
                    ]
                self.assertEqual(bundles, explicit or expected_defaults)
                self.assertNotIn(".", bundles)
                db.unlink()


class TrustdResourcesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = runpy.run_path(str(MODULE_PATH))
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = self.module["Store"](
            Path(self.temp_dir.name) / "health.sqlite3", emit_stdout=False
        )
        self.args = SimpleNamespace(
            command_timeout=1,
            trustd_cpu_warn=50,
            trustd_rss_warn_mb=100,
            trustd_rss_growth_warn_mb_per_minute=1,
            trustd_rss_error_mb=200,
        )

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def collect(self, rows: list[tuple[int, str, int]]) -> list[dict[str, Any]]:
        snapshot_id = self.store.create_snapshot("test", [])

        def run(command: list[str], **_kwargs: Any) -> tuple[int, str, str, bool, int]:
            if command[0] == "pgrep":
                return 0, "\n".join(str(row[0]) for row in rows), "", False, 1
            pid, user, rss_kb = next(row for row in rows if str(row[0]) == command[2])
            return (
                0,
                f"{pid} 1 {user} S 0.0 0.0 {rss_kb} 04-01:00:00 /usr/libexec/trustd",
                "",
                False,
                1,
            )

        with mock.patch.dict(
            self.module["collect_trustd_health"].__globals__, {"run_command": run}
        ):
            self.module["collect_trustd_health"](self.store, snapshot_id, self.args)
        signals = list(self.store.current_signals)
        self.store.finish_snapshot(snapshot_id, "ok")
        return signals

    def test_rss_rank_changes_do_not_report_restarts(self) -> None:
        # Ignore the old aggregate baseline on upgrade; it tracks RSS rank.
        self.store.set_state(
            "last_process_resource:trustd",
            json.dumps({"ts": "2000-01-01T00:00:00Z", "pid": "712", "rss_mb": 10}),
        )
        self.assertEqual(self.collect([(495, "_trustd", 11264), (712, "alex", 10240)]), [])
        self.assertEqual(self.collect([(712, "alex", 10240), (495, "_trustd", 9216)]), [])
        self.assertEqual(self.collect([(495, "_trustd", 9216), (712, "alex", 8192)]), [])

    def test_restart_of_smaller_instance_is_reported(self) -> None:
        self.collect([(495, "_trustd", 10240), (712, "alex", 5120)])
        signals = self.collect([(495, "_trustd", 10240), (900, "alex", 5120)])
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["signal"], "process_pid_changed")
        self.assertEqual(str(signals[0]["pid"]), "900")
        self.assertEqual(str(signals[0]["value"]), "712")

    def test_growth_of_smaller_instance_is_reported(self) -> None:
        self.collect([(495, "_trustd", 10240), (712, "alex", 5120)])
        signals = self.collect([(495, "_trustd", 10240), (712, "alex", 8192)])
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["signal"], "process_rss_growth_high")
        self.assertEqual(str(signals[0]["pid"]), "712")

    def test_new_user_has_no_previous_process(self) -> None:
        self.collect([(495, "_trustd", 10240)])
        self.assertEqual(self.collect([(495, "_trustd", 10240), (712, "alex", 5120)]), [])


class NotificationSummaryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = runpy.run_path(str(MODULE_PATH))
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = self.module["Store"](
            Path(self.temp_dir.name) / "health.sqlite3", emit_stdout=False
        )
        self.args = SimpleNamespace(
            brrr_notify_cooldown_minutes=10,
            brrr_thread_id="macos-session-health",
            brrr_interruption_level="passive",
            brrr_open_url="",
            brrr_timeout=2,
        )

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def notify(self, signals: set[str], status: str = "unhealthy") -> None:
        snapshot_id = self.store.create_snapshot("test", [])
        for signal in signals:
            self.store.emit(
                snapshot_id,
                "health_signal",
                "warning",
                signal=signal,
                value=1,
                detail="test",
            )
        self.module["maybe_send_brrr_notification"](
            self.store, snapshot_id, self.args, status
        )

    def install_delivery_stub(
        self, results: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        queued = list(results or [])

        def deliver(payload: dict[str, Any], _timeout: float) -> dict[str, Any]:
            payloads.append(payload)
            if queued:
                return queued.pop(0)
            return {
                "exit": 0,
                "timeout": False,
                "duration_ms": 1,
                "auth_mode": "bearer",
                "credential_source": "test",
                "endpoint": "https://example.test/send",
                "http_status": 202,
            }

        self.module["maybe_send_brrr_notification"].__globals__["deliver_brrr"] = deliver
        return payloads

    def test_sorted_signal_summary_and_success_cooldown(self) -> None:
        payloads = self.install_delivery_stub()
        self.notify({"spawn_failed"})

        self.assertEqual(len(payloads), 1)
        self.assertIn(
            "signals=spawn_failed", payloads[0]["message"]
        )
        self.assertIn("status=unhealthy", payloads[0]["message"])
        self.assertIn("incident --hours 6 --format markdown", payloads[0]["message"])
        self.assertIsNotNone(self.store.get_state("last_brrr_notification_sent_at"))

    def test_no_signal_sends_nothing_and_no_recovery(self) -> None:
        payloads = self.install_delivery_stub()
        self.notify(set(), status="ok")
        self.assertEqual(payloads, [])

    def test_failed_delivery_does_not_start_cooldown(self) -> None:
        payloads = self.install_delivery_stub(
            [
                {
                    "exit": 1,
                    "timeout": True,
                    "duration_ms": 10,
                    "auth_mode": "bearer",
                    "credential_source": "test",
                    "endpoint": "https://example.test/send",
                    "error": "timed out",
                }
            ]
        )
        self.notify({"spawn_failed"})
        self.notify({"spawn_failed"})
        self.assertEqual(len(payloads), 2)

    def test_notification_channel_signal_does_not_bootstrap_notification(self) -> None:
        snapshot_id = self.store.create_snapshot("test", [])
        with mock.patch.dict(
            self.module["collect_notification_channel_guard"].__globals__,
            {
                "brrr_configuration": lambda: {
                    "configured": False,
                    "auth_mode": "unconfigured",
                    "credential_source": "",
                    "endpoint": "",
                    "secret": "",
                }
            },
        ):
            self.module["collect_notification_channel_guard"](
                self.store, snapshot_id, SimpleNamespace()
            )
        self.assertIn(
            "notification_channel_unconfigured",
            {signal["signal"] for signal in self.store.current_signals},
        )
        payloads = self.install_delivery_stub()
        self.module["maybe_send_brrr_notification"](
            self.store, snapshot_id, self.args, "unhealthy"
        )
        self.assertEqual(payloads, [])


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
        lifecycle["bootstrap_launch_agent"] = mock.Mock(side_effect=self.module["CliError"]("boom"))
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
            with self.assertRaisesRegex(self.module["CliError"], "removed=plist.*rerun uninstall"):
                uninstall()
            self.assertFalse(self.plist.exists())
            self.assertEqual(uninstall(), 0)
        self.assertFalse(self.wrapper.exists())
        self.assertFalse(self.runtime.exists())


if __name__ == "__main__":
    unittest.main()
