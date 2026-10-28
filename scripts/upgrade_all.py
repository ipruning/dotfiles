"""Compose the baseline and host upgrades with the repository verification gate."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from . import update, upgrade_tools
from .mise import canonical_mise_executable


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="upgrade and verify")
    args = parser.parse_args(argv)
    arguments = ["--apply"] if args.apply else []
    for operation in (upgrade_tools.main, update.main):
        result = operation(arguments)
        if result:
            return result
    if not args.apply:
        print("Preview only. Re-run with -- --apply to upgrade and verify.")
        return 0
    mise = canonical_mise_executable(Path.home())
    if mise is None:
        print(
            "Canonical mise executable is unavailable for verification", file=sys.stderr
        )
        return 1
    return subprocess.run(
        [mise, "run", "verify"],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
