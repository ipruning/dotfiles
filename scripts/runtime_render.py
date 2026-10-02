"""JSON and operator handoffs for runtime refresh reports."""

from __future__ import annotations

import shlex
import sys

from .runtime_models import RuntimeAction, RuntimeReport, RuntimeSpec, RuntimeStatus


def _summary(report: RuntimeReport) -> dict[str, int]:
    return {
        status.value: count
        for status in (
            RuntimeStatus.PLANNED,
            RuntimeStatus.SUCCEEDED,
            RuntimeStatus.SKIPPED,
            RuntimeStatus.FAILED,
        )
        if (count := sum(result.status is status for result in report.results))
    }


def _document(
    report: RuntimeReport,
    *,
    apply_allowed: bool = True,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "operation": "runtime",
        "apply": report.apply,
        "ok": report.ok,
        "next": list(_next_commands(report, apply_allowed=apply_allowed)),
        "shell_restart_required": _shell_restart_required(report),
        "steps": [
            {
                "name": result.spec.name,
                "action": result.action.value,
                "status": result.status.value,
                "tool": result.spec.tool,
                "target": str(result.spec.target) if result.spec.target else None,
                "command": list(result.spec.command),
                "source": result.spec.source,
                "revision": result.spec.revision,
                "sha256": result.spec.sha256,
                "reason": result.reason,
                "exit_code": result.exit_code,
            }
            for result in report.results
        ],
        "summary": _summary(report),
    }


def _next_commands(
    report: RuntimeReport,
    *,
    apply_allowed: bool = True,
) -> tuple[str, ...]:
    if not report.apply:
        if (
            not apply_allowed
            or not report.ok
            or not any(
                result.status is RuntimeStatus.PLANNED for result in report.results
            )
        ):
            return ()
        arguments = ["mise", "run", "runtime", "--"]
        if report.generated_root is not None:
            arguments.extend(("--repo-root", str(report.generated_root.parent)))
        if not report.network:
            arguments.append("--offline")
        arguments.append("--apply")
        return (shlex.join(arguments),)
    if not report.ok:
        return ()
    if any(result.status is RuntimeStatus.SUCCEEDED for result in report.results):
        return ("mise run check", "mise run diff")
    return ()


def _shell_restart_required(report: RuntimeReport) -> bool:
    return any(
        result.status is RuntimeStatus.SUCCEEDED
        and (
            result.spec.name.startswith(("function.", "completion.", "plugin."))
            or result.spec.name == "zsh.compdump"
        )
        for result in report.results
    )


def _step_detail(spec: RuntimeSpec, action: RuntimeAction) -> str:
    command = shlex.join(spec.command) if spec.command else ""
    revision = f" [revision={spec.revision}]" if spec.revision else ""
    if action is RuntimeAction.GENERATE:
        return f"{command} -> {spec.target}"
    if command:
        return f"{command}{revision}"
    if action is RuntimeAction.DOWNLOAD:
        return f"download {spec.source} -> {spec.target}"
    if action is RuntimeAction.REMOVE:
        return f"remove {spec.target}"
    return str(spec.target or action)


def _render(report: RuntimeReport, *, apply_allowed: bool = True) -> None:
    for result in report.results:
        if result.status is RuntimeStatus.FAILED:
            print(
                f"[{result.spec.name}] FAIL {result.reason}",
                file=sys.stderr,
            )
            continue
        detail = (
            _step_detail(result.spec, result.action)
            if result.status in {RuntimeStatus.PLANNED, RuntimeStatus.SKIPPED}
            else result.action.value
        )
        print(f"{result.status.value.upper():7} {result.spec.name}: {detail}")
        if result.reason:
            print(f"        {result.reason}")
    summary = _summary(report)
    rendered = ", ".join(f"{count} {status}" for status, count in summary.items())
    print(f"Summary: {rendered or 'no steps'}")
    if not report.apply:
        next_commands = _next_commands(report, apply_allowed=apply_allowed)
        if not report.ok:
            print("No files changed. Resolve preview failures before applying.")
        elif next_commands:
            print("No files changed. Re-run with --apply to refresh the runtime.")
            print("Next:")
            for command in next_commands:
                print(f"  {command}")
        elif not apply_allowed:
            print("No files changed. Host policy disables runtime apply.")
        else:
            print("No runtime refresh steps are available on this host.")
        return
    if _shell_restart_required(report):
        print("Refreshed shell runtime is not active in existing shells.")
        print(
            "Restart the affected shell; for Zsh, open a new shell or run `exec zsh`."
        )
    if not report.ok:
        return
    if _next_commands(report):
        print("Next:")
        for command in _next_commands(report):
            print(f"  {command}")


def _announce_step(spec: RuntimeSpec, action: RuntimeAction) -> None:
    print(f"RUN {spec.name}: {_step_detail(spec, action)}", flush=True)
