"""JSON and operator handoffs for generate reports."""

from __future__ import annotations

import shlex
import sys

from .generate_models import GenerateAction, GenerateReport, GenerateSpec
from .models import Status, status_summary


def _summary(report: GenerateReport) -> dict[str, int]:
    return status_summary(result.status for result in report.results)


def generate_document(
    report: GenerateReport,
    *,
    apply_allowed: bool = True,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "operation": "generate",
        "apply": report.apply,
        "ok": report.ok,
        "next": list(generate_next_commands(report, apply_allowed=apply_allowed)),
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


def generate_next_commands(
    report: GenerateReport,
    *,
    apply_allowed: bool = True,
) -> tuple[str, ...]:
    if not report.apply:
        if (
            not apply_allowed
            or not report.ok
            or not any(result.status is Status.PLANNED for result in report.results)
        ):
            return ()
        arguments = ["mise", "run", "generate", "--"]
        if report.generated_root is not None:
            arguments.extend(("--repo-root", str(report.generated_root.parent)))
        if not report.network:
            arguments.append("--offline")
        arguments.append("--apply")
        return (shlex.join(arguments),)
    if not report.ok:
        return ()
    if any(result.status is Status.SUCCEEDED for result in report.results):
        return ("mise run check", "mise run diff")
    return ()


def _shell_restart_required(report: GenerateReport) -> bool:
    return any(
        result.status is Status.SUCCEEDED
        and (
            result.spec.name.startswith(("function.", "completion.", "plugin."))
            or result.spec.name == "zsh.compdump"
        )
        for result in report.results
    )


def _step_detail(spec: GenerateSpec, action: GenerateAction) -> str:
    command = shlex.join(spec.command) if spec.command else ""
    revision = f" [revision={spec.revision}]" if spec.revision else ""
    if action is GenerateAction.GENERATE:
        return f"{command} -> {spec.target}"
    if command:
        return f"{command}{revision}"
    if action is GenerateAction.DOWNLOAD:
        return f"download {spec.source} -> {spec.target}"
    if action is GenerateAction.REMOVE:
        return f"remove {spec.target}"
    return str(spec.target or action)


def render_generate(report: GenerateReport, *, apply_allowed: bool = True) -> None:
    for result in report.results:
        if result.status is Status.FAILED:
            print(
                f"[{result.spec.name}] FAIL {result.reason}",
                file=sys.stderr,
            )
            continue
        detail = (
            _step_detail(result.spec, result.action)
            if result.status in {Status.PLANNED, Status.SKIPPED}
            else result.action.value
        )
        print(f"{result.status.value.upper():7} {result.spec.name}: {detail}")
        if result.reason:
            print(f"        {result.reason}")
    summary = _summary(report)
    rendered = ", ".join(f"{count} {status}" for status, count in summary.items())
    print(f"Summary: {rendered or 'no steps'}")
    if not report.apply:
        next_commands = generate_next_commands(report, apply_allowed=apply_allowed)
        if not report.ok:
            print("No files changed. Resolve preview failures before applying.")
        elif next_commands:
            print("No files changed. Re-run with --apply to regenerate generated/.")
            print("Next:")
            for command in next_commands:
                print(f"  {command}")
        elif not apply_allowed:
            print("No files changed. Host policy disables generate apply.")
        else:
            print("No generate steps are available on this host.")
        return
    if _shell_restart_required(report):
        print("Regenerated shell integrations are not active in existing shells.")
        print(
            "Restart the affected shell; for Zsh, open a new shell or run `exec zsh`."
        )
    if not report.ok:
        return
    if generate_next_commands(report):
        print("Next:")
        for command in generate_next_commands(report):
            print(f"  {command}")


def announce_generate_step(spec: GenerateSpec, action: GenerateAction) -> None:
    print(f"RUN {spec.name}: {_step_detail(spec, action)}", flush=True)
