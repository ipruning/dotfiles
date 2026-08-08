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
        assert executed.stdout.rstrip("\n") == str(directory)
    script = script_log.read_text()
    assert str(directory) not in script
    assert "set the clipboard to oldClip" in script
    assert "on error errorMessage number errorNumber" in script
