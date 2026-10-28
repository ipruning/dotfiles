from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts import upgrade_all


@pytest.mark.parametrize("apply", [False, True])
def test_upgrade_all_only_verifies_after_apply(
    monkeypatch: pytest.MonkeyPatch, apply: bool
) -> None:
    baseline = Mock(return_value=0)
    host = Mock(return_value=0)
    run = Mock(return_value=Mock(returncode=7))
    monkeypatch.setattr(upgrade_all.upgrade_tools, "main", baseline)
    monkeypatch.setattr(upgrade_all.update, "main", host)
    monkeypatch.setattr(upgrade_all.subprocess, "run", run)
    monkeypatch.setattr(
        upgrade_all, "canonical_mise_executable", lambda home: "/canonical/mise"
    )

    assert upgrade_all.main(["--apply"] if apply else []) == (7 if apply else 0)

    arguments = ["--apply"] if apply else []
    baseline.assert_called_once_with(arguments)
    host.assert_called_once_with(arguments)
    if apply:
        run.assert_called_once_with(
            ["/canonical/mise", "run", "verify"],
            cwd=Path(upgrade_all.__file__).resolve().parents[1],
            check=False,
        )
    else:
        run.assert_not_called()


def test_upgrade_all_stops_after_baseline_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = Mock()
    run = Mock()
    monkeypatch.setattr(upgrade_all.upgrade_tools, "main", Mock(return_value=1))
    monkeypatch.setattr(upgrade_all.update, "main", host)
    monkeypatch.setattr(upgrade_all.subprocess, "run", run)

    assert upgrade_all.main(["--apply"]) == 1

    host.assert_not_called()
    run.assert_not_called()
