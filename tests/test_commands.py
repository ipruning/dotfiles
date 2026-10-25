import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

# These tests induce a write failure by making a directory read-only. Root
# bypasses directory permission checks (CAP_DAC_OVERRIDE), so the failure path
# never triggers and the assertions are meaningless — skip them there.
skip_as_root = pytest.mark.skipif(
    os.geteuid() == 0,
    reason="permission-denied write failure cannot be induced as root",
)


def test_skillshare_source_reports_version() -> None:
    executable = Path(__file__).resolve().parents[1] / "commands/skillshare-source"

    completed = subprocess.run(
        [str(executable), "--version"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert re.fullmatch(r"skillshare-source \d+\.\d+\.\d+", completed.stdout.strip())


def test_skillshare_source_requires_universal_target_path(
    tmp_path: Path,
) -> None:
    executable = Path(__file__).resolve().parents[1] / "commands/skillshare-source"
    config = tmp_path / "skillshare/config.yaml"
    config.parent.mkdir()
    target = tmp_path / "installed-skills"
    skill = target / "example"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: example\ndescription: Example skill.\n---\n"
    )
    config.write_text(f"targets:\n  universal:\n    skills:\n      path: {target}\n")

    configured = subprocess.run(
        [str(executable), "descriptions"],
        env={**os.environ, "SKILLSHARE_CONFIG": str(config)},
        check=False,
        capture_output=True,
        text=True,
    )

    assert configured.returncode == 0
    assert json.loads(configured.stdout) == {
        "name": "example",
        "path": "example",
        "description": "Example skill.",
    }

    config.write_text(
        "targets:\n  claude:\n    skills:\n      path: ~/.claude/skills\n"
    )
    missing = subprocess.run(
        [str(executable), "descriptions"],
        env={**os.environ, "SKILLSHARE_CONFIG": str(config)},
        check=False,
        capture_output=True,
        text=True,
    )

    assert missing.returncode == 1
    assert "no usable targets.universal.skills.path" in missing.stderr


def test_zsh_profile_reports_invalid_input_without_optional_gum(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    executable = repo_root / "scripts/zsh-profile"
    tool_bin = tmp_path / "bin"
    tool_bin.mkdir()
    # Real bash and dirname serve the script preamble; the bare PATH keeps an
    # optional host gum from hijacking the plain-error output this test pins.
    import shutil as _shutil

    for real in ("bash", "dirname"):
        source = _shutil.which(real)
        assert source is not None
        (tool_bin / real).symlink_to(source)

    help_result = subprocess.run(
        [str(executable), "--help"],
        env={"HOME": str(tmp_path), "PATH": str(tool_bin)},
        check=False,
        capture_output=True,
        text=True,
    )

    assert help_result.returncode == 0
    assert help_result.stderr == ""
    assert "Usage: mise run zsh-profile -- [runs] [warmup]" in help_result.stdout

    completed = subprocess.run(
        [str(executable), "invalid"],
        env={"HOME": str(tmp_path), "PATH": str(tool_bin)},
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert (
        completed.stderr.strip()
        == "error: runs must be a positive integer (got: invalid)"
    )


def test_zsh_profile_validates_arity_and_numeric_bounds_before_tools(
    tmp_path: Path,
) -> None:
    executable = Path(__file__).resolve().parents[1] / "scripts/zsh-profile"
    tool_bin = tmp_path / "bin"
    tool_bin.mkdir()
    import shutil as _shutil

    for real in ("bash", "dirname"):
        source = _shutil.which(real)
        assert source is not None
        (tool_bin / real).symlink_to(source)

    cases = [
        (["1", "2", "3"], 2, "Usage:"),
        (["0"], 1, "runs must be a positive integer"),
        (["1", "-1"], 1, "warmup must be a nonnegative integer"),
    ]
    for args, returncode, diagnostic in cases:
        completed = subprocess.run(
            [str(executable), *args],
            env={"HOME": str(tmp_path), "PATH": str(tool_bin)},
            capture_output=True,
            text=True,
        )
        assert completed.returncode == returncode
        assert completed.stdout == ""
        assert diagnostic in completed.stderr
        assert "Missing required" not in completed.stderr


def _write_executable(path: Path, contents: str) -> None:
    path.write_text(contents)
    path.chmod(0o755)


def test_pi_session_export_requires_an_explicit_command(tmp_path: Path) -> None:
    executable = Path(__file__).resolve().parents[1] / "commands/pi-session-export"
    input_path = tmp_path / "session.jsonl"
    input_path.write_text("")

    completed = subprocess.run(
        [sys.executable, str(executable), str(input_path)],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "invalid choice" in completed.stderr
    assert "convert" in completed.stderr


def test_pi_session_export_keeps_data_derived_names_inside_output_dir(
    tmp_path: Path,
) -> None:
    executable = Path(__file__).resolve().parents[1] / "commands/pi-session-export"
    input_path = tmp_path / "session.jsonl"
    output_dir = tmp_path / "out"
    input_path.write_text(json.dumps({"type": "session", "id": "session-123"}) + "\n")

    completed = subprocess.run(
        [str(executable), "convert", str(input_path), "--output-dir", str(output_dir)],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    raw_path = output_dir / "session-123.jsonl"
    turns_path = output_dir / "session-123.turns.with-tools.jsonl"
    assert raw_path.is_file()
    assert turns_path.is_file()
    assert raw_path.read_text() == input_path.read_text()
    assert raw_path.parent == turns_path.parent == output_dir


@pytest.mark.parametrize(
    "name", ("../escaped", "/tmp/escaped", "nested/name", "nested\\name")
)
def test_pi_session_export_rejects_path_like_names(tmp_path: Path, name: str) -> None:
    executable = Path(__file__).resolve().parents[1] / "commands/pi-session-export"
    input_path = tmp_path / "session.jsonl"
    output_dir = tmp_path / "out"
    input_path.write_text(json.dumps({"type": "session", "id": name}) + "\n")

    completed = subprocess.run(
        [str(executable), "convert", str(input_path), "--output-dir", str(output_dir)],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "single filename component" in completed.stderr
    assert not output_dir.exists()
    assert not (tmp_path / "escaped.jsonl").exists()


def test_pi_session_export_rejects_path_like_stem(tmp_path: Path) -> None:
    executable = Path(__file__).resolve().parents[1] / "commands/pi-session-export"
    input_path = tmp_path / "session.jsonl"
    output_dir = tmp_path / "out"
    input_path.write_text(json.dumps({"type": "session", "id": "session-123"}) + "\n")

    completed = subprocess.run(
        [
            str(executable),
            "convert",
            str(input_path),
            "--output-dir",
            str(output_dir),
            "--stem",
            "../escaped",
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "single filename component" in completed.stderr
    assert not output_dir.exists()
    assert not (tmp_path / "escaped.jsonl").exists()


def test_pi_session_export_rejects_symlinked_output_destination(tmp_path: Path) -> None:
    executable = Path(__file__).resolve().parents[1] / "commands/pi-session-export"
    input_path = tmp_path / "session.jsonl"
    output_dir = tmp_path / "out"
    outside = tmp_path / "outside.jsonl"
    output_dir.mkdir()
    outside.write_text("keep\n")
    (output_dir / "session-123.jsonl").symlink_to(outside)
    input_path.write_text(json.dumps({"type": "session", "id": "session-123"}) + "\n")

    completed = subprocess.run(
        [str(executable), "convert", str(input_path), "--output-dir", str(output_dir)],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "symlinked output destination" in completed.stderr
    assert outside.read_text() == "keep\n"
    assert not (output_dir / "session-123.turns.with-tools.jsonl").exists()


@skip_as_root
def test_skillshare_exec_restore_failure_overrides_child_success(
    tmp_path: Path,
) -> None:
    executable = Path(__file__).resolve().parents[1] / "commands/skillshare-source"
    config_dir = tmp_path / "skillshare"
    config_dir.mkdir()
    config = config_dir / "config.yaml"
    original = tmp_path / "original"
    temporary = tmp_path / "temporary"
    config.write_text(f"source: {original}\n")
    (config_dir / "sources.json").write_text(json.dumps({"temporary": str(temporary)}))
    tool_bin = tmp_path / "bin"
    tool_bin.mkdir()
    _write_executable(
        tool_bin / "skillshare",
        f'#!/bin/sh\nprintf \'%s\\n\' \'{{"source":{{"path":"{original}"}}}}\'\n',
    )
    child = tmp_path / "child"
    _write_executable(child, f"#!/bin/sh\nchmod 555 '{config_dir}'\nexit 0\n")
    try:
        completed = subprocess.run(
            [str(executable), "exec", "temporary", "--", str(child)],
            env={
                **os.environ,
                "PATH": f"{tool_bin}:{os.environ['PATH']}",
                "SKILLSHARE_CONFIG": str(config),
            },
            capture_output=True,
            text=True,
        )
    finally:
        config_dir.chmod(0o755)
    assert completed.returncode != 0
    assert "Failed to restore source" in completed.stderr
    assert "Restore manually by editing" in completed.stderr
    # The manual-restore hint must name the nested key skillshare actually
    # reads, not the shadowed legacy `source` key.
    assert "skills:" in completed.stderr
    assert "\n  source:" not in completed.stderr


def test_skillshare_exec_requires_a_command_before_switching_source(
    tmp_path: Path,
) -> None:
    executable = Path(__file__).resolve().parents[1] / "commands/skillshare-source"
    config_dir = tmp_path / "skillshare"
    config_dir.mkdir()
    config = config_dir / "config.yaml"
    config.write_text("source: /original\n")
    (config_dir / "sources.json").write_text(json.dumps({"temporary": "/temporary"}))

    completed = subprocess.run(
        [str(executable), "exec", "temporary", "--"],
        env={**os.environ, "SKILLSHARE_CONFIG": str(config)},
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "Missing argument 'cmd'." in completed.stderr
    assert config.read_text() == "source: /original\n"


@skip_as_root
def test_skillshare_exec_switch_failure_preserves_config(tmp_path: Path) -> None:
    executable = Path(__file__).resolve().parents[1] / "commands/skillshare-source"
    config_dir = tmp_path / "skillshare"
    config_dir.mkdir()
    config = config_dir / "config.yaml"
    original = tmp_path / "original"
    original_contents = f"source: {original}\nother: retained\n"
    config.write_text(original_contents)
    (config_dir / "sources.json").write_text(json.dumps({"temporary": "/temporary"}))
    tool_bin = tmp_path / "bin"
    tool_bin.mkdir()
    _write_executable(
        tool_bin / "skillshare",
        f'#!/bin/sh\nprintf \'%s\\n\' \'{{"source":{{"path":"{original}"}}}}\'\n',
    )

    config_dir.chmod(0o555)
    try:
        completed = subprocess.run(
            [str(executable), "exec", "temporary", "--", "true"],
            env={
                **os.environ,
                "PATH": f"{tool_bin}:{os.environ['PATH']}",
                "SKILLSHARE_CONFIG": str(config),
            },
            capture_output=True,
            text=True,
        )
    finally:
        config_dir.chmod(0o755)

    assert completed.returncode == 1
    assert "Failed to switch source" in completed.stderr
    assert "Traceback" not in completed.stderr
    assert config.read_text() == original_contents
    assert not list(config_dir.glob(".config.yaml.*"))


def test_skillshare_exec_preserves_symlinked_config(tmp_path: Path) -> None:
    executable = Path(__file__).resolve().parents[1] / "commands/skillshare-source"
    config_dir = tmp_path / "skillshare"
    config_dir.mkdir()
    actual_config = tmp_path / "shared/config.yaml"
    actual_config.parent.mkdir()
    original = "/original"
    actual_config.write_text(f"source: {original}\nother: retained\n")
    config = config_dir / "config.yaml"
    config.symlink_to(actual_config)
    (config_dir / "sources.json").write_text(json.dumps({"temporary": "/temporary"}))
    tool_bin = tmp_path / "bin"
    tool_bin.mkdir()
    _write_executable(
        tool_bin / "skillshare",
        f'#!/bin/sh\nprintf \'%s\\n\' \'{{"source":{{"path":"{original}"}}}}\'\n',
    )

    completed = subprocess.run(
        [str(executable), "exec", "temporary", "--", "true"],
        env={
            **os.environ,
            "PATH": f"{tool_bin}:{os.environ['PATH']}",
            "SKILLSHARE_CONFIG": str(config),
        },
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert config.is_symlink()
    # The round-trip migrates the legacy top-level key to sources.skills and
    # preserves unrelated keys; assert semantically, not byte-for-byte.
    content = actual_config.read_text()
    assert not any(line.startswith("source:") for line in content.splitlines())
    assert "skills: /original" in content
    assert "other: retained" in content


def test_skillshare_switch_writes_the_nested_sources_skills_key(
    tmp_path: Path,
) -> None:
    executable = Path(__file__).resolve().parents[1] / "commands/skillshare-source"
    config_dir = tmp_path / "skillshare"
    config_dir.mkdir()
    config = config_dir / "config.yaml"
    # Legacy top-level key on input; the switch must migrate to sources.skills,
    # the key skillshare actually reads, not leave a shadowed `source`.
    config.write_text("source: /original\nother: retained\n")
    (config_dir / "sources.json").write_text(
        json.dumps({"original": "/original", "temporary": "/temporary"})
    )
    tool_bin = tmp_path / "bin"
    tool_bin.mkdir()
    _write_executable(
        tool_bin / "skillshare",
        '#!/bin/sh\nprintf \'%s\\n\' \'{"source":{"path":"/original"}}\'\n',
    )

    completed = subprocess.run(
        [str(executable), "switch", "temporary"],
        env={
            **os.environ,
            "PATH": f"{tool_bin}:{os.environ['PATH']}",
            "SKILLSHARE_CONFIG": str(config),
        },
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    content = config.read_text()
    assert "  skills: /temporary" in content
    assert not any(line.startswith("source:") for line in content.splitlines())
    assert "other: retained" in content


def test_skillshare_add_preserves_symlinked_sources_registry(tmp_path: Path) -> None:
    executable = Path(__file__).resolve().parents[1] / "commands/skillshare-source"
    config_dir = tmp_path / "skillshare"
    config_dir.mkdir()
    config = config_dir / "config.yaml"
    config.write_text("source: /original\n")
    actual_registry = tmp_path / "shared/sources.json"
    actual_registry.parent.mkdir()
    actual_registry.write_text(json.dumps({"original": "/original"}))
    registry = config_dir / "sources.json"
    registry.symlink_to(actual_registry)
    added_source = tmp_path / "added"
    added_source.mkdir()

    completed = subprocess.run(
        [str(executable), "add", "added", str(added_source)],
        env={**os.environ, "SKILLSHARE_CONFIG": str(config)},
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert registry.is_symlink()
    assert json.loads(actual_registry.read_text()) == {
        "original": "/original",
        "added": str(added_source),
    }


REPO_ROOT = Path(__file__).resolve().parents[1]
BIN = REPO_ROOT / "commands"
SPECIAL_NAMES = [
    "space path",
    "single'quote",
    'double"quote',
    "back\\slash",
    "line\nbreak",
    "triple'''quote",
]


def _session_for(directory: Path) -> str:
    path = str(directory.resolve())
    base = re.sub(r"[^0-9A-Za-z]+", "_", Path(path).name).strip("_")
    digest = subprocess.run(
        ["git", "hash-object", "--stdin"],
        input=path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout[:8]
    return f"{base}-{digest}"


def test_link_reads_zellij_dump_screen_from_stdout(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    argv_log = tmp_path / "argv"
    _write_executable(
        fake_bin / "zellij",
        "#!/bin/bash\nprintf '%s\\0' \"$@\" >\"$ARGV_LOG\"\nprintf 'screen output'\n",
    )
    code = (
        "import importlib.machinery, importlib.util; "
        f"loader=importlib.machinery.SourceFileLoader('link', {str(BIN / 'link')!r}); "
        "spec=importlib.util.spec_from_loader('link', loader); "
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
        [BIN / "link"],
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
        [BIN / "link"],
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


def test_pi_tmux_requires_git(tmp_path: Path) -> None:
    completed = subprocess.run(
        ["/bin/bash", BIN / "pi-tmux"],
        cwd=tmp_path,
        env={**os.environ, "PATH": ""},
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 127
    assert completed.stdout == ""
    assert "git is required" in completed.stderr


def test_pmt_wraps_stdin_context_and_instructions() -> None:
    completed = subprocess.run(
        [sys.executable, BIN / "pmt", "hello", "world"],
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
    "mkbir",
    "o",
    "p",
    "pi-tmux",
    "ports",
    "repoprompt",
    "scratch",
    "zed-image-paste",
]
PYTHON_COMMANDS = [
    "autocorrect-text",
    "chatgpt",
    "get-codex-dump",
    "get-transcript",
    "link",
    "pi-session-export",
    "pmt",
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


@pytest.mark.parametrize("command", ["chatgpt", "pmt", "ttok"])
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


def test_mkbir_creates_bird_dirs_and_increments_counter(tmp_path: Path) -> None:
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
def test_pi_tmux_attaches_or_switches_to_existing_session(
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
        assert f"]({command})" in index
