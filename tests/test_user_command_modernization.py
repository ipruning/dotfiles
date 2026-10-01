from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BIN = REPO_ROOT / "modules/bin"
SPECIAL_NAMES = [
    "space path",
    "single'quote",
    'double"quote',
    "back\\slash",
    "line\nbreak",
    "triple'''quote",
]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o755)


def _pi_environment(
    tmp_path: Path, list_status: int, list_output: str
) -> tuple[dict[str, str], Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "zellij.log"
    _write_executable(
        fake_bin / "zellij",
        "#!/bin/bash\n"
        'printf \'%s\\n\' "$*" >>"$ZELLIJ_LOG"\n'
        "if [[ $1 == list-sessions ]]; then\n"
        "  printf '%s' \"$LIST_OUTPUT\"\n"
        '  exit "$LIST_STATUS"\n'
        "fi\n",
    )
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "ZELLIJ_LOG": str(log),
        "LIST_STATUS": str(list_status),
        "LIST_OUTPUT": list_output,
    }
    return env, log


def _session_for(directory: Path) -> str:
    command = (
        f"source {shlex.quote(str(BIN / '_lib/session-id.sh'))}; "
        f"session_id_for_dir {shlex.quote(str(directory.resolve()))}"
    )
    return subprocess.run(
        ["bash", "-c", command], check=True, capture_output=True, text=True
    ).stdout


def test_link_reads_zellij_dump_screen_from_stdout(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    argv_log = tmp_path / "argv"
    _write_executable(
        fake_bin / "zellij",
        "#!/bin/bash\nprintf '%s\\0' \"$@\" >\"$ARGV_LOG\"\nprintf 'screen output'\n",
    )
    code = (
        "import importlib.util; "
        f"spec=importlib.util.spec_from_file_location('link', {str(BIN / 'link.py')!r}); "
        "module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); "
        "print(module.get_zellij_screen(), end='')"
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "ZELLIJ": "1",
            "ARGV_LOG": str(argv_log),
        },
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout == "screen output"
    assert argv_log.read_bytes().split(b"\0")[:-1] == [b"action", b"dump-screen"]


def test_link_fails_without_stdin_or_zellij_input() -> None:
    completed = subprocess.run(
        [BIN / "link.py"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "no input" in completed.stderr
    assert "pipe text on stdin" in completed.stderr
    assert "Zellij" in completed.stderr


def test_link_rejects_non_exact_fzf_selection(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    open_log = tmp_path / "open.log"
    _write_executable(
        fake_bin / "fzf", "#!/bin/bash\ncat >/dev/null\necho example.com\n"
    )
    _write_executable(fake_bin / "open", '#!/bin/bash\necho "$*" >"$OPEN_LOG"\n')

    completed = subprocess.run(
        [BIN / "link.py"],
        input="https://example.com\n",
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "OPEN_LOG": str(open_log),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "No matching item found" in completed.stderr
    assert not open_log.exists()


def test_session_id_requires_git() -> None:
    command = (
        f"source {shlex.quote(str(BIN / '_lib/session-id.sh'))}; "
        "PATH='' session_id_short_hash /tmp/example"
    )
    completed = subprocess.run(
        ["bash", "-c", command], capture_output=True, text=True, check=False
    )

    assert completed.returncode == 127
    assert completed.stdout == ""
    assert "git is required" in completed.stderr


def test_pmt_keeps_prompt_behavior_without_zellij_context() -> None:
    completed = subprocess.run(
        [sys.executable, BIN / "pmt.py", "hello", "world"],
        env={**os.environ, "ZELLIJ": "1"},
        input="supporting context\n",
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout == (
        "<other_context>\nsupporting context\n</other_context>\n\n"
        "<user_instructions>\nhello world\n</user_instructions>\n\n"
    )
    assert "terminal_context" not in completed.stdout


def test_pi_zellij_attaches_to_existing_session(tmp_path: Path) -> None:
    session = _session_for(tmp_path)
    env, log = _pi_environment(tmp_path, 0, f"other\n{session}\n")

    completed = subprocess.run([BIN / "pi-zellij"], cwd=tmp_path, env=env, check=False)

    assert completed.returncode == 0
    assert log.read_text().splitlines() == [
        "list-sessions --no-formatting --short",
        f"attach {session}",
    ]


def test_pi_zellij_creates_when_zellij_reports_no_sessions(tmp_path: Path) -> None:
    env, log = _pi_environment(tmp_path, 1, "No active zellij sessions found.\n")

    completed = subprocess.run([BIN / "pi-zellij"], cwd=tmp_path, env=env, check=False)

    assert completed.returncode == 0
    assert "--new-session-with-layout pi" in log.read_text()


def test_pi_zellij_preserves_other_list_failure(tmp_path: Path) -> None:
    env, log = _pi_environment(tmp_path, 7, "connection failed\n")

    completed = subprocess.run(
        [BIN / "pi-zellij"],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 7
    assert completed.stderr == "connection failed\n"
    assert log.read_text().splitlines() == ["list-sessions --no-formatting --short"]


@pytest.mark.parametrize("special_name", SPECIAL_NAMES)
def test_zed_image_paste_passes_special_paths_only_as_argv(
    tmp_path: Path, special_name: str
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    argv_log = tmp_path / "argv"
    script_log = tmp_path / "script"
    _write_executable(
        fake_bin / "osascript",
        '#!/bin/bash\nprintf \'%s\\0\' "$@" >"$ARGV_LOG"\ncat >"$SCRIPT_LOG"\ntouch "$2"\nprintf ok\n',
    )
    _write_executable(fake_bin / "pbcopy", '#!/bin/bash\ncat >"$PBCOPY_LOG"\n')
    worktree = tmp_path / special_name
    editor_dir = worktree / "docs"
    editor_dir.mkdir(parents=True)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "ZED_FILE": "note.md",
        "ZED_WORKTREE_ROOT": str(worktree),
        "IMG_SAVE_PATH": "images",
        "ZED_STEM": "note",
        "ZED_DIRNAME": str(editor_dir),
        "ARGV_LOG": str(argv_log),
        "SCRIPT_LOG": str(script_log),
        "PBCOPY_LOG": str(tmp_path / "clipboard"),
    }

    completed = subprocess.run([BIN / "zed-image-paste"], env=env, check=False)

    assert completed.returncode == 0
    argv = argv_log.read_bytes().split(b"\0")[:-1]
    assert argv[0] == b"-"
    assert Path(os.fsdecode(argv[1])).parent == worktree / "images"
    assert str(worktree) not in script_log.read_text()


@pytest.mark.parametrize("special_name", SPECIAL_NAMES)
def test_amp_ghostty_passes_quoted_commands_as_argv(
    tmp_path: Path, special_name: str
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    argv_log = tmp_path / "argv"
    _write_executable(
        fake_bin / "osascript",
        '#!/bin/bash\nprintf \'%s\\0\' "$@" >"$ARGV_LOG"\ncat >"$SCRIPT_LOG"\n',
    )
    for command in ("amp", "lazygit", "yazi"):
        _write_executable(fake_bin / command, "#!/bin/bash\npwd -P\n")
    directory = tmp_path / special_name
    directory.mkdir()
    script_log = tmp_path / "script"
    env = {
        **os.environ,
        "OSTYPE": "darwin",
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "ARGV_LOG": str(argv_log),
        "SCRIPT_LOG": str(script_log),
    }

    completed = subprocess.run([BIN / "amp-ghostty", directory], env=env, check=False)

    assert completed.returncode == 0
    argv = [os.fsdecode(value) for value in argv_log.read_bytes().split(b"\0")[:-1]]
    assert argv[0] == "-"
    for command, expected_program in zip(
        argv[1:], ("amp", "lazygit", "yazi"), strict=True
    ):
        assert command.endswith(f" && {expected_program}")
        executed = subprocess.run(
            ["bash", "-c", command], env=env, check=True, capture_output=True, text=True
        )
        assert executed.stdout.rstrip("\n") == str(directory.resolve())
    script = script_log.read_text()
    assert str(directory.resolve()) not in script
    assert 'click menu item "New Tab"' in script
    assert (
        "if candidateId is not in existingIds then return terminal id candidateId"
        in (script)
    )
    assert script.index("my waitForNewTerminal(existingIds)") < script.index(
        "my sendCommand(item 1 of argv, ampTerminal)"
    )
    assert "split ampTerminal direction right" in script
    assert "split lazygitTerminal direction down" in script
    assert "input text commandText to targetTerminal" in script
    assert 'send key "enter" to targetTerminal' in script
    assert '"com.mitchellh.ghostty" to focus ampTerminal' in script
    assert "clipboard" not in script
    assert "keystroke" not in script


@pytest.mark.skipif(
    sys.platform != "darwin" or not Path("/Applications/Ghostty.app").is_dir(),
    reason="Ghostty AppleScript compilation requires its installed macOS dictionary",
)
def test_amp_ghostty_applescript_compiles(tmp_path: Path) -> None:
    source = (BIN / "amp-ghostty").read_text()
    applescript = source.split("<<'APPLESCRIPT'\n", 1)[1].rsplit("\nAPPLESCRIPT", 1)[0]
    completed = subprocess.run(
        ["/usr/bin/osacompile", "-o", str(tmp_path / "compiled.scpt")],
        input=applescript,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr


SHELL_COMMANDS = [
    "amp-ghostty",
    "c",
    "d",
    "dateutc",
    "g",
    "histx",
    "mkbir",
    "newwin",
    "o",
    "p",
    "pi-tmux",
    "pi-zellij",
    "ports",
    "repoprompt",
    "scratch",
    "zed-image-paste",
]
PYTHON_COMMANDS = [
    "autocorrect.py",
    "chatgpt.py",
    "get-codex-dump.py",
    "get-transcript.py",
    "link.py",
    "pi-session-export.py",
    "pmt.py",
    "skillshare-source",
    "ttok",
]


def _discovery_environment(tmp_path: Path) -> tuple[dict[str, str], Path]:
    """Isolate host state and log external boundaries, not command logic."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "bash").symlink_to("/bin/bash")
    log = tmp_path / "effects.log"
    for name in (
        "atuin",
        "date",
        "dirname",
        "git",
        "lazydocker",
        "lazygit",
        "lsof",
        "mkdir",
        "mktemp",
        "open",
        "osascript",
        "pbcopy",
        "pbpaste",
        "ss",
        "tmux",
        "viddy",
        "vim",
        "xdg-open",
        "xclip",
        "zellij",
    ):
        _write_executable(
            fake_bin / name,
            '#!/bin/bash\nprintf \'%s\\n\' "${0##*/} $*" >>"$EFFECTS_LOG"\n',
        )
    for name in ("home", "work", "temp", "cache"):
        (tmp_path / name).mkdir()
    env = {
        **os.environ,
        "PATH": str(fake_bin),
        "HOME": str(tmp_path / "home"),
        "TMPDIR": str(tmp_path / "temp"),
        "XDG_CONFIG_HOME": str(tmp_path / "home/config"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "TIKTOKEN_CACHE_DIR": str(tmp_path / "cache"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "BASH_ENV": "/dev/null",
        "ENV": "/dev/null",
        "VISUAL": "vim",
        "EDITOR": "vim",
        "ZELLIJ": "1",
        "ZED_FILE": "note.md",
        "ZED_WORKTREE_ROOT": str(tmp_path / "work"),
        "IMG_SAVE_PATH": "images",
        "ZED_STEM": "note",
        "ZED_DIRNAME": str(tmp_path / "work"),
        "EFFECTS_LOG": str(log),
    }
    return env, log


def _assert_no_discovery_effects(tmp_path: Path, log: Path) -> None:
    assert not log.exists()
    for name in ("home", "work", "temp", "cache"):
        assert list((tmp_path / name).iterdir()) == []


@pytest.mark.parametrize("command", SHELL_COMMANDS)
@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_shell_help_is_local_and_has_no_effects(
    tmp_path: Path, command: str, flag: str
) -> None:
    env, log = _discovery_environment(tmp_path)
    completed = subprocess.run(
        [BIN / command, flag],
        env=env,
        cwd=tmp_path / "work",
        input="must not copy this\n",
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Usage:" in completed.stdout
    assert completed.stderr == ""
    _assert_no_discovery_effects(tmp_path, log)


@pytest.mark.parametrize("command", PYTHON_COMMANDS)
def test_python_help_has_no_command_effects(tmp_path: Path, command: str) -> None:
    env, log = _discovery_environment(tmp_path)
    # Use the already-provisioned interpreter: uv's launcher can provision an
    # environment even for --help, which is a separate dependency boundary.
    completed = subprocess.run(
        [sys.executable, BIN / command, "--help"],
        env=env,
        cwd=tmp_path / "work",
        input="must not send this\n",
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr
    assert "usage:" in completed.stdout.lower()
    assert completed.stderr == ""
    _assert_no_discovery_effects(tmp_path, log)


@pytest.mark.parametrize("command", ["chatgpt.py", "pmt.py", "ttok"])
def test_python_short_help_has_no_command_effects(tmp_path: Path, command: str) -> None:
    env, log = _discovery_environment(tmp_path)
    completed = subprocess.run(
        [sys.executable, BIN / command, "-h"],
        env=env,
        cwd=tmp_path / "work",
        input="must not send this\n",
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Usage:" in completed.stdout
    _assert_no_discovery_effects(tmp_path, log)


@pytest.mark.parametrize("command", [c for c in SHELL_COMMANDS if c not in {"d", "g"}])
@pytest.mark.parametrize("args", [["--invalid"], ["--help", "extra"]])
def test_shell_rejected_arguments_have_no_effects(
    tmp_path: Path, command: str, args: list[str]
) -> None:
    env, log = _discovery_environment(tmp_path)
    completed = subprocess.run(
        [BIN / command, *args],
        env=env,
        cwd=tmp_path / "work",
        input="must not copy this\n",
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr
    _assert_no_discovery_effects(tmp_path, log)


@pytest.mark.parametrize(
    "command,args",
    [
        ("mkbir", ["one", "two"]),
        ("mkbir", [""]),
        ("o", ["one", "two"]),
        ("o", [""]),
        ("newwin", ["chrome", "extra"]),
        ("histx", ["-1"]),
        ("ports", ["--watch", "extra"]),
    ],
)
def test_rejected_operands_have_no_effects(
    tmp_path: Path, command: str, args: list[str]
) -> None:
    env, log = _discovery_environment(tmp_path)
    completed = subprocess.run(
        [BIN / command, *args],
        env=env,
        cwd=tmp_path / "work",
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )

    assert completed.returncode == 2
    assert completed.stderr
    _assert_no_discovery_effects(tmp_path, log)


@pytest.mark.parametrize(
    "ostype,listing",
    [
        ("darwin", "lsof -nP -iTCP -sTCP:LISTEN"),
        ("linux-gnu", "ss -tulpn"),
    ],
)
@pytest.mark.parametrize("watch", [False, True])
@pytest.mark.parametrize("has_viddy", [False, True])
def test_ports_only_watches_when_explicit(
    tmp_path: Path, ostype: str, listing: str, watch: bool, has_viddy: bool
) -> None:
    env, log = _discovery_environment(tmp_path)
    if not has_viddy:
        (tmp_path / "bin/viddy").unlink()
    completed = subprocess.run(
        [BIN / "ports", *(["--watch"] if watch else [])],
        env={**env, "OSTYPE": ostype},
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )

    if watch and not has_viddy:
        assert completed.returncode == 1
        assert "requires viddy" in completed.stderr
        assert not log.exists()
    else:
        assert completed.returncode == 0, completed.stderr
        expected = f"viddy --interval 1s {listing}" if watch else listing
        assert log.read_text().splitlines() == [expected]


def test_mkbir_valid_directory_keeps_counter_behavior(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    target = tmp_path / "bird folders"
    for bird, count in (("Albatross", "1\n"), ("Avocet", "2\n")):
        completed = subprocess.run(
            [BIN / "mkbir", target],
            env={**os.environ, "HOME": str(home)},
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        assert completed.returncode == 0, completed.stderr
        assert (target / bird).is_dir()
        assert (home / ".bird_count").read_text() == count
        assert not (home / ".bird_count.lock").exists()


def test_scratch_creates_a_file_and_invokes_selected_editor(tmp_path: Path) -> None:
    editor = tmp_path / "editor"
    log = tmp_path / "editor.argv"
    _write_executable(editor, '#!/bin/bash\nprintf \'%s\\0\' "$@" >"$EDITOR_LOG"\n')
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    # macOS mktemp with no template need not honor TMPDIR. Redirect only the
    # external allocation boundary, retaining a real temporary file.
    _write_executable(
        fake_bin / "mktemp",
        '#!/bin/bash\nexec /usr/bin/mktemp "$SCRATCH_TEMPLATE"\n',
    )
    completed = subprocess.run(
        [BIN / "scratch"],
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "SCRATCH_TEMPLATE": str(tmp_path / "scratch.XXXXXX"),
            "VISUAL": f"{editor} --wait",
            "EDITOR_LOG": str(log),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )

    assert completed.returncode == 0, completed.stderr
    args = log.read_bytes().split(b"\0")[:-1]
    assert args[0] == b"--wait"
    assert len(args) == 2
    retained_file = Path(os.fsdecode(args[1]))
    assert retained_file.parent.resolve() == tmp_path.resolve()
    assert retained_file.is_file()


@pytest.mark.parametrize("nested", [False, True])
def test_pi_tmux_existing_session_keeps_attach_or_switch_behavior(
    tmp_path: Path, nested: bool
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "tmux.log"
    _write_executable(
        fake_bin / "tmux",
        '#!/bin/bash\nprintf \'%s\\n\' "$*" >>"$TMUX_LOG"\n'
        'if [[ $1 == list-windows ]]; then printf "pi\\n"; fi\n',
    )
    session = _session_for(tmp_path)
    completed = subprocess.run(
        [BIN / "pi-tmux"],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "TMUX": "test-session" if nested else "",
            "TMUX_LOG": str(log),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )

    assert completed.returncode == 0, completed.stderr
    expected = [f"has-session -t {session}", f"list-windows -t {session} -F #W"]
    if nested:
        expected.extend([
            f"switch-client -t {session}",
            f"select-window -t {session}:pi",
        ])
    else:
        expected.extend([f"select-window -t {session}:pi", f"attach -t {session}"])
    assert log.read_text().splitlines() == expected


@pytest.mark.parametrize("ostype,tool", [("darwin", "lsof"), ("linux-gnu", "ss")])
def test_ports_missing_listing_tool_does_not_launch_watcher(
    tmp_path: Path, ostype: str, tool: str
) -> None:
    env, log = _discovery_environment(tmp_path)
    (tmp_path / "bin" / tool).unlink()
    completed = subprocess.run(
        [BIN / "ports", "--watch"],
        env={**env, "OSTYPE": ostype},
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )

    assert completed.returncode == 1
    assert f"required command not found: {tool}" in completed.stderr
    assert not log.exists()


def test_command_index_covers_every_executable() -> None:
    index = (BIN / "README.md").read_text()
    commands = [
        path.name
        for path in BIN.iterdir()
        if path.is_file() and os.access(path, os.X_OK)
    ]
    for command in commands:
        assert f"[{command}]({command})" in index
