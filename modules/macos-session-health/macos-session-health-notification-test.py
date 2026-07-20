#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import runpy
import subprocess
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

    def test_secret_file_accepts_plain_quoted_and_exported_forms(self) -> None:
        reader = self.module["read_brrr_secret_from_file"]
        env_file = Path(self.temp_dir.name) / "env"
        for content, expected in (
            ("BRRR_SECRET=plain\n", "plain"),
            ("BRRR_SECRET='quoted value'\n", "quoted value"),
            ("export BRRR_SECRET=exported\n", "exported"),
            ("# comment\nexport BRRR_SECRET='exported quoted'\n", "exported quoted"),
            ("OTHER=x\n", ""),
            ("export\n", ""),
        ):
            env_file.write_text(content)
            self.assertEqual(reader(env_file), expected, content)

    def test_explicit_secret_wins_over_exe_dev_proxy(self) -> None:
        with (
            mock.patch.dict(self.module["os"].environ, {"BRRR_SECRET": "test-secret"}),
            mock.patch.object(self.module["Path"], "is_file", return_value=True),
        ):
            config = self.module["brrr_configuration"]()

        self.assertEqual(config["auth_mode"], "bearer")
        self.assertEqual(config["endpoint"], "https://api.brrr.now/v1/send")


class BagModeGuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = runpy.run_path(str(MODULE_PATH))
        self.temp_dir = tempfile.TemporaryDirectory()
        self.bag_mode_dir = Path(self.temp_dir.name) / "bag-mode"
        self.store = self.module["Store"](
            Path(self.temp_dir.name) / "health.sqlite3", emit_stdout=False
        )
        self.args = SimpleNamespace(
            bag_mode_dir=self.bag_mode_dir,
            bag_mode_guard_min_processes=1,
        )

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def collect(self, codex_summary: dict[str, Any]) -> list[dict[str, Any]]:
        self.store.current_signals = []
        self.store.current_brrr_observations = set()
        snapshot_id = self.store.create_snapshot("test", [])
        self.module["collect_bag_mode_guard"](
            self.store, snapshot_id, self.args, codex_summary
        )
        return self.store.current_signals

    def signal_names(self, signals: list[dict[str, Any]]) -> set[str]:
        return {str(signal.get("signal")) for signal in signals}

    def write_state(self, pid: int | str) -> None:
        (self.bag_mode_dir / "state").write_text(f"last_event\tstarted\npid\t{pid}\n")

    def test_disabled_bag_mode_with_active_ai_session_alerts(self) -> None:
        self.bag_mode_dir.mkdir(parents=True)
        signals = self.collect({"codex_app_server_count": 1, "node_repl_count": 2})

        self.assertIn("bag_mode_unarmed", self.signal_names(signals))
        self.assertIn("bag_mode_unprotected", self.store.current_brrr_observations)
        unarmed = next(
            signal for signal in signals if signal["signal"] == "bag_mode_unarmed"
        )
        self.assertEqual(unarmed["value"], 3)

    def test_disabled_bag_mode_without_ai_session_stays_quiet(self) -> None:
        self.bag_mode_dir.mkdir(parents=True)
        signals = self.collect({"codex_app_server_count": 0, "node_repl_count": 0})

        self.assertEqual(self.signal_names(signals), set())
        self.assertIn("bag_mode_unprotected", self.store.current_brrr_observations)

    def test_enabled_bag_mode_with_live_controller_stays_quiet(self) -> None:
        self.bag_mode_dir.mkdir(parents=True)
        (self.bag_mode_dir / "enabled").write_text("")
        self.write_state(os.getpid())
        signals = self.collect({"codex_app_server_count": 1, "node_repl_count": 0})

        self.assertEqual(self.signal_names(signals), set())
        self.assertIn("bag_mode_unprotected", self.store.current_brrr_observations)

    def test_enabled_bag_mode_with_dead_controller_alerts(self) -> None:
        self.bag_mode_dir.mkdir(parents=True)
        (self.bag_mode_dir / "enabled").write_text("")
        dead = subprocess.Popen(["/usr/bin/true"])
        dead.wait()
        self.write_state(dead.pid)
        signals = self.collect({})

        self.assertIn("bag_mode_stalled", self.signal_names(signals))

    def test_unreadable_state_and_failed_ps_do_not_claim_observation(self) -> None:
        self.bag_mode_dir.mkdir(parents=True)
        self.write_state("not-a-pid")
        signals = self.collect({})

        self.assertEqual(self.signal_names(signals), set())
        self.assertNotIn("bag_mode_unprotected", self.store.current_brrr_observations)

    def test_missing_bag_mode_installation_observes_without_signals(self) -> None:
        signals = self.collect({"codex_app_server_count": 5})

        self.assertEqual(self.signal_names(signals), set())
        self.assertIn("bag_mode_unprotected", self.store.current_brrr_observations)

    def test_incident_mapping_prefers_stalled_over_unarmed(self) -> None:
        build = self.module["build_brrr_incident"]
        unarmed = {"severity": "warning", "signal": "bag_mode_unarmed", "value": 2}
        stalled = {"severity": "error", "signal": "bag_mode_stalled", "value": 1}

        incident = build([unarmed], "snapshot", "unhealthy", 1000)
        self.assertEqual(incident["kind"], "bag_mode_unprotected")
        self.assertIn("bag-mode", incident["title"])
        self.assertIn("bag-mode start", incident["message"])

        incident = build([unarmed, stalled], "snapshot", "unhealthy", 1000)
        self.assertEqual(incident["kind"], "bag_mode_unprotected")
        self.assertIn("停摆", incident["title"])

    def test_spawn_failure_outranks_bag_mode_and_process_table(self) -> None:
        build = self.module["build_brrr_incident"]
        incident = build(
            [
                {"severity": "warning", "signal": "bag_mode_unarmed", "value": 1},
                {"severity": "warning", "signal": "process_table_high", "value": 900},
                {"severity": "critical", "signal": "spawn_failed", "value": 1},
            ],
            "snapshot",
            "unhealthy",
            1000,
        )
        self.assertEqual(incident["kind"], "spawn_failed")


class ProcessTablePressureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = runpy.run_path(str(MODULE_PATH))
        self.pressure = self.module["process_table_pressure_signals"]

    def test_below_threshold_stays_quiet(self) -> None:
        self.assertEqual(self.pressure(500, 400, 1000, 900, 85), [])

    def test_reaching_threshold_warns_for_each_exhausted_table(self) -> None:
        both = self.pressure(850, 765, 1000, 900, 85)
        self.assertEqual(
            [signal_name for signal_name, _value, _detail in both],
            ["process_table_high", "user_process_table_high"],
        )
        self.assertIn("850 of 1000", both[0][2])

        user_only = self.pressure(500, 765, 1000, 900, 85)
        self.assertEqual(
            [signal_name for signal_name, _value, _detail in user_only],
            ["user_process_table_high"],
        )

    def test_unknown_counts_or_limits_stay_quiet(self) -> None:
        self.assertEqual(self.pressure(None, None, 1000, 900, 85), [])
        self.assertEqual(self.pressure(900, 800, None, 0, 85), [])

    def test_incident_mapping_reports_process_table_pressure(self) -> None:
        build = self.module["build_brrr_incident"]
        incident = build(
            [
                {
                    "severity": "warning",
                    "signal": "process_table_high",
                    "value": 900,
                    "detail": "900 of 1000 system process slots are in use",
                }
            ],
            "snapshot",
            "unhealthy",
            1000,
        )
        self.assertEqual(incident["kind"], "process_table_high")
        self.assertIn("900 of 1000", incident["message"])


class LifecycleRollbackTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = runpy.run_path(str(MODULE_PATH))
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.runtime = root / "runtime"
        self.wrapper = root / "bin/macos-session-health"
        self.plist = root / "LaunchAgents/com.alex.macos-session-health.plist"
        self.runtime.parent.mkdir(parents=True, exist_ok=True)
        self.wrapper.parent.mkdir(parents=True)
        self.plist.parent.mkdir(parents=True)
        self.runtime.write_text("runtime\n")
        marker = self.module["WRAPPER_MARKER"]
        self.wrapper.write_text(f"#!/bin/sh\n{marker}\nexit 0\n")
        self.plist.write_text("plist\n")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_uninstall_failure_restores_files_and_loaded_state(self) -> None:
        uninstall = self.module["uninstall_launch_agent"]
        function_globals = uninstall.__globals__
        original_unlink = Path.unlink
        failed = False

        def fail_wrapper_unlink(file_path: Path, *args: Any, **kwargs: Any) -> None:
            nonlocal failed
            if file_path == self.wrapper and not failed:
                failed = True
                raise OSError("injected wrapper removal failure")
            original_unlink(file_path, *args, **kwargs)

        loaded = subprocess.CompletedProcess(["launchctl", "print"], 0, "", "")
        with (
            mock.patch.object(function_globals["sys"], "platform", "darwin"),
            mock.patch.dict(
                function_globals,
                {
                    "RUNTIME_CLI": self.runtime,
                    "USER_BIN": self.wrapper,
                    "LAUNCH_AGENT": self.plist,
                    "DEFAULT_DB": Path(self.temp_dir.name) / "state/health.sqlite3",
                    "launchd_job": mock.Mock(return_value=loaded),
                    "bootout_launch_agent": mock.Mock(),
                    "bootstrap_launch_agent": mock.Mock(),
                },
            ),
            mock.patch.object(Path, "unlink", fail_wrapper_unlink),
        ):
            with self.assertRaises(self.module["CliError"]) as raised:
                uninstall()
            bootstrap = function_globals["bootstrap_launch_agent"]
            bootstrap.assert_called_once()

        self.assertIn("LaunchAgent state restored", str(raised.exception))
        self.assertEqual(self.runtime.read_text(), "runtime\n")
        self.assertIn(self.module["WRAPPER_MARKER"], self.wrapper.read_text())
        self.assertEqual(self.plist.read_text(), "plist\n")


class ChannelGuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = runpy.run_path(str(MODULE_PATH))
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = self.module["Store"](
            Path(self.temp_dir.name) / "health.sqlite3", emit_stdout=False
        )
        self.args = SimpleNamespace()

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def collect(self, *, secret: str = "") -> list[dict[str, Any]]:
        self.store.current_signals = []
        self.store.current_brrr_observations = set()
        snapshot_id = self.store.create_snapshot("test", [])
        environment = {"BRRR_SECRET": secret, "BRRR_ENV_FILE": ""}
        with (
            mock.patch.dict(self.module["os"].environ, environment),
            mock.patch.dict(
                self.module["collect_notification_channel_guard"].__globals__,
                {"BRRR_ENV_FILES": (Path(self.temp_dir.name) / "missing-env",)},
            ),
        ):
            self.module["collect_notification_channel_guard"](
                self.store, snapshot_id, self.args
            )
        return self.store.current_signals

    def seed_failed_deliveries(self, count: int) -> None:
        snapshot_id = self.store.create_snapshot("seed", [])
        for _ in range(count):
            self.store.emit(
                snapshot_id, "brrr_notification", "warning", sent=False
            )

    def signal_names(self, signals: list[dict[str, Any]]) -> set[str]:
        return {str(signal.get("signal")) for signal in signals}

    def test_unconfigured_channel_signals_and_claims_observation(self) -> None:
        signals = self.collect()

        self.assertIn("notification_channel_unconfigured", self.signal_names(signals))
        self.assertIn(
            "notification_channel_unhealthy", self.store.current_brrr_observations
        )

    def test_configured_channel_without_failures_stays_quiet(self) -> None:
        signals = self.collect(secret="test-secret")

        self.assertEqual(self.signal_names(signals), set())
        self.assertIn(
            "notification_channel_unhealthy", self.store.current_brrr_observations
        )

    def test_failure_streak_crosses_threshold_into_a_signal(self) -> None:
        self.seed_failed_deliveries(2)
        below = self.collect(secret="test-secret")
        self.assertEqual(self.signal_names(below), set())

        self.seed_failed_deliveries(1)
        at_threshold = self.collect(secret="test-secret")
        self.assertIn(
            "notification_channel_failing", self.signal_names(at_threshold)
        )
        failing = next(
            signal
            for signal in at_threshold
            if signal["signal"] == "notification_channel_failing"
        )
        self.assertEqual(failing["value"], 3)

    def test_incident_mapping_and_priorities_for_channel_health(self) -> None:
        build = self.module["build_brrr_incident"]
        unconfigured = {
            "severity": "warning",
            "signal": "notification_channel_unconfigured",
            "value": 1,
        }
        failing = {
            "severity": "warning",
            "signal": "notification_channel_failing",
            "value": 4,
        }
        skillshare = {
            "severity": "warning",
            "signal": "skillshare_unready",
            "value": 1,
            "detail": "skillshare executable is missing from PATH",
        }
        spawn = {"severity": "critical", "signal": "spawn_failed", "value": 1}

        incident = build([unconfigured], "snapshot", "unhealthy", 1000)
        self.assertEqual(incident["kind"], "notification_channel_unhealthy")
        self.assertIn("BRRR_SECRET", incident["message"])

        incident = build([failing], "snapshot", "unhealthy", 1000)
        self.assertEqual(incident["kind"], "notification_channel_unhealthy")
        self.assertIn("4", incident["message"])

        incident = build([unconfigured, spawn], "snapshot", "unhealthy", 1000)
        self.assertEqual(incident["kind"], "spawn_failed")

        incident = build([skillshare, unconfigured], "snapshot", "unhealthy", 1000)
        self.assertEqual(incident["kind"], "notification_channel_unhealthy")

    def test_channel_recovery_follows_the_observed_state_machine(self) -> None:
        notify_args = SimpleNamespace(
            brrr_syspolicyd_assessment_failure_count=1000,
            brrr_notify_cooldown_minutes=0,
            brrr_thread_id="macos-session-health",
            brrr_interruption_level="passive",
            brrr_open_url="",
            brrr_timeout=10,
        )
        payloads: list[dict[str, Any]] = []

        def deliver(
            payload: dict[str, Any], _timeout: float, **_kwargs: Any
        ) -> dict[str, Any]:
            payloads.append(payload)
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
        failing = {
            "severity": "warning",
            "signal": "notification_channel_failing",
            "value": 3,
        }

        snapshot_id = self.store.create_snapshot("test", [])
        self.store.current_signals = [failing]
        self.store.current_brrr_observations = {"notification_channel_unhealthy"}
        self.module["maybe_send_brrr_notification"](
            self.store, snapshot_id, notify_args, "unhealthy"
        )
        self.assertEqual(len(payloads), 1)

        snapshot_id = self.store.create_snapshot("test", [])
        self.store.current_signals = []
        self.store.current_brrr_observations = {"notification_channel_unhealthy"}
        self.module["maybe_send_brrr_notification"](
            self.store, snapshot_id, notify_args, "ok"
        )
        self.assertEqual(len(payloads), 2)
        self.assertIn("已恢复", payloads[1]["title"])


class SkillshareGuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = runpy.run_path(str(MODULE_PATH))
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "skillshare/config.yaml"
        self.store = self.module["Store"](
            Path(self.temp_dir.name) / "health.sqlite3", emit_stdout=False
        )
        self.args = SimpleNamespace(skillshare_config=self.config_path)

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def collect(
        self,
        executable: str | None,
        *,
        status: dict[str, Any] | None = None,
        status_returncode: int = 0,
    ) -> list[dict[str, Any]]:
        self.store.current_signals = []
        self.store.current_brrr_observations = set()
        self.status_calls = []
        snapshot_id = self.store.create_snapshot("test", [])

        def runner(cmd: list[str], **_kwargs: Any) -> SimpleNamespace:
            self.status_calls.append(cmd)
            document = {"source": status} if status is not None else {}
            return SimpleNamespace(
                returncode=status_returncode, stdout=json.dumps(document)
            )

        self.module["collect_skillshare_guard"](
            self.store,
            snapshot_id,
            self.args,
            executable_finder=lambda _name: executable,
            runner=runner,
        )
        return self.store.current_signals

    def details(self, signals: list[dict[str, Any]]) -> list[str]:
        return [
            str(signal.get("detail"))
            for signal in signals
            if signal.get("signal") == "skillshare_unready"
        ]

    def touch_config(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text("sources:\n  skills: ~/skills\n")

    def test_missing_executable_signals_first(self) -> None:
        signals = self.collect(None)

        self.assertIn("executable is missing", self.details(signals)[0])
        self.assertIn("skillshare_unready", self.store.current_brrr_observations)

    def test_missing_configuration_signals_with_its_path(self) -> None:
        signals = self.collect("/opt/homebrew/bin/skillshare")

        self.assertIn("configuration is missing", self.details(signals)[0])

    def test_source_status_transitions_between_present_and_missing(self) -> None:
        self.touch_config()
        ready = self.collect(
            "/opt/homebrew/bin/skillshare",
            status={"path": "/Users/x/skills", "exists": True},
        )
        self.assertEqual(self.details(ready), [])
        self.assertIn("skillshare_unready", self.store.current_brrr_observations)
        # It queries skillshare's own status, not the config file.
        self.assertEqual(self.status_calls[0][1:4], ["status", "--json", "-g"])

        broken = self.collect(
            "/opt/homebrew/bin/skillshare",
            status={"path": "/Users/x/skills", "exists": False},
        )
        self.assertIn("source is missing (/Users/x/skills)", self.details(broken)[0])

    def test_unreadable_status_is_reported_not_silently_ready(self) -> None:
        self.touch_config()
        signals = self.collect("/opt/homebrew/bin/skillshare", status_returncode=1)

        self.assertIn("status could not be read", self.details(signals)[0])

    def test_incident_mapping_carries_the_detail(self) -> None:
        build = self.module["build_brrr_incident"]
        incident = build(
            [
                {
                    "severity": "warning",
                    "signal": "skillshare_unready",
                    "value": 1,
                    "detail": "skillshare configuration is missing (/tmp/x)",
                }
            ],
            "snapshot",
            "unhealthy",
            1000,
        )
        self.assertEqual(incident["kind"], "skillshare_unready")
        self.assertIn("skillshare doctor", incident["message"])
        self.assertIn("configuration is missing", incident["message"])


class LegacyInstallDetectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = runpy.run_path(str(MODULE_PATH))
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.user_bin = self.root / "macos-session-health"
        # runpy returns a copy of the namespace; the functions read USER_BIN
        # from their shared __globals__, so patch there, not on self.module.
        self.module["legacy_symlink_install"].__globals__["USER_BIN"] = self.user_bin

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_symlink_to_module_script_is_recognized_as_legacy(self) -> None:
        module_dir = self.root / "dotfiles/modules/macos-session-health"
        module_dir.mkdir(parents=True)
        script = module_dir / "macos-session-health"
        script.write_text("#!/usr/bin/env python3\n")
        self.user_bin.symlink_to(script)

        self.assertTrue(self.module["legacy_symlink_install"]())
        self.assertTrue(self.module["replaceable_install"]())

    def test_symlink_to_an_unrelated_target_is_not_legacy(self) -> None:
        other = self.root / "elsewhere/some-tool"
        other.parent.mkdir(parents=True)
        other.write_text("x")
        self.user_bin.symlink_to(other)

        self.assertFalse(self.module["legacy_symlink_install"]())
        self.assertFalse(self.module["replaceable_install"]())

    def test_plain_unmanaged_file_is_neither_legacy_nor_replaceable(self) -> None:
        self.user_bin.write_text("#!/bin/sh\necho hi\n")

        self.assertFalse(self.module["legacy_symlink_install"]())
        self.assertFalse(self.module["replaceable_install"]())


if __name__ == "__main__":
    unittest.main()
