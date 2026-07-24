"""Read-only macOS service and module checks."""

from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path

from .models import ExecutableFinder, Finding, Severity

SESSION_HEALTH_SNAPSHOT_MAX_AGE = dt.timedelta(minutes=30)
SESSION_HEALTH_FAILURE_STREAK = 3


def _session_health_findings(
    executable_finder: ExecutableFinder,
    *,
    now: dt.datetime | None = None,
) -> list[Finding]:
    executable = executable_finder("macos-session-health")
    if executable is None:
        return [
            Finding(
                "session_health.agent",
                Severity.WARN,
                "session_health.missing",
                "macos-session-health is not installed",
                action=(
                    "Run modules/macos-session-health/macos-session-health install."
                ),
            ),
        ]
    try:
        completed = subprocess.run(
            [str(executable), "status", "--format", "json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return [
            Finding(
                "session_health.agent",
                Severity.WARN,
                "session_health.status_unavailable",
                f"macos-session-health status could not run: {error}",
                action="Run macos-session-health status and resolve the failure.",
            ),
        ]
    if completed.returncode != 0 and not completed.stdout.strip():
        detail = completed.stderr.strip() or f"exit {completed.returncode}"
        return [
            Finding(
                "session_health.agent",
                Severity.WARN,
                "session_health.status_unavailable",
                f"macos-session-health status failed: {detail}",
                action="Run macos-session-health status and resolve the failure.",
            ),
        ]
    try:
        records = json.loads(completed.stdout)
        record = records[0]
        installed = bool(record["installed"])
        loaded = bool(record["loaded"])
        last_snapshot_at = str(record.get("last_snapshot_at") or "")
        failures = int(record.get("consecutive_delivery_failures") or 0)
        configured = bool(record.get("notification_configured"))
    except (json.JSONDecodeError, LookupError, TypeError, ValueError) as error:
        return [
            Finding(
                "session_health.agent",
                Severity.WARN,
                "session_health.status_invalid",
                f"macos-session-health status returned an invalid report: {error}",
                action="Run macos-session-health status --format json.",
            ),
        ]

    agent_ready = installed and loaded
    if completed.returncode != 0 and agent_ready:
        return [
            Finding(
                "session_health.agent",
                Severity.WARN,
                "session_health.status_unavailable",
                f"macos-session-health status contradicted exit {completed.returncode}",
                action="Run macos-session-health status and resolve the failure.",
            )
        ]
    findings = [
        Finding(
            "session_health.agent",
            Severity.OK if agent_ready else Severity.WARN,
            "session_health.agent_ready"
            if agent_ready
            else "session_health.agent_down",
            "session-health launch agent is installed and loaded"
            if agent_ready
            else "session-health launch agent is not running",
            action=(
                None
                if agent_ready
                else "Run modules/macos-session-health/macos-session-health install."
            ),
        ),
    ]

    snapshot_fresh = False
    if last_snapshot_at:
        try:
            last = dt.datetime.fromisoformat(last_snapshot_at.replace("Z", "+00:00"))
            current = now or dt.datetime.now(dt.timezone.utc)
            snapshot_fresh = current - last <= SESSION_HEALTH_SNAPSHOT_MAX_AGE
        except ValueError, TypeError:
            snapshot_fresh = False
    findings.append(
        Finding(
            "session_health.snapshot",
            Severity.OK if snapshot_fresh else Severity.WARN,
            "session_health.snapshot_recent"
            if snapshot_fresh
            else "session_health.snapshot_stale",
            f"last snapshot: {last_snapshot_at}"
            if last_snapshot_at
            else "no snapshot has been recorded",
            action=(
                None
                if snapshot_fresh
                else "Inspect launchd logs; the agent may have silently stopped."
            ),
        ),
    )

    if not configured:
        findings.append(
            Finding(
                "session_health.notifications",
                Severity.WARN,
                "session_health.notifications_unconfigured",
                "notification delivery is not configured",
                action="Provide BRRR_SECRET via ~/.config/brrr/env.",
            ),
        )
    elif failures >= SESSION_HEALTH_FAILURE_STREAK:
        findings.append(
            Finding(
                "session_health.notifications",
                Severity.WARN,
                "session_health.notifications_failing",
                f"last {failures} notification deliveries failed",
                action="Run macos-session-health notify-test --dry-run.",
            ),
        )
    else:
        findings.append(
            Finding(
                "session_health.notifications",
                Severity.OK,
                "session_health.notifications_ready",
                "notification delivery is configured and recently healthy",
            ),
        )
    return findings


def _module_source_constant(source: Path, name: str) -> str | None:
    try:
        for line in source.read_text().splitlines():
            if line.startswith(f'{name}="') and line.rstrip().endswith('"'):
                return line.rstrip()[len(name) + 2 : -1]
    except OSError:
        return None
    return None


def _bag_mode_findings(
    executable_finder: ExecutableFinder,
    repo_root: Path,
) -> list[Finding]:
    executable = executable_finder("bag-mode")
    if executable is None:
        return [
            Finding(
                "bag_mode.lifecycle",
                Severity.WARN,
                "bag_mode.missing",
                "bag-mode is not installed",
                action="Run modules/bag-mode/bag-mode install if this host needs lid-closed sessions.",
            ),
        ]
    try:
        completed = subprocess.run(
            [str(executable), "status", "--json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"status exited {completed.returncode}")
        record = json.loads(completed.stdout)
        enabled = bool(record["enabled"])
        phase = str(record["phase"])
        recovery_required = bool(record["recovery_required"])
        brightness_pending = bool(record["brightness_pending"])
    except (
        OSError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        LookupError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        return [
            Finding(
                "bag_mode.lifecycle",
                Severity.WARN,
                "bag_mode.status_unavailable",
                f"bag-mode status could not be read: {error}",
                action="Run bag-mode status --json and resolve the failure.",
            ),
        ]

    if recovery_required or brightness_pending:
        lifecycle = Finding(
            "bag_mode.lifecycle",
            Severity.WARN,
            "bag_mode.recovery_pending",
            "bag-mode has unrestored captured settings",
            action="Run bag-mode recover.",
        )
    elif enabled and phase != "running":
        lifecycle = Finding(
            "bag_mode.lifecycle",
            Severity.WARN,
            "bag_mode.stalled",
            f"bag-mode is enabled but its controller phase is {phase}",
            action="Inspect bag-mode logs, then run bag-mode status.",
        )
    elif enabled:
        lifecycle = Finding(
            "bag_mode.lifecycle",
            Severity.OK,
            "bag_mode.running",
            "bag-mode is enabled and its controller is running",
        )
    else:
        lifecycle = Finding(
            "bag_mode.lifecycle",
            Severity.OK,
            "bag_mode.stopped",
            "bag-mode is stopped; the Mac sleeps normally when the lid closes",
        )
    findings = [lifecycle]

    repo_version = _module_source_constant(
        repo_root / "modules/bag-mode/bag-mode",
        "VERSION",
    )
    if repo_version:
        version_error = ""
        try:
            completed = subprocess.run(
                [str(executable), "version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            reported = completed.stdout.strip()
            if completed.returncode != 0:
                detail = completed.stderr.strip() or completed.stdout.strip()
                version_error = f"command exited {completed.returncode}"
                if detail:
                    version_error += f": {detail}"
                reported = ""
        except (OSError, subprocess.TimeoutExpired) as error:
            reported = ""
            version_error = str(error)
        installed_version = reported.removeprefix("bag-mode ").strip()
        drifted = installed_version != repo_version
        findings.append(
            Finding(
                "bag_mode.version",
                Severity.WARN if drifted or version_error else Severity.OK,
                (
                    "bag_mode.version_unavailable"
                    if version_error
                    else (
                        "bag_mode.version_drift"
                        if drifted
                        else "bag_mode.version_current"
                    )
                ),
                (
                    f"could not read installed bag-mode version: {version_error}"
                    if version_error
                    else (
                        f"installed bag-mode {installed_version or 'unknown'} differs "
                        f"from repository version {repo_version}"
                        if drifted
                        else f"installed bag-mode matches repository version {repo_version}"
                    )
                ),
                action=(
                    "Run bag-mode version, then inspect or upgrade the installation."
                    if version_error
                    else ("Run modules/bag-mode/bag-mode upgrade." if drifted else None)
                ),
            ),
        )
    return findings


def _limit_satisfied(actual: str, expected: str) -> bool:
    """Return whether a launchd limit meets or exceeds its target."""
    if actual == expected or actual == "unlimited":
        return True
    try:
        return int(actual) >= int(expected)
    except ValueError:
        return False


def _maxfiles_findings(
    executable_finder: ExecutableFinder,
    repo_root: Path,
) -> list[Finding]:
    executable = executable_finder("macos-maxfiles")
    if executable is None:
        return [
            Finding(
                "maxfiles.agent",
                Severity.WARN,
                "maxfiles.missing",
                "macos-maxfiles is not installed",
                action="Run modules/macos-maxfiles/macos-maxfiles install.",
            ),
        ]
    try:
        completed = subprocess.run(
            [str(executable), "status", "--json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        record = json.loads(completed.stdout)
        installed = bool(record["installed"])
        loaded = bool(record["loaded"])
        soft_limit = str(record.get("soft_limit") or "")
        hard_limit = str(record.get("hard_limit") or "")
    except (
        OSError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        LookupError,
        TypeError,
        ValueError,
    ) as error:
        return [
            Finding(
                "maxfiles.agent",
                Severity.WARN,
                "maxfiles.status_unavailable",
                f"macos-maxfiles status could not be read: {error}",
                action="Run macos-maxfiles status --json and resolve the failure.",
            ),
        ]

    agent_ready = installed and loaded
    if completed.returncode != 0 and agent_ready:
        return [
            Finding(
                "maxfiles.agent",
                Severity.WARN,
                "maxfiles.status_unavailable",
                f"macos-maxfiles status contradicted exit {completed.returncode}",
                action="Run macos-maxfiles status --json and resolve the failure.",
            )
        ]
    findings = [
        Finding(
            "maxfiles.agent",
            Severity.OK if agent_ready else Severity.WARN,
            "maxfiles.agent_ready" if agent_ready else "maxfiles.agent_down",
            "maxfiles LaunchDaemon is installed and loaded"
            if agent_ready
            else "maxfiles LaunchDaemon is not loaded",
            action=(
                None
                if agent_ready
                else "Run modules/macos-maxfiles/macos-maxfiles install."
            ),
        ),
    ]
    source = repo_root / "modules/macos-maxfiles/macos-maxfiles"
    expected_soft = _module_source_constant(source, "SOFT_LIMIT")
    expected_hard = _module_source_constant(source, "HARD_LIMIT")
    if agent_ready and expected_soft and expected_hard:
        matches = _limit_satisfied(soft_limit, expected_soft) and _limit_satisfied(
            hard_limit, expected_hard
        )
        findings.append(
            Finding(
                "maxfiles.limits",
                Severity.OK if matches else Severity.WARN,
                "maxfiles.limits_effective" if matches else "maxfiles.limits_drift",
                (
                    f"effective maxfiles limits {soft_limit}/{hard_limit} satisfy "
                    f"the configured {expected_soft}/{expected_hard}"
                    if matches
                    else (
                        f"effective maxfiles limits {soft_limit or 'unknown'}/"
                        f"{hard_limit or 'unknown'} fall below the configured "
                        f"{expected_soft}/{expected_hard}"
                    )
                ),
                action=(
                    None
                    if matches
                    else "Run modules/macos-maxfiles/macos-maxfiles install to reapply the limit."
                ),
            ),
        )
    return findings
