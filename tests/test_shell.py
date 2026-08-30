import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest

from scripts.models import Severity
from scripts.shell import ShellCheckError, check_shell_files, shell_dialect

requires_shellcheck = pytest.mark.skipif(
    shutil.which("shellcheck") is None,
    reason="shellcheck is not installed",
)
requires_zsh = pytest.mark.skipif(
    shutil.which("zsh") is None,
    reason="zsh is not installed",
)
requires_nu = pytest.mark.skipif(
    shutil.which("nu") is None,
    reason="nushell is not installed",
)


def _tracked_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo_root = tmp_path / "repo"
    for relative, content in files.items():
        file_path = repo_root / relative
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
    subprocess.run(["git", "init", "-q", str(repo_root)], check=True)
    subprocess.run(["git", "-C", str(repo_root), "add", "."], check=True)
    return repo_root


def test_shell_dialect_covers_extensions_shebangs_and_reference_data() -> None:
    assert shell_dialect("modules/bash/init.bash", "# sourced fragment") == "bash"
    assert shell_dialect("modules/bin/_lib/session-id.sh", "") == "bash"
    assert shell_dialect("modules/zsh/env.zsh", "") == "zsh"
    assert shell_dialect("modules/bin/g", "#!/usr/bin/env bash") == "bash"
    assert shell_dialect("modules/bin/ttok", "#!/usr/bin/env -S zsh -f") == "zsh"
    assert shell_dialect("modules/bin/watchdog", "#!/bin/sh") == "bash"
    assert shell_dialect("modules/bin/portable", "#!/usr/bin/env sh") == "bash"
    assert shell_dialect("modules/bin/dashy", "#!/bin/dash") == "bash"
    assert shell_dialect("modules/bin/pyenvish", "#!/usr/bin/env -S python3 -u") is None
    assert shell_dialect("scripts/diff.py", "#!/usr/bin/env python3") is None
    # Restored startup dotfiles are gated by name even under reference/...
    assert shell_dialect("reference/.zshrc", "autoload -Uz compinit") == "zsh"
    assert shell_dialect("reference/.zshenv", "# read by every zsh") == "zsh"
    assert shell_dialect("reference/.zprofile", "# login-shell only") == "zsh"
    assert shell_dialect("reference/.bashrc", "# bash startup") == "bash"
    # ...but the private template keeps its skip (it may hold placeholders).
    assert shell_dialect("reference/.zshenv.private.tpl.zsh", "") is None
    assert shell_dialect("notes.txt", "plain text") is None
    assert shell_dialect("modules/tool/tool", "#!/bin/sh", '""":"') is None


def test_check_shell_files_reports_bash_syntax_failures_then_passes(
    tmp_path: Path,
) -> None:
    repo_root = _tracked_repo(
        tmp_path,
        {
            "modules/bin/good": "#!/usr/bin/env bash\nprintf 'ok\\n'\n",
            "modules/bin/broken": "#!/usr/bin/env bash\nif true; then\n",
        },
    )
    quiet_shellcheck = tmp_path / "quiet-shellcheck"
    quiet_shellcheck.write_text("#!/bin/sh\nexit 0\n")
    quiet_shellcheck.chmod(0o755)

    def finder(name: str) -> str | None:
        return str(quiet_shellcheck) if name == "shellcheck" else shutil.which(name)

    failing = check_shell_files(repo_root, executable_finder=finder)
    syntax_findings = [
        finding for finding in failing.findings if finding.code == "shell.bash_syntax"
    ]
    assert syntax_findings
    assert all(
        finding.severity is Severity.ERROR and finding.path is not None
        for finding in syntax_findings
    )
    assert failing.is_ok() is False

    (repo_root / "modules/bin/broken").write_text(
        "#!/usr/bin/env bash\nif true; then\n  printf 'ok\\n'\nfi\n",
    )
    assert check_shell_files(repo_root, executable_finder=finder).is_ok() is True


@requires_shellcheck
def test_check_shell_files_reports_shellcheck_warnings(tmp_path: Path) -> None:
    repo_root = _tracked_repo(
        tmp_path,
        {
            "modules/bin/warned": (
                "#!/usr/bin/env bash\n"
                "helper() {\n"
                "  local stamp=$(date)\n"
                "  printf '%s\\n' \"$stamp\"\n"
                "}\n"
                "helper\n"
            ),
        },
    )

    report = check_shell_files(repo_root)

    shellcheck_findings = [
        finding for finding in report.findings if finding.code == "shell.shellcheck"
    ]
    assert shellcheck_findings
    assert all(finding.severity is Severity.ERROR for finding in shellcheck_findings)
    assert any("SC2155" in finding.message for finding in shellcheck_findings)


@requires_zsh
def test_check_shell_files_checks_zsh_syntax(tmp_path: Path) -> None:
    repo_root = _tracked_repo(
        tmp_path,
        {
            "modules/zsh/broken.zsh": "if true; then\n",
        },
    )

    report = check_shell_files(repo_root)

    assert any(
        finding.code == "shell.zsh_syntax" and finding.severity is Severity.ERROR
        for finding in report.findings
    )


@requires_zsh
def test_check_shell_files_gates_restored_reference_startup_dotfiles(
    tmp_path: Path,
) -> None:
    repo_root = _tracked_repo(
        tmp_path,
        # A syntax error in a startup file restore links into $HOME must fail
        # the gate even though it lives under reference/.
        {"reference/.zshrc": "if true; then\n"},
    )

    report = check_shell_files(repo_root)

    assert any(
        finding.code == "shell.zsh_syntax"
        and finding.path == repo_root / "reference/.zshrc"
        for finding in report.findings
    )
    assert report.is_ok() is False


@requires_zsh
def test_zsh_tv_binding_requires_television(tmp_path: Path) -> None:
    source_root = Path(__file__).resolve().parents[1]
    repo_root = tmp_path / "repo"
    env_file = repo_root / "modules/zsh/env.zsh"
    env_file.parent.mkdir(parents=True)
    shutil.copy2(source_root / "modules/zsh/env.zsh", env_file)
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    home.mkdir()
    bin_dir.mkdir()
    (home / "dotfiles").symlink_to(repo_root, target_is_directory=True)
    environment = {
        "HOME": str(home),
        "PATH": f"{bin_dir}:/usr/bin:/bin",
    }
    command = f'source "{env_file}"; bindkey -M emacs "^T"; bindkey -M emacs "^R"'

    without_tv = subprocess.run(
        ["zsh", "-dfc", command],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert without_tv.returncode == 0
    assert without_tv.stdout.splitlines()[0] == '"^T" transpose-chars'

    tv = bin_dir / "tv"
    tv.write_text(
        """#!/bin/sh
if [ "$1" = "--version" ]; then
  exit 0
fi
if [ "$1" = "init" ] && [ "$2" = "zsh" ]; then
  cat <<'EOF'
_tv_smart_autocomplete() { :; }
zle -N tv-smart-autocomplete _tv_smart_autocomplete
bindkey '^T' tv-smart-autocomplete
EOF
  exit 0
fi
exit 1
"""
    )
    tv.chmod(0o755)
    atuin = bin_dir / "atuin"
    atuin.write_text("#!/bin/sh\nexit 99\n")
    atuin.chmod(0o755)
    generated_tv = repo_root / "generated/functions/_tv.zsh"
    generated_tv.parent.mkdir(parents=True)
    generated_tv.write_text(
        "_tv_smart_autocomplete() { :; }\n"
        "zle -N tv-smart-autocomplete _tv_smart_autocomplete\n"
        "bindkey '^T' tv-smart-autocomplete\n"
    )
    (generated_tv.parent / "_atuin.zsh").write_text(
        "_atuin_search() { :; }\n"
        "zle -N atuin-search _atuin_search\n"
        "bindkey '^R' atuin-search\n"
    )
    with_tv = subprocess.run(
        ["zsh", "-dfc", command],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert with_tv.returncode == 0
    assert with_tv.stdout.splitlines() == [
        '"^T" tv-smart-autocomplete',
        '"^R" atuin-search',
    ]


def _television_channel(name: str) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / f"reference/.config/television/cable/{name}.toml"
    with path.open("rb") as file:
        return tomllib.load(file)


def test_television_channel_triggers_are_unambiguous_and_exist() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / "reference/.config/television/config.toml"
    with config_path.open("rb") as file:
        config = tomllib.load(file)

    triggers = config["shell_integration"]["channel_triggers"]
    cable_names = {
        path.stem
        for path in (repo_root / "reference/.config/television/cable").glob("*.toml")
    }
    commands: dict[str, str] = {}
    duplicates: dict[str, tuple[str, str]] = {}
    for channel, channel_commands in triggers.items():
        assert channel in cable_names
        for command in channel_commands:
            if previous := commands.get(command):
                duplicates[command] = (previous, channel)
            commands[command] = channel

    assert duplicates == {}


def test_television_preview_placeholders_use_shell_safe_quoting() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cable_dir = repo_root / "reference/.config/television/cable"
    shell_quote_transform = "replace:s/'/'\"'\"'/g"

    for path in cable_dir.glob("*.toml"):
        with path.open("rb") as file:
            channel = tomllib.load(file)
        preview = channel.get("preview")
        if not isinstance(preview, dict) or "command" not in preview:
            continue
        command = preview["command"]
        if "{" in command:
            assert shell_quote_transform in command, path


def test_television_ssh_channels_parse_aliases_and_known_hosts(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    ssh_dir = home / ".ssh"
    ssh_dir.mkdir(parents=True)
    (ssh_dir / "config").write_text(
        "Host alpha beta\nHost alpha\nHost *.internal !blocked.internal wildcard?\n"
    )
    (ssh_dir / "known_hosts").write_text(
        "one.example,two.example ssh-ed25519 key\n"
        "one.example ssh-ed25519 key\n"
        "@cert-authority marker.example ssh-ed25519 key\n"
        "|1|hash|hash ssh-ed25519 key\n"
        "# comment\n"
    )
    environment = {"HOME": str(home), "PATH": "/usr/bin:/bin"}

    hosts = subprocess.run(
        _television_channel("hosts")["source"]["command"],
        shell=True,
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    known_hosts = subprocess.run(
        _television_channel("known-hosts")["source"]["command"],
        shell=True,
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert hosts.stdout.splitlines() == ["alpha", "beta"]
    assert known_hosts.stdout.splitlines() == [
        "one.example",
        "two.example",
        "marker.example",
    ]


def test_television_channels_use_safe_current_sources() -> None:
    dirs = _television_channel("dirs")
    gists = _television_channel("gists")
    hosts = _television_channel("hosts")

    assert dirs["source"]["command"] == "fd -t d --hidden"
    assert "curl" in gists["metadata"]["requirements"]
    assert 'select(type == "string" and length > 0)' in gists["source"]["command"]
    assert (
        "curl -fsSL -o \"$tmp\" -- '{replace:s/'/'\"'\"'/g}'"
        in gists["preview"]["command"]
    )
    assert "television/gists" not in gists["preview"]["command"]
    assert hosts["keybindings"]["enter"] == "actions:connect"
    assert hosts["actions"]["connect"] == {
        "command": "ssh -- '{replace:s/'/'\"'\"'/g}'",
        "mode": "execute",
    }


@requires_nu
def test_nushell_skips_stale_cached_integrations_when_tools_are_missing(
    tmp_path: Path,
) -> None:
    nu = shutil.which("nu")
    assert nu is not None
    repo_root = tmp_path / "dotfiles"
    config_path = repo_root / "reference/.config/nushell/config.nu"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        (
            Path(__file__).resolve().parents[1] / config_path.relative_to(repo_root)
        ).read_text()
    )
    functions = repo_root / "generated/functions"
    functions.mkdir(parents=True)
    (functions / "_mise.nu").write_text(
        'error make { msg: "stale mise cache loaded" }\n'
    )
    (functions / "_zoxide.nu").write_text(
        'error make { msg: "stale zoxide cache loaded" }\n'
    )
    home = tmp_path / "home"
    home.mkdir()

    completed = subprocess.run(
        [nu, "--config", str(config_path), "--commands", 'print "nu-ready"'],
        check=False,
        capture_output=True,
        text=True,
        env={"HOME": str(home), "PATH": ""},
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "nu-ready"


@requires_zsh
def test_zshenv_exposes_user_and_mise_commands_without_repo_bins_on_linux(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    zshenv = repo_root / "reference/.zshenv"
    home = tmp_path / "home"
    local_bin = home / ".local/bin"
    shims = home / ".local/share/mise/shims"
    modules_bin = home / "dotfiles/modules/bin"
    system_bin = tmp_path / "system-bin"
    for directory in (local_bin, shims, modules_bin, system_bin):
        directory.mkdir(parents=True)
    for executable in (local_bin / "mise", shims / "uv", system_bin / "ss"):
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)

    completed = subprocess.run(
        [
            "zsh",
            "-dfc",
            (
                f'OSTYPE=linux-gnu; source "{zshenv}"; source "{zshenv}"; '
                "command -v mise; command -v uv; command -v ss; "
                'command -v skillshare-source || print -r -- "skillshare-source missing"; '
                'print -r -- "$PATH"'
            ),
        ],
        env={
            "HOME": str(home),
            "PATH": f"{system_bin}:/usr/bin:/bin",
        },
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    lines = completed.stdout.splitlines()
    assert lines[:4] == [
        str(local_bin / "mise"),
        str(shims / "uv"),
        str(system_bin / "ss"),
        "skillshare-source missing",
    ]
    loaded_path = lines[4].split(":")
    assert loaded_path.count(str(local_bin)) == 1
    assert loaded_path.count(str(shims)) == 1
    assert str(modules_bin) not in loaded_path


@requires_zsh
def test_zsh_mise_activation_replaces_the_noninteractive_shim_fallback(
    tmp_path: Path,
) -> None:
    source_root = Path(__file__).resolve().parents[1]
    repo_root = tmp_path / "repo"
    env_file = repo_root / "modules/zsh/env.zsh"
    env_file.parent.mkdir(parents=True)
    shutil.copy2(source_root / "modules/zsh/env.zsh", env_file)
    home = tmp_path / "home"
    local_bin = home / ".local/bin"
    shims = home / ".local/share/mise/shims"
    functions = repo_root / "generated/functions"
    for directory in (local_bin, shims, functions):
        directory.mkdir(parents=True)
    mise = local_bin / "mise"
    mise.write_text("#!/bin/sh\nexit 0\n")
    mise.chmod(0o755)
    (functions / "_mise.zsh").write_text("export MISE_TEST_ACTIVATED=1\n")

    completed = subprocess.run(
        [
            "zsh",
            "-dfc",
            (
                f'source "{env_file}"; '
                'print -r -- "${MISE_TEST_ACTIVATED:-0}"; '
                'print -r -- "${(j.:.)path}"'
            ),
        ],
        env={
            "HOME": str(home),
            "PATH": f"{shims}:/usr/bin:/bin",
        },
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    activated, loaded_path = completed.stdout.splitlines()
    assert activated == "1"
    assert str(shims) not in loaded_path.split(":")


def test_bash_init_loads_starship_only_for_interactive_shells(tmp_path: Path) -> None:
    source_root = Path(__file__).resolve().parents[1]
    repo_root = tmp_path / "repo"
    bash_init = repo_root / "modules/bash/init.bash"
    bash_init.parent.mkdir(parents=True)
    shutil.copy2(source_root / "modules/bash/init.bash", bash_init)
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    home.mkdir()
    bin_dir.mkdir()
    invocation_log = tmp_path / "starship.log"
    starship = bin_dir / "starship"
    starship.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$*\" >> {invocation_log}\n"
        "printf '%s\\n' 'export STARSHIP_READY=1'\n",
    )
    starship.chmod(0o755)
    generated = repo_root / "generated/functions/_starship.bash"
    generated.parent.mkdir(parents=True)
    generated.write_text("export STARSHIP_READY=1\n")
    bash = shutil.which("bash")
    assert bash is not None
    environment = {
        "HOME": str(home),
        "PATH": f"{bin_dir}:/usr/bin:/bin",
    }

    noninteractive = subprocess.run(
        [bash, "--noprofile", "--norc", "-c", f'. "{bash_init}"'],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert noninteractive.returncode == 0
    assert not invocation_log.exists()

    interactive = subprocess.run(
        [
            bash,
            "--noprofile",
            "--norc",
            "-ic",
            f'. "{bash_init}"; test "${{STARSHIP_READY:-}}" = 1',
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert interactive.returncode == 0
    assert not invocation_log.exists()

    starship.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' 'stale shim' >&2\n"
        "printf '%s\\n' 'export STARSHIP_READY=1'\n"
        "exit 1\n",
    )
    failing_shim = subprocess.run(
        [
            bash,
            "--noprofile",
            "--norc",
            "-ic",
            f'. "{bash_init}"; test "${{STARSHIP_READY:-}}" = 1',
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert failing_shim.returncode == 0
    assert "stale shim" not in failing_shim.stderr


def test_bash_init_adds_navigation_editing_and_guarded_history_tools(
    tmp_path: Path,
) -> None:
    source_root = Path(__file__).resolve().parents[1]
    repo_root = tmp_path / "repo"
    bash_init = repo_root / "modules/bash/init.bash"
    bash_init.parent.mkdir(parents=True)
    shutil.copy2(source_root / "modules/bash/init.bash", bash_init)
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    home.mkdir()
    bin_dir.mkdir()
    invocation_log = tmp_path / "shell-tools.log"
    for tool, output in (
        ("atuin", "export ATUIN_READY=1"),
        ("zoxide", "export ZOXIDE_READY=1"),
    ):
        executable = bin_dir / tool
        executable.write_text(
            "#!/bin/sh\n"
            f"printf '%s %s\\n' {tool} \"$*\" >> {invocation_log}\n"
            f"printf '%s\\n' '{output}'\n",
        )
        executable.chmod(0o755)
    functions = repo_root / "generated/functions"
    functions.mkdir(parents=True)
    (functions / "_atuin.bash").write_text("export ATUIN_READY=1\n")
    (functions / "_zoxide.bash").write_text("export ZOXIDE_READY=1\n")
    bash = shutil.which("bash")
    assert bash is not None
    dirname = shutil.which("dirname")
    assert dirname is not None
    (bin_dir / "dirname").symlink_to(dirname)
    environment = {
        "HOME": str(home),
        "PATH": str(bin_dir),
    }

    completed = subprocess.run(
        [
            bash,
            "--noprofile",
            "--norc",
            "-ic",
            (
                f'. "{bash_init}"; '
                'test "${FZF_CTRL_R_COMMAND+x}" = x; '
                'test -z "$FZF_CTRL_R_COMMAND"; '
                "alias ..; alias ...; "
                "bind -s; "
                'printf "READY=%s:%s\\n" "$ATUIN_READY" "$ZOXIDE_READY"'
            ),
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "alias ..='cd ..'" in completed.stdout
    assert "alias ...='cd ../..'" in completed.stdout
    assert '"\\C-w": "\\e\\C-?"' in completed.stdout
    assert "READY=1:1" in completed.stdout
    assert not invocation_log.exists()

    for tool in ("atuin", "zoxide"):
        executable = bin_dir / tool
        executable.unlink()
    degraded = subprocess.run(
        [
            bash,
            "--noprofile",
            "--norc",
            "-ic",
            (
                f'. "{bash_init}"; '
                'test -z "${ATUIN_READY:-}" && test -z "${ZOXIDE_READY:-}" && '
                'test -z "${FZF_CTRL_R_COMMAND+x}"'
            ),
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert degraded.returncode == 0
    assert "stale shim" not in degraded.stderr


def test_bash_init_activates_mise_after_prompt_tools(tmp_path: Path) -> None:
    source_root = Path(__file__).resolve().parents[1]
    repo_root = tmp_path / "repo"
    bash_init = repo_root / "modules/bash/init.bash"
    bash_init.parent.mkdir(parents=True)
    shutil.copy2(source_root / "modules/bash/init.bash", bash_init)
    home = tmp_path / "home"
    local_bin = home / ".local/bin"
    bin_dir = tmp_path / "bin"
    local_bin.mkdir(parents=True)
    bin_dir.mkdir()
    tools = {
        local_bin
        / "mise": "printf '%s\\n' 'PROMPT_COMMAND=\"${PROMPT_COMMAND:+$PROMPT_COMMAND;}mise_hook\"'",
        bin_dir / "starship": "printf '%s\\n' 'PROMPT_COMMAND=starship_precmd'",
        bin_dir / "atuin": ":",
        bin_dir
        / "zoxide": "printf '%s\\n' 'PROMPT_COMMAND=\"$PROMPT_COMMAND;zoxide_hook\"'",
    }
    for executable, command in tools.items():
        executable.write_text(f"#!/bin/sh\n{command}\n")
        executable.chmod(0o755)
    functions = repo_root / "generated/functions"
    functions.mkdir(parents=True)
    (functions / "_starship.bash").write_text("PROMPT_COMMAND=starship_precmd\n")
    (functions / "_atuin.bash").write_text(":\n")
    (functions / "_zoxide.bash").write_text(
        'PROMPT_COMMAND="$PROMPT_COMMAND;zoxide_hook"\n'
    )
    (functions / "_mise.bash").write_text(
        'PROMPT_COMMAND="${PROMPT_COMMAND:+$PROMPT_COMMAND;}mise_hook"\n'
    )
    bash = shutil.which("bash")
    assert bash is not None

    completed = subprocess.run(
        [
            bash,
            "--noprofile",
            "--norc",
            "-ic",
            f'. "{bash_init}"; printf "%s" "$PROMPT_COMMAND"',
        ],
        env={"HOME": str(home), "PATH": f"{bin_dir}:/usr/bin:/bin"},
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout == "starship_precmd;zoxide_hook;mise_hook"


def test_bash_init_does_not_autostart_herdr_for_interactive_ssh(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    bash_init = repo_root / "modules/bash/init.bash"
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    home.mkdir()
    bin_dir.mkdir()
    herdr = bin_dir / "herdr"
    herdr.write_text(
        "#!/bin/sh\n"
        'if [ "${1:-}" = --version ]; then\n'
        "  exit 0\n"
        "fi\n"
        "printf '%s\\n' HERDR_STARTED\n",
    )
    herdr.chmod(0o755)
    bash = shutil.which("bash")
    assert bash is not None
    environment = {
        "HOME": str(home),
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "SSH_TTY": "/dev/pts/test",
    }

    completed = subprocess.run(
        [
            bash,
            "--noprofile",
            "--norc",
            "-ic",
            f'. "{bash_init}"; printf "%s\\n" SHELL_CONTINUED',
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout.splitlines() == ["SHELL_CONTINUED"]

    noninteractive = subprocess.run(
        [
            bash,
            "--noprofile",
            "--norc",
            "-c",
            f'. "{bash_init}"; printf "%s\\n" SHELL_CONTINUED',
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert noninteractive.returncode == 0
    assert noninteractive.stdout.splitlines() == ["SHELL_CONTINUED"]


def test_check_shell_files_requires_missing_tools_explicitly(tmp_path: Path) -> None:
    repo_root = _tracked_repo(
        tmp_path,
        {"modules/bin/good": "#!/usr/bin/env bash\nprintf 'ok\\n'\n"},
    )

    with pytest.raises(ShellCheckError, match="shellcheck"):
        check_shell_files(
            repo_root,
            executable_finder=lambda name: (
                None if name == "shellcheck" else shutil.which(name)
            ),
        )


def test_check_shell_files_skips_zsh_loudly_when_zsh_is_absent(
    tmp_path: Path,
) -> None:
    repo_root = _tracked_repo(
        tmp_path,
        {
            "modules/zsh/env.zsh": "alias ok=true\n",
            "modules/bin/good": "#!/usr/bin/env bash\nprintf 'ok\\n'\n",
        },
    )
    quiet_shellcheck = tmp_path / "quiet-shellcheck"
    quiet_shellcheck.write_text("#!/bin/sh\nexit 0\n")
    quiet_shellcheck.chmod(0o755)

    def finder(name: str) -> str | None:
        if name == "zsh":
            return None
        if name == "shellcheck":
            return str(quiet_shellcheck)
        return shutil.which(name)

    report = check_shell_files(repo_root, executable_finder=finder)

    assert report.is_ok() is True
    skipped = [
        finding for finding in report.findings if finding.code == "shell.zsh_skipped"
    ]
    assert skipped
    assert skipped[0].severity is None
    assert skipped[0].applicable is False
    assert "zsh is not installed" in skipped[0].message


@requires_zsh
def test_zsh_env_derives_root_and_rejects_invalid_override(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env_file = repo_root / "modules/zsh/env.zsh"
    environment = {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}

    derived = subprocess.run(
        ["zsh", "-dfc", f'source "{env_file}"; print -r -- "$DOTFILES_ROOT"'],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    invalid = subprocess.run(
        ["zsh", "-dfc", f'source "{env_file}"'],
        env={**environment, "DOTFILES_ROOT": str(tmp_path / "missing")},
        check=False,
        capture_output=True,
        text=True,
    )

    assert derived.returncode == 0
    assert derived.stdout.strip() == str(repo_root)
    assert invalid.returncode != 0
    assert "DOTFILES_ROOT is invalid" in invalid.stderr


@requires_zsh
def test_openv_uses_one_selected_op_without_signin_retry(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env_file = repo_root / "modules/zsh/env.zsh"
    fake_op = tmp_path / "op"
    log = tmp_path / "op.log"
    fake_op.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$*\" >>\"$OP_LOG\"\nprintf 'auth failed\\n' >&2\nexit 7\n"
    )
    fake_op.chmod(0o755)

    completed = subprocess.run(
        ["zsh", "-dfc", f'source "{env_file}"; openv example'],
        env={
            "HOME": str(tmp_path),
            "PATH": "/usr/bin:/bin",
            "OPENV_OP_ENV_BIN": str(fake_op),
            "OP_LOG": str(log),
        },
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert log.read_text().splitlines() == ["environment read example"]
    assert "auth failed" in completed.stderr
