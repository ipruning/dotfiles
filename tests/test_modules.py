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
