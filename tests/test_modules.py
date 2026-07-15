import subprocess
from pathlib import Path


def test_skillshare_source_uses_a_descriptive_non_system_command_name() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    executable = repo_root / "modules/bin/skillshare-source"

    assert executable.is_file()
    assert not (repo_root / "modules/bin/ss").exists()

    completed = subprocess.run(
        [str(executable), "--version"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout.strip() == "skillshare-source 0.2.0"


def test_zsh_profile_reports_invalid_input_without_optional_gum(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    executable = repo_root / "scripts/zsh-profile"
    tool_bin = tmp_path / "bin"
    tool_bin.mkdir()
    for command in ("hyperfine", "uv", "zsh"):
        tool = tool_bin / command
        tool.write_text("#!/bin/sh\nexit 0\n")
        tool.chmod(0o755)
    # Real bash and dirname serve the script preamble; the bare PATH keeps an
    # optional host gum from hijacking the plain-error output this test pins.
    import shutil as _shutil

    for real in ("bash", "dirname"):
        source = _shutil.which(real)
        assert source is not None
        (tool_bin / real).symlink_to(source)

    completed = subprocess.run(
        [str(executable), "invalid"],
        env={"HOME": str(tmp_path), "PATH": str(tool_bin)},
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert completed.stderr.strip() == "error: runs must be an integer (got: invalid)"
