import json
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts.adopt import AdoptReport, apply_adopt
from scripts.check import inspect_host
from scripts.host_policy import (
    HostPolicyError,
    HostPolicyMutationError,
    load_host_policy,
)
from scripts.inventory import InventoryReport, execute_inventory
from scripts.mise import canonical_mise_executable, canonical_mise_path
from scripts.mise_sync import execute_mise_sync
from scripts.models import Severity
from scripts.restore import RestoreReport, apply_restore
from scripts.runtime import RuntimeReport, execute_runtime
from scripts.setup import apply_setup
from scripts.update import execute_updates
from tests.conftest import run_scripts_module


def _write_policy(home: Path, content: str) -> Path:
    policy = home / ".config/dotfiles/policy.toml"
    policy.parent.mkdir(parents=True)
    policy.write_text(content)
    return policy


def _write_mise(home: Path) -> Path:
    executable = home / ".local/bin/mise"
    executable.parent.mkdir(parents=True)
    executable.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "config" ] && [ "$2" = "ls" ]; then\n'
        "  printf '[]\\n'\n"
        'elif [ "$1" = "ls" ]; then\n'
        "  printf '{}\\n'\n"
        "fi\n",
    )
    executable.chmod(0o755)
    return executable


def _apply_arguments(module: str, tmp_path: Path) -> tuple[str, ...]:
    if module == "setup":
        return "--profile", "linux-lite"
    if module in {"restore", "adopt"}:
        return ("hushlogin",)
    if module == "runtime":
        return "--offline", "--repo-root", str(tmp_path / "runtime-repo")
    if module == "inventory":
        return (
            "--repo-root",
            str(tmp_path / "inventory-repo"),
            "--host",
            "TestHost",
        )
    return ()


@pytest.mark.parametrize(
    ("policy", "expected_code"),
    [
        (
            'mode = "audit-only"\nmise_path = "/usr/bin/mise"\n',
            "host_policy.audit_only",
        ),
        ('mod = "audit-only"\n', "host_policy.invalid"),
    ],
)
@pytest.mark.parametrize(
    ("module", "operation"),
    [
        ("setup", "setup"),
        ("mise_sync", "mise-sync"),
        ("restore", "restore"),
        ("update", "update"),
        ("adopt", "adopt"),
        ("runtime", "runtime"),
        ("inventory", "inventory"),
    ],
)
def test_host_policy_refuses_every_cli_mutation_before_planning(
    tmp_path: Path,
    policy: str,
    expected_code: str,
    module: str,
    operation: str,
) -> None:
    home = tmp_path / "home"
    _write_policy(home, policy)

    completed = run_scripts_module(
        module,
        home,
        *_apply_arguments(module, tmp_path),
        "--apply",
        "--json",
    )

    assert completed.returncode == 1
    document = json.loads(completed.stdout)
    assert document["operation"] == operation
    assert document["apply"] is True
    assert document["ok"] is False
    assert document["error"]["code"] == expected_code
    assert "Traceback" not in completed.stderr
    assert not (tmp_path / "runtime-repo").exists()
    assert not (tmp_path / "inventory-repo").exists()


@pytest.mark.parametrize(
    "module",
    ["setup", "mise_sync", "restore", "update", "adopt", "runtime", "inventory"],
)
def test_audit_only_policy_keeps_cli_previews_available(
    tmp_path: Path,
    module: str,
) -> None:
    home = tmp_path / "home"
    mise = _write_mise(home)
    _write_policy(
        home,
        f'mode = "audit-only"\nmise_path = "{mise}"\n',
    )

    completed = run_scripts_module(
        module,
        home,
        *_apply_arguments(module, tmp_path),
        "--json",
    )

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    assert document["apply"] is False
    assert document["next"] == []


def test_audit_only_mise_preview_observes_live_only_tools_without_failing(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    mise = _write_mise(home)
    config = home / ".config/mise/config.toml"
    config.parent.mkdir(parents=True)
    config.write_text('[tools]\nhost-only = "latest"\n')
    _write_policy(
        home,
        f'mode = "audit-only"\nmise_path = "{mise}"\n',
    )

    completed = run_scripts_module("mise_sync", home, "--json")

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    assert document["ok"] is True
    assert document["safety"]["apply_blocked"] is True
    assert document["safety"]["live_only_tools"] == ["host-only"]
    assert document["next"] == []
    assert "FAIL live-only global tools" not in completed.stderr


def test_audit_only_policy_guards_direct_mutation_apis(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    _write_policy(home, 'mode = "audit-only"\n')
    calls: tuple[Callable[[], object], ...] = (
        lambda: apply_setup(repo_root, home),
        lambda: execute_mise_sync(repo_root, home),
        lambda: apply_restore(repo_root, home, RestoreReport("example", False, ())),
        lambda: apply_adopt(repo_root, home, AdoptReport("example", False, ())),
        lambda: execute_updates(home, executable_finder=lambda _tool: None),
        lambda: execute_runtime(RuntimeReport(False, ()), home),
        lambda: execute_inventory(InventoryReport("host", False, ()), home),
    )

    for mutation in calls:
        with pytest.raises(HostPolicyMutationError):
            mutation()


def test_valid_policy_selects_mise_and_is_visible_to_check(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    installed_mise = tmp_path / "homebrew/Cellar/mise/2026.8.5/bin/mise"
    installed_mise.parent.mkdir(parents=True)
    installed_mise.write_text("#!/bin/sh\nexit 0\n")
    installed_mise.chmod(0o755)
    mise = tmp_path / "homebrew/bin/mise"
    mise.parent.mkdir(parents=True)
    mise.symlink_to(Path("../Cellar/mise/2026.8.5/bin/mise"))
    stale_mise = tmp_path / "old/bin/mise"
    stale_mise.parent.mkdir(parents=True)
    stale_mise.write_text("#!/bin/sh\nexit 0\n")
    stale_mise.chmod(0o755)
    stale_shim = home / ".local/share/mise/shims/example"
    stale_shim.parent.mkdir(parents=True)
    stale_shim.symlink_to(stale_mise)
    policy = _write_policy(
        home,
        f'mode = "audit-only"\nmise_path = "{mise}"\n',
    )

    report = inspect_host(
        repo_root,
        home,
        executable_finder=lambda command: (
            str(mise) if command == "mise" else f"/tools/{command}"
        ),
        system_name="Linux",
        profile="linux-lite",
    )
    findings = {finding.check: finding for finding in report.findings}

    assert canonical_mise_path(home) == mise
    assert canonical_mise_executable(home) == str(mise)
    assert findings["host.policy"].code == "host.policy_audit_only"
    assert findings["host.policy"].path == policy
    assert findings["mise.canonical"].path == mise
    assert (
        findings["mise.canonical"].message
        == "The host-selected Mise executable is ready"
    )
    assert findings["mise.installations"].code == "mise.installations_single"
    assert findings["mise.shims"].severity is Severity.WARN
    assert findings["mise.shims"].action == (
        "Rebuild the shims with the host owner that selected the canonical Mise executable."
    )
    assert findings["shell.bash"].severity is None
    assert findings["shell.bash"].applicable is False
    assert findings["shell.bash"].action is None
    for command in ("starship", "herdr", "atuin", "zoxide", "hunk", "lazygit"):
        finding = findings[f"executable.{command}"]
        assert finding.severity is None
        assert finding.action is None
    assert findings["executable.skillshare"].applicable is True


def test_canonical_mise_rejects_broken_package_manager_symlink(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    mise = tmp_path / "homebrew/bin/mise"
    mise.parent.mkdir(parents=True)
    mise.symlink_to(Path("../Cellar/mise/missing/bin/mise"))
    _write_policy(
        home,
        f'mode = "audit-only"\nmise_path = "{mise}"\n',
    )

    assert canonical_mise_path(home) == mise
    assert canonical_mise_executable(home) is None


def test_audit_only_full_check_skips_repository_runtime_readiness(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    mise = _write_mise(home)
    _write_policy(home, f'mode = "audit-only"\nmise_path = "{mise}"\n')

    def finder(command: str) -> str | None:
        if command == "mise":
            return str(mise)
        if command in {"skillshare", "btop"}:
            return None
        return f"/tools/{command}"

    report = inspect_host(
        repo_root,
        home,
        executable_finder=finder,
        system_name="Linux",
        profile="full",
    )
    findings = {finding.check: finding for finding in report.findings}

    for check in (
        "shell.plugins",
        "shell.completions",
        "shell.functions",
        "runtime.function.mise",
        "runtime.plugin.fzf-tab",
        "zellij.zjstatus.wasm",
    ):
        assert findings[check].applicable is False
        assert findings[check].action is None
    assert findings["executable.skillshare"].severity is Severity.WARN
    assert findings["executable.btop"].severity is Severity.WARN


def test_invalid_policy_is_diagnosed_without_mise_owner_fallback(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    home = tmp_path / "home"
    _write_policy(home, 'mode = "audit-only"\nmisel_path = "/usr/bin/mise"\n')

    report = inspect_host(
        repo_root,
        home,
        executable_finder=lambda command: f"/tools/{command}",
        system_name="Linux",
        profile="linux-lite",
    )
    findings = {finding.check: finding for finding in report.findings}

    assert findings["host.policy"].code == "host.policy_invalid"
    assert "mise.canonical" not in findings
    assert report.is_ok() is False
    with pytest.raises(HostPolicyError, match="unknown fields"):
        canonical_mise_path(home)


def test_absent_policy_preserves_managed_defaults(tmp_path: Path) -> None:
    home = tmp_path / "home"

    assert load_host_policy(home).mode == "managed"
    assert canonical_mise_path(home) == home / ".local/bin/mise"
    report = inspect_host(
        tmp_path / "repo",
        home,
        executable_finder=lambda command: f"/tools/{command}",
        system_name="Linux",
        profile="linux-lite",
    )
    assert all(finding.check != "host.policy" for finding in report.findings)
