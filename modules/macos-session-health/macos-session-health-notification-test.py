#!/usr/bin/env python3
from __future__ import annotations

import runpy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock


MODULE_PATH = Path(__file__).with_name("macos-session-health")


class NotificationStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = runpy.run_path(str(MODULE_PATH))
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = self.module["Store"](
            Path(self.temp_dir.name) / "health.sqlite3", emit_stdout=False
        )
        self.args = SimpleNamespace(
            brrr_syspolicyd_assessment_failure_count=1000,
            brrr_notify_cooldown_minutes=0,
            brrr_thread_id="macos-session-health",
            brrr_interruption_level="passive",
            brrr_open_url="",
            brrr_timeout=10,
        )

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def snapshot(self) -> str:
        return self.store.create_snapshot("test", [])

    def spawn_failure(self) -> list[dict[str, Any]]:
        return [
            {
                "severity": "critical",
                "signal": "spawn_failed",
                "name": "spawn-test",
                "value": 1,
            }
        ]

    def install_delivery_stub(
        self, results: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        queued_results = list(results or [])

        def deliver(
            payload: dict[str, Any], _timeout: float, **_kwargs: Any
        ) -> dict[str, Any]:
            payloads.append(payload)
            if queued_results:
                return queued_results.pop(0)
            return {
                "exit": 0,
                "timeout": False,
                "duration_ms": 1,
                "auth_mode": "bearer",
                "credential_source": "test",
                "http_status": 202,
                "attempts": 1,
            }

        self.module["maybe_send_brrr_notification"].__globals__["deliver_brrr"] = (
            deliver
        )
        return payloads

    def notify(
        self,
        signals: list[dict[str, Any]],
        status: str = "unhealthy",
        *,
        observed: set[str] | None = None,
    ) -> None:
        snapshot_id = self.snapshot()
        self.store.current_signals = signals
        self.store.current_brrr_observations = set(observed or set())
        self.module["maybe_send_brrr_notification"](
            self.store, snapshot_id, self.args, status
        )

    def test_same_incident_sends_once_and_has_self_contained_content(self) -> None:
        payloads = self.install_delivery_stub()
        with mock.patch.object(
            self.module["socket"], "gethostname", return_value="macbook.example"
        ):
            self.notify(self.spawn_failure())
            self.notify(self.spawn_failure())

        self.assertEqual(len(payloads), 1)
        payload = payloads[0]
        self.assertEqual(payload["title"], "macbook.example: macOS 无法正常启动进程")
        self.assertEqual(payload["subtitle"], "macOS session health")
        self.assertIn("新的 app 或 shell 命令可能无法启动", payload["message"])
        self.assertIn("macos-session-health incident", payload["message"])
        self.assertNotIn("snapshot=", payload["message"])

    def test_failed_delivery_does_not_suppress_retry(self) -> None:
        payloads = self.install_delivery_stub(
            [
                {
                    "exit": 1,
                    "timeout": True,
                    "duration_ms": 10,
                    "auth_mode": "bearer",
                    "credential_source": "test",
                    "attempts": 3,
                    "error": "timeout",
                }
            ]
        )
        self.args.brrr_notify_cooldown_minutes = 10

        self.notify(self.spawn_failure())
        self.notify(self.spawn_failure())

        self.assertEqual(len(payloads), 2)

    def test_recovery_sends_once_after_notified_incident(self) -> None:
        payloads = self.install_delivery_stub()

        self.notify(self.spawn_failure())
        self.notify([], status="ok", observed={"spawn_failed"})
        self.notify([], status="ok", observed={"spawn_failed"})

        self.assertEqual(len(payloads), 2)
        self.assertIn("恢复", payloads[1]["title"])
        self.assertIn("无需针对该异常操作", payloads[1]["message"])

    def test_unobserved_detector_does_not_recover_active_incident(self) -> None:
        payloads = self.install_delivery_stub()

        self.notify(self.spawn_failure())
        self.notify([], status="ok")

        self.assertEqual(len(payloads), 1)
        self.assertEqual(
            self.store.get_state("active_brrr_incident_kind"), "spawn_failed"
        )

    def test_skipped_passive_log_scan_waits_for_explicit_clean_observation(
        self,
    ) -> None:
        payloads = self.install_delivery_stub()
        assessment_failure = [
            {
                "severity": "error",
                "signal": "syspolicyd_assessment_failure",
                "value": 1200,
            }
        ]

        self.notify(assessment_failure)
        self.notify([], status="ok")
        self.notify(
            [],
            status="ok",
            observed={"syspolicyd_assessment_failure"},
        )

        self.assertEqual(len(payloads), 2)
        self.assertIn("Gatekeeper", payloads[0]["title"])
        self.assertIn("恢复", payloads[1]["title"])

    def test_changed_incident_sends_without_waiting_for_cooldown(self) -> None:
        payloads = self.install_delivery_stub()
        self.args.brrr_notify_cooldown_minutes = 60

        self.notify(self.spawn_failure())
        self.notify(
            [
                {
                    "severity": "error",
                    "signal": "collector_exception",
                    "value": 1,
                }
            ]
        )

        self.assertEqual(len(payloads), 2)
        self.assertIn("采集器异常", payloads[1]["title"])

    def test_failed_recovery_is_retried(self) -> None:
        payloads = self.install_delivery_stub(
            [
                {
                    "exit": 0,
                    "timeout": False,
                    "duration_ms": 1,
                    "auth_mode": "bearer",
                    "credential_source": "test",
                    "http_status": 202,
                    "attempts": 1,
                },
                {
                    "exit": 1,
                    "timeout": True,
                    "duration_ms": 10,
                    "auth_mode": "bearer",
                    "credential_source": "test",
                    "attempts": 3,
                    "error": "timeout",
                },
            ]
        )

        self.notify(self.spawn_failure())
        self.notify([], status="ok", observed={"spawn_failed"})
        self.notify([], status="ok", observed={"spawn_failed"})

        self.assertEqual(len(payloads), 3)
        self.assertIn("恢复", payloads[1]["title"])
        self.assertIn("恢复", payloads[2]["title"])

    def test_legacy_onset_timestamp_does_not_suppress_new_state_machine(self) -> None:
        payloads = self.install_delivery_stub()
        self.args.brrr_notify_cooldown_minutes = 60
        self.store.set_state("last_brrr_notification_sent_at", self.module["utc_now"]())

        self.notify(self.spawn_failure())

        self.assertEqual(len(payloads), 1)

    def test_code_sign_clone_requires_positive_observation_evidence(self) -> None:
        collect = self.module["collect_code_sign_clone_status"]
        collect.__globals__["candidate_code_sign_clone_paths"] = lambda: []
        args = SimpleNamespace(
            code_sign_clone_timeout=1,
            code_sign_clone_warn_mb=100,
            code_sign_clone_growth_warn_mb_per_minute=10,
        )

        collect(self.store, self.snapshot(), args)
        self.assertNotIn("code_sign_clone_growth", self.store.current_brrr_observations)

        missing_path = Path(self.temp_dir.name) / "missing"
        collect.__globals__["candidate_code_sign_clone_paths"] = lambda: [missing_path]
        collect(self.store, self.snapshot(), args)
        self.assertNotIn("code_sign_clone_growth", self.store.current_brrr_observations)

        existing_path = Path(self.temp_dir.name) / "existing"
        existing_path.mkdir()
        collect.__globals__["candidate_code_sign_clone_paths"] = lambda: [existing_path]
        collect.__globals__["run_command"] = lambda *_args, **_kwargs: (
            124,
            "",
            "timeout",
            True,
            1000,
        )
        collect(self.store, self.snapshot(), args)
        self.assertNotIn("code_sign_clone_growth", self.store.current_brrr_observations)

    def test_reporting_failures_do_not_mask_collector_exception(self) -> None:
        class CollectorFailure(Exception):
            pass

        snapshot = self.module["snapshot"]
        snapshot.__globals__["collect_system_context"] = lambda *_args, **_kwargs: (
            _ for _ in ()
        ).throw(CollectorFailure("original collector failure"))
        original_emit = self.store.emit

        def failing_emit(
            snapshot_id: str,
            event: str,
            severity: str | None = None,
            **data: Any,
        ) -> None:
            if event in {"health_signal", "snapshot_end"}:
                raise RuntimeError("reporting failed")
            original_emit(snapshot_id, event, severity, **data)

        self.store.emit = failing_emit
        self.store.finish_snapshot = lambda *_args: (_ for _ in ()).throw(
            RuntimeError("finalization failed")
        )
        args = SimpleNamespace(
            app=[],
            db=self.store.db_path,
            retention_days=14,
            command_timeout=1,
        )

        with self.assertRaisesRegex(CollectorFailure, "original collector failure"):
            snapshot(args, self.store, "test")

    def test_native_fallback_fires_once_per_cooldown_when_allowed(self) -> None:
        fallback_calls: list[dict[str, Any]] = []
        deliver = self.module["deliver_brrr"]
        deliver.__globals__["brrr_configuration"] = lambda **_: {
            "configured": False,
            "auth_mode": "unconfigured",
            "endpoint": "",
            "credential_source": "",
            "secret": "",
        }
        deliver.__globals__["deliver_native_notification"] = (
            lambda payload, timeout: fallback_calls.append(payload) or True
        )

        withheld = deliver({"title": "t", "message": "m"}, 1)
        self.assertEqual(withheld["exit"], 3)
        self.assertFalse(withheld["native_fallback"])
        self.assertEqual(fallback_calls, [])

        allowed = deliver({"title": "t", "message": "m"}, 1, native_fallback=True)
        self.assertTrue(allowed["native_fallback"])
        self.assertEqual(fallback_calls, [{"title": "t", "message": "m"}])

        self.assertTrue(self.module["native_fallback_due"](self.store))
        self.store.set_state(
            "last_brrr_native_fallback_at", self.module["utc_now"]()
        )
        self.assertFalse(self.module["native_fallback_due"](self.store))

    def test_persistent_incident_banners_are_rate_limited(self) -> None:
        banner_count = 0

        def fake_native(payload: dict[str, Any], timeout: float) -> bool:
            nonlocal banner_count
            banner_count += 1
            return True

        maybe_send = self.module["maybe_send_brrr_notification"]
        maybe_send.__globals__["deliver_native_notification"] = fake_native
        maybe_send.__globals__["brrr_configuration"] = lambda **_: {
            "configured": False,
            "auth_mode": "unconfigured",
            "endpoint": "",
            "credential_source": "",
            "secret": "",
        }

        for _ in range(5):
            self.notify(self.spawn_failure())

        self.assertEqual(banner_count, 1)

    def test_native_fallback_posts_title_and_message_via_argv(self) -> None:
        recorded: list[list[str]] = []

        def runner(command: list[str], **_kwargs: Any) -> Any:
            recorded.append(command)
            return SimpleNamespace(returncode=0)

        sent = self.module["deliver_native_notification"](
            {"title": "host: 异常", "message": "详情"}, 1, runner=runner
        )

        self.assertTrue(sent)
        self.assertEqual(recorded[0][-2:], ["host: 异常", "详情"])

        def broken_runner(command: list[str], **_kwargs: Any) -> Any:
            raise OSError("osascript missing")

        self.assertFalse(
            self.module["deliver_native_notification"](
                {"title": "t", "message": "m"}, 1, runner=broken_runner
            )
        )

    def test_status_health_reports_snapshot_and_delivery_failure_streak(self) -> None:
        db_path = Path(self.temp_dir.name) / "health.sqlite3"
        snapshot_id = self.snapshot()
        self.store.emit(snapshot_id, "brrr_notification", None, sent=True)
        self.store.emit(snapshot_id, "brrr_notification", "warning", sent=False)
        self.store.emit(snapshot_id, "brrr_notification", "warning", sent=False)
        self.store.finish_snapshot(snapshot_id, "unhealthy")

        health = self.module["runtime_status_health"](db_path)

        self.assertTrue(health["last_snapshot_at"])
        self.assertEqual(health["last_snapshot_status"], "unhealthy")
        self.assertEqual(health["consecutive_delivery_failures"], 2)

        assert self.store.conn is not None
        self.store.conn.execute(
            "UPDATE events SET ts = '2026-01-01T00:00:00Z'"
            " WHERE event = 'brrr_notification'"
        )
        self.store.conn.commit()
        aged = self.module["runtime_status_health"](db_path)
        self.assertEqual(aged["consecutive_delivery_failures"], 0)

        missing = self.module["runtime_status_health"](
            Path(self.temp_dir.name) / "absent.sqlite3"
        )
        self.assertEqual(missing["consecutive_delivery_failures"], 0)
        self.assertEqual(missing["last_snapshot_at"], "")

    def test_explicit_secret_wins_over_exe_dev_proxy(self) -> None:
        with (
            mock.patch.dict(self.module["os"].environ, {"BRRR_SECRET": "test-secret"}),
            mock.patch.object(self.module["Path"], "is_file", return_value=True),
        ):
            config = self.module["brrr_configuration"]()

        self.assertEqual(config["auth_mode"], "bearer")
        self.assertEqual(config["endpoint"], "https://api.brrr.now/v1/send")


if __name__ == "__main__":
    unittest.main()
