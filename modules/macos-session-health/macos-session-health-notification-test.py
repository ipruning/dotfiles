#!/usr/bin/env python3
from __future__ import annotations

import runpy
import subprocess
import tempfile
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock


MODULE_PATH = Path(__file__).with_name("macos-session-health")


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
        self.notify({"spawn_failed", "bag_mode_unprotected"})
        self.notify({"spawn_failed"})

        self.assertEqual(len(payloads), 1)
        self.assertIn(
            "signals=bag_mode_unprotected,spawn_failed", payloads[0]["message"]
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
