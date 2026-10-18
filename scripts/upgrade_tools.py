"""Explicitly advance shared baselines (mise tools, Yazi plugins); `update` only installs them."""

from __future__ import annotations

import argparse
import json
import shutil
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
from .models import ExecutableFinder, Status
from .update import (
    UpdateReport,
    UpdateResult,
    UpdateStep,
    inspect_shared_mise_tools,
    run_with_progress,
    update_document,
)


def plan_upgrade_tools(
    repo_root: Path,
    home: Path,
    *,
    executable_finder: ExecutableFinder = shutil.which,
) -> UpdateReport:
    """Advance the shared baselines this checkout owns: mise tools and Yazi plugins."""
    return UpdateReport(
        False,
        (
            _mise_baseline(repo_root, home),
            _yazi_packages(repo_root, home, executable_finder),
        ),
    )


def _yazi_packages(
    repo_root: Path, home: Path, executable_finder: ExecutableFinder
) -> UpdateResult:
    # `ya pkg upgrade` rewrites package.toml revisions; `update` only runs
    # `ya pkg install`, which deploys the revisions committed here.
    step = UpdateStep("yazi.packages", "ya", ("ya", "pkg", "upgrade"), 300, cwd=home)
    executable = executable_finder("ya")
    if executable is None:
        return UpdateResult(step, Status.SKIPPED, reason="ya is not available on PATH")
    live = home / ".config/yazi/package.toml"
    reference = repo_root / "reference/.config/yazi/package.toml"
    try:
        linked = live.samefile(reference)
    except OSError:
        linked = False
    if not linked:
        return UpdateResult(
            step,
            Status.SKIPPED,
            reason=f"{live} does not link to this checkout; preview mise run restore -- yazi",
        )
    return UpdateResult(
        replace(step, command=(executable, *step.command[1:])), Status.PLANNED
    )


def _mise_baseline(repo_root: Path, home: Path) -> UpdateResult:
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
        return UpdateResult(
            step,
            Status.SKIPPED,
            reason=f"{canonical_mise_path(home)} is missing, broken, or not executable",
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
        return UpdateResult(
            step,
            Status.FAILED if mutation_allowed(home) else Status.SKIPPED,
            reason=str(error),
        )
    if not selectors:
        return UpdateResult(
            step, Status.SKIPPED, reason="no rolling shared tools are installed"
        )
    return UpdateResult(
        replace(step, command=(*step.command, *selectors)), Status.PLANNED
    )


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
        description="Preview or advance the shared mise tool baseline and Yazi plugin revisions."
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
        "Advance shared baselines only on the maintenance host. Run mise run verify, review the mise config, lock, locked platform artifacts, and Yazi package.toml, and commit; other hosts then install them with mise run update."
    ]
    document["next"] = (
        [
            "mise run verify",
            "git diff -- reference/.config/mise reference/.config/yazi/package.toml",
        ]
        if args.apply
        else (["mise run upgrade-tools -- --apply"] if allowed and report.ok else [])
    )
    if args.as_json:
        print(json.dumps(document, indent=2, sort_keys=True))
    else:
        for result in report.results:
            print(
                f"{result.status.value.upper():9} {result.step.name}: {' '.join(result.step.command)}"
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
