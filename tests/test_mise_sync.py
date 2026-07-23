import json
import os
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT, run_scripts_module


def _write_mise(home: Path, log_path: Path, *, install_exit: int = 0) -> Path:
    executable = home / ".local/bin/mise"
    executable.parent.mkdir(parents=True)
    config_listing = executable.parent / "mise-configs.json"
    config_listing.write_text(
        json.dumps(
            [
                {
                    "path": str(home / ".config/mise/config.toml"),
                    "tools": [],
                }
            ]
        )
    )
    executable.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "config" ] && [ "$2" = "ls" ]; then\n'
        f"  cat {config_listing}\n"
        "  exit 0\n"
        "fi\n"
        f'printf \'%s|%s\\n\' "$*" "$PATH" >> {log_path}\n'
        'if [ "$1" = "install" ]; then\n'
        f"  exit {install_exit}\n"
        "fi\n"
        "exit 0\n",
    )
    executable.chmod(0o755)
    return executable


def _set_loaded_configs(executable: Path, config_paths: list[Path]) -> None:
    (executable.parent / "mise-configs.json").write_text(
        json.dumps(
            [{"path": str(config_path), "tools": []} for config_path in config_paths]
        )
    )


def _write_live_config(home: Path) -> None:
    config = home / ".config/mise"
    config.mkdir(parents=True)
    (config / "config.toml").write_text('[tools]\nnode = "20"\n')
    (config / "mise.lock").write_text("# host-specific lock\n")


def test_mise_sync_previews_configuration_tools_and_shims_without_writing(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _write_live_config(home)
    log_path = tmp_path / "mise.log"
    executable = _write_mise(home, log_path)

    completed = run_scripts_module("mise_sync", home, "--json")

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    assert document["schema_version"] == 1
    assert document["operation"] == "mise-sync"
    assert document["apply"] is False
    assert document["ok"] is True
    assert document["summary"] == {"planned": 4}
    assert [change["status"] for change in document["changes"]] == [
        "planned",
        "planned",
    ]
    assert [step["command"] for step in document["steps"]] == [
        [
            str(executable),
            "install",
            "--locked",
            "--yes",
            "-C",
            str(home),
        ],
        [str(executable), "reshim", "-C", str(home)],
    ]
    assert all(
        step["environment"]["PATH_prepend"] == [str(executable.parent)]
        for step in document["steps"]
    )
    assert document["next"] == ["mise run mise-sync -- --apply"]
    assert not log_path.exists()
    assert not (home / ".config/mise/config.toml").is_symlink()


def test_mise_sync_recognizes_the_primary_config_through_a_symlinked_home(
    tmp_path: Path,
) -> None:
    real_home = tmp_path / "real-home"
    real_home.mkdir()
    home = tmp_path / "home"
    home.symlink_to(real_home, target_is_directory=True)
    _write_live_config(home)
    executable = _write_mise(home, tmp_path / "mise.log")
    _set_loaded_configs(
        executable,
        [real_home / ".config/mise/config.toml"],
    )

    completed = run_scripts_module("mise_sync", home, "--json")

    assert completed.returncode == 0
    safety = json.loads(completed.stdout)["safety"]
    assert safety["apply_blocked"] is False
    assert safety["additional_global_configs"] == []


def test_mise_sync_blocks_live_only_tools_until_ownership_is_resolved(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _write_live_config(home)
    live_config = home / ".config/mise/config.toml"
    live_config.write_text('[tools]\nnode = "20"\n\n[tools.pueue]\nversion = "4.0.4"\n')
    log_path = tmp_path / "mise.log"
    _write_mise(home, log_path)

    preview = run_scripts_module("mise_sync", home, "--json")

    assert preview.returncode == 1
    preview_document = json.loads(preview.stdout)
    assert preview_document["ok"] is False
    assert preview_document["safety"] == {
        "apply_blocked": True,
        "additional_global_configs": [],
        "configuration_error": None,
        "live_alias_overrides": [],
        "live_only_tools": ["pueue"],
    }
    assert [step["status"] for step in preview_document["steps"]] == [
        "skipped",
        "skipped",
    ]
    assert "[mise.safety] FAIL live-only global tools: pueue" in preview.stderr

    applied = run_scripts_module("mise_sync", home, "--apply", "--json")

    assert applied.returncode == 1
    assert live_config.is_symlink() is False
    assert "[tools.pueue]" in live_config.read_text()
    assert not log_path.exists()

    live_config.write_text('[tools]\nnode = "20"\n')
    resolved = run_scripts_module("mise_sync", home, "--json")
    assert resolved.returncode == 0
    assert json.loads(resolved.stdout)["safety"]["apply_blocked"] is False


def test_mise_sync_blocks_an_additional_global_config_with_live_only_tools(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _write_live_config(home)
    local_config = home / ".config/mise/config.local.toml"
    local_config.write_text('[tools]\npueue = "4.0.4"\n')
    executable = _write_mise(home, tmp_path / "mise.log")
    _set_loaded_configs(
        executable,
        [home / ".config/mise/config.toml", local_config],
    )

    completed = run_scripts_module("mise_sync", home, "--json")

    assert completed.returncode == 1
    safety = json.loads(completed.stdout)["safety"]
    assert safety["apply_blocked"] is True
    assert safety["additional_global_configs"] == [str(local_config)]
    assert safety["live_only_tools"] == ["pueue"]


def test_mise_sync_blocks_an_additional_global_config_with_duplicate_tools(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _write_live_config(home)
    local_config = home / ".config/mise/config.local.toml"
    local_config.write_text('[tools]\nnode = "20"\n')
    executable = _write_mise(home, tmp_path / "mise.log")
    _set_loaded_configs(
        executable,
        [home / ".config/mise/config.toml", local_config],
    )

    completed = run_scripts_module("mise_sync", home, "--json")

    assert completed.returncode == 1
    safety = json.loads(completed.stdout)["safety"]
    assert safety["apply_blocked"] is True
    assert safety["additional_global_configs"] == [str(local_config)]
    assert safety["live_only_tools"] == []


@pytest.mark.parametrize(
    "additional_config",
    [Path(".mise.toml"), Path("/etc/mise/config.toml")],
)
def test_mise_sync_blocks_an_active_config_outside_the_standard_directory(
    tmp_path: Path,
    additional_config: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _write_live_config(home)
    config_path = (
        additional_config
        if additional_config.is_absolute()
        else home / additional_config
    )
    executable = _write_mise(home, tmp_path / "mise.log")
    _set_loaded_configs(
        executable,
        [home / ".config/mise/config.toml", config_path],
    )

    completed = run_scripts_module("mise_sync", home, "--json")

    assert completed.returncode == 1
    safety = json.loads(completed.stdout)["safety"]
    assert safety["apply_blocked"] is True
    assert safety["additional_global_configs"] == [str(config_path)]


def test_mise_sync_blocks_a_malformed_additional_global_config(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _write_live_config(home)
    local_config = home / ".config/mise/config.local.toml"
    local_config.write_text("[tools\n")
    executable = _write_mise(home, tmp_path / "mise.log")
    _set_loaded_configs(
        executable,
        [home / ".config/mise/config.toml", local_config],
    )

    completed = run_scripts_module("mise_sync", home, "--apply", "--json")

    assert completed.returncode == 1
    safety = json.loads(completed.stdout)["safety"]
    assert safety["apply_blocked"] is True
    assert "cannot be read as TOML" in safety["configuration_error"]
    assert not (home / ".config/mise/config.toml").is_symlink()


@pytest.mark.parametrize("alias_section", ["alias", "tool_alias"])
def test_mise_sync_accepts_a_tracked_backend_migration_alias(
    tmp_path: Path,
    alias_section: str,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _write_live_config(home)
    (home / ".config/mise/config.toml").write_text(
        f'[{alias_section}]\nyarn = "vfox:mise-plugins/vfox-yarn"\n\n'
        '[tools]\nnode = "20"\nyarn = "latest"\n'
    )
    _write_mise(home, tmp_path / "mise.log")

    preview = run_scripts_module("mise_sync", home, "--json")

    assert preview.returncode == 0
    document = json.loads(preview.stdout)
    assert document["safety"]["apply_blocked"] is False
    assert document["safety"]["live_alias_overrides"] == []
    assert document["safety"]["live_only_tools"] == []

    applied = run_scripts_module("mise_sync", home, "--apply", "--json")

    assert applied.returncode == 0
    assert json.loads(applied.stdout)["ok"] is True
    live_config = home / ".config/mise/config.toml"
    assert live_config.is_symlink()
    assert live_config.resolve() == REPO_ROOT / "reference/.config/mise/config.toml"


def test_mise_sync_normalizes_an_explicit_backend_to_its_tracked_alias(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _write_live_config(home)
    (home / ".config/mise/config.toml").write_text(
        '[tool_alias]\nuv = "aqua:astral-sh/uv"\n\n'
        '[tools]\n"aqua:astral-sh/uv" = "latest"\n'
    )
    _write_mise(home, tmp_path / "mise.log")

    completed = run_scripts_module("mise_sync", home, "--json")

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    assert document["safety"]["apply_blocked"] is False
    assert document["safety"]["live_only_tools"] == []


def test_mise_sync_accepts_a_previous_tracked_backend_without_its_new_alias(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _write_live_config(home)
    (home / ".config/mise/config.toml").write_text(
        '[tools]\n"aqua:yarnpkg/berry" = "latest"\n'
    )
    _write_mise(home, tmp_path / "mise.log")

    completed = run_scripts_module("mise_sync", home, "--json")

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    assert document["safety"]["apply_blocked"] is False
    assert document["safety"]["live_only_tools"] == []


@pytest.mark.parametrize(
    ("live_config", "live_only_tools", "alias", "backend"),
    [
        (
            '[tool_alias]\npueue = "aqua:yarnpkg/berry"\n\n[tools]\npueue = "latest"\n',
            ["pueue"],
            "pueue",
            "aqua:yarnpkg/berry",
        ),
        (
            '[tool_alias]\nnode = "aqua:evil/thing"\n\n'
            '[tools]\n"aqua:evil/thing" = "latest"\n',
            ["aqua:evil/thing"],
            "node",
            "aqua:evil/thing",
        ),
        (
            '[tool_alias]\nnode = "aqua:evil/thing"\n\n[tools]\nnode = "latest"\n',
            [],
            "node",
            "aqua:evil/thing",
        ),
        (
            '[alias]\nnode = "aqua:evil/thing"\n\n[tools]\nnode = "latest"\n',
            [],
            "node",
            "aqua:evil/thing",
        ),
        (
            '[tool_alias]\nnode = "aqua:evil/thing"\n\n'
            '[tools]\n"aqua:yarnpkg/berry" = "latest"\n',
            [],
            "node",
            "aqua:evil/thing",
        ),
        (
            '[tool_alias]\nnode = "aqua:yarnpkg/berry"\n\n[tools]\nnode = "latest"\n',
            [],
            "node",
            "aqua:yarnpkg/berry",
        ),
    ],
)
def test_mise_sync_does_not_trust_live_aliases_to_claim_tracked_ownership(
    tmp_path: Path,
    live_config: str,
    live_only_tools: list[str],
    alias: str,
    backend: str,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _write_live_config(home)
    (home / ".config/mise/config.toml").write_text(live_config)
    _write_mise(home, tmp_path / "mise.log")

    completed = run_scripts_module("mise_sync", home, "--json")

    assert completed.returncode == 1
    document = json.loads(completed.stdout)
    assert document["safety"]["apply_blocked"] is True
    assert document["safety"]["live_only_tools"] == live_only_tools
    assert document["safety"]["live_alias_overrides"] == [
        {"alias": alias, "backend": backend}
    ]


def test_mise_sync_gives_tool_alias_precedence_over_legacy_alias(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _write_live_config(home)
    (home / ".config/mise/config.toml").write_text(
        '[alias]\naube = "aqua:evil/thing"\n\n'
        '[tool_alias]\naube = "aqua:jdx/aube"\n\n'
        '[tools]\naube = "latest"\n'
    )
    _write_mise(home, tmp_path / "mise.log")

    completed = run_scripts_module("mise_sync", home, "--json")

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    assert document["safety"]["apply_blocked"] is False
    assert document["safety"]["live_alias_overrides"] == []
    assert document["safety"]["live_only_tools"] == []


def test_mise_sync_blocks_when_live_tool_ownership_cannot_be_parsed(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _write_live_config(home)
    live_config = home / ".config/mise/config.toml"
    live_config.write_text("[tools\n")
    log_path = tmp_path / "mise.log"
    _write_mise(home, log_path)

    completed = run_scripts_module("mise_sync", home, "--apply", "--json")

    assert completed.returncode == 1
    document = json.loads(completed.stdout)
    assert document["safety"]["apply_blocked"] is True
    assert "cannot be read as TOML" in document["safety"]["configuration_error"]
    assert live_config.read_text() == "[tools\n"
    assert not live_config.is_symlink()
    assert not log_path.exists()


def test_mise_sync_apply_links_shared_declaration_and_runs_locked_commands(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _write_live_config(home)
    log_path = tmp_path / "mise.log"
    executable = _write_mise(home, log_path)

    completed = run_scripts_module("mise_sync", home, "--apply", "--json")

    assert completed.returncode == 0
    document = json.loads(completed.stdout)
    assert document["apply"] is True
    assert document["ok"] is True
    assert document["summary"] == {"applied": 2, "succeeded": 2}
    config = home / ".config/mise/config.toml"
    lockfile = home / ".config/mise/mise.lock"
    assert config.is_symlink()
    assert config.resolve() == REPO_ROOT / "reference/.config/mise/config.toml"
    assert lockfile.is_symlink()
    assert lockfile.resolve() == REPO_ROOT / "reference/.config/mise/mise.lock"
    assert all(Path(change["backup_path"]).is_file() for change in document["changes"])
    invocations = log_path.read_text().splitlines()
    assert invocations[0].split("|", 1)[0] == (f"install --locked --yes -C {home}")
    assert invocations[1].split("|", 1)[0] == f"reshim -C {home}"
    assert all(
        line.split("|", 1)[1].split(os.pathsep)[0] == str(executable.parent)
        for line in invocations
    )
    assert document["next"] == ["mise run check", "mise run diff"]

    converged = run_scripts_module("mise_sync", home, "--apply", "--json")
    assert converged.returncode == 0
    converged_document = json.loads(converged.stdout)
    assert converged_document["changes"] == []
    assert converged_document["summary"] == {"succeeded": 2}


def test_mise_sync_fails_before_restore_without_canonical_mise(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _write_live_config(home)

    completed = run_scripts_module("mise_sync", home, "--apply", "--json")

    assert completed.returncode == 1
    document = json.loads(completed.stdout)
    assert document["ok"] is False
    assert document["apply"] is True
    assert document["steps"][0]["status"] == "failed"
    assert document["steps"][1]["status"] == "skipped"
    assert "missing, symlinked, or not executable" in document["steps"][0]["reason"]
    assert "[mise.tools] FAIL" in completed.stderr
    config = home / ".config/mise/config.toml"
    assert config.read_text() == '[tools]\nnode = "20"\n'
    assert not config.is_symlink()


def test_mise_sync_reports_install_failure_but_still_repairs_shims(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _write_live_config(home)
    log_path = tmp_path / "mise.log"
    _write_mise(home, log_path, install_exit=7)

    completed = run_scripts_module("mise_sync", home, "--apply", "--json")

    assert completed.returncode == 1
    document = json.loads(completed.stdout)
    assert document["ok"] is False
    assert [step["status"] for step in document["steps"]] == [
        "failed",
        "succeeded",
    ]
    assert [line.split("|", 1)[0] for line in log_path.read_text().splitlines()] == [
        f"install --locked --yes -C {home}",
        f"reshim -C {home}",
    ]
    assert "[mise.tools] FAIL command exited 7" in completed.stderr
