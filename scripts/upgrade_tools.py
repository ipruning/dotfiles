"""Explicitly advance the shared mise baseline; ordinary host updates only consume the lock."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from .host_policy import HostPolicyError, mutation_allowed, require_mutation_allowed
from .mise import (
    canonical_mise_environment,
    canonical_mise_executable,
    canonical_mise_path,
)
from .models import Status
from .update import (
    UpdateReport,
    UpdateResult,
    UpdateStep,
    inspect_shared_mise_tools,
    run_with_progress,
    update_document,
)


def plan_upgrade_tools(repo_root: Path, home: Path) -> UpdateReport:
    """Advance only the shared declaration this checkout owns; ignore other project versions."""
    executable = canonical_mise_executable(home)
    step = UpdateStep(
        "mise.baseline",
        "mise",
        (
            str(canonical_mise_path(home)),
            "upgrade",
            "--bump",
            "--no-prune",
            "-C",
            str(home),
        ),
        1800,
        path_prepend=(canonical_mise_path(home).parent,),
        cwd=home,
    )
    if executable is None:
        return UpdateReport(
            False,
            (
                UpdateResult(
                    step,
                    Status.SKIPPED,
                    reason=f"{canonical_mise_path(home)} is missing, broken, or not executable",
                ),
            ),
        )
    try:
        installed, declaration = inspect_shared_mise_tools(repo_root, home, executable)
        source = repo_root / "reference/.config/mise/config.toml"
        if not (home / ".config/mise/config.toml").samefile(source):
            raise ValueError(
                "live global mise config must link to this checkout; preview mise-sync"
            )
        selectors = []
        for name in installed:
            request = declaration[name]
            version = request.get("version") if isinstance(request, dict) else request
            # Exact pins and refs are deliberate holds; `--bump` would rewrite them.
            if version == "latest":
                selectors.append(f"{name}@latest")
    except (OSError, ValueError, RuntimeError) as error:
        return UpdateReport(
            False,
            (
                UpdateResult(
                    step,
                    Status.FAILED if mutation_allowed(home) else Status.SKIPPED,
                    reason=str(error),
                ),
            ),
        )
    if not selectors:
        return UpdateReport(
            False,
            (
                UpdateResult(
                    step,
                    Status.SKIPPED,
                    reason="no rolling shared tools are installed",
                ),
            ),
        )
    step = replace(step, command=(*step.command, *selectors))
    return UpdateReport(False, (UpdateResult(step, Status.PLANNED),))


def execute_upgrade_tools(repo_root: Path, home: Path) -> UpdateReport:
    require_mutation_allowed(home)
    plan = plan_upgrade_tools(repo_root, home)
    results = []
    for planned in plan.results:
        if planned.status is not Status.PLANNED:
            results.append(planned)
            continue
        try:
            completed = run_with_progress(
                planned.step,
                env=canonical_mise_environment(home),
                progress_interval_seconds=30,
            )
            results.append(
                UpdateResult(
                    planned.step,
                    Status.SUCCEEDED if completed.returncode == 0 else Status.FAILED,
                    exit_code=completed.returncode,
                    reason=None
                    if completed.returncode == 0
                    else f"command exited {completed.returncode}",
                    stdout_tail=completed.stdout or None,
                    stderr_tail=completed.stderr or None,
                )
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            results.append(replace(planned, status=Status.FAILED, reason=str(error)))
    return UpdateReport(True, tuple(results))


def main(argv: list[str] | None = None) -> int:
    from .render import emit_error

    parser = argparse.ArgumentParser(
        description="Preview or advance the shared mise baseline and its lock."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="advance installed shared tool versions (default: preview only)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit the report as JSON on stdout",
    )
    args = parser.parse_args(argv)
    home = Path.home()
    root = Path(__file__).resolve().parents[1]
    try:
        allowed = mutation_allowed(home)
        report = (
            execute_upgrade_tools(root, home)
            if args.apply
            else plan_upgrade_tools(root, home)
        )
    except HostPolicyError as error:
        emit_error(
            "upgrade-tools",
            str(error),
            as_json=args.as_json,
            apply=args.apply,
            code=error.code,
        )
        return 1
    document = update_document(report, apply_allowed=allowed)
    document["operation"] = "upgrade-tools"
    document["notes"] = [
        "Advance the shared baseline only on the maintenance host. Run mise run verify, review the config, lock, and locked platform artifacts, and commit; other hosts then install it with mise run update."
    ]
    document["next"] = (
        ["mise run verify", "git diff -- reference/.config/mise"]
        if args.apply
        else (["mise run upgrade-tools -- --apply"] if allowed and report.ok else [])
    )
    if args.as_json:
        print(json.dumps(document, indent=2, sort_keys=True))
    else:
        for result in report.results:
            print(
                f"{result.status.value.upper()} {result.step.name}: {' '.join(result.step.command)}"
            )
            if result.reason:
                print(
                    result.reason,
                    file=sys.stderr if result.status is Status.FAILED else sys.stdout,
                )
        print(document["notes"][0])
        for command in document["next"]:
            print(command)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
