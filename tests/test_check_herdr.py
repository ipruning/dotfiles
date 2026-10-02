import hashlib
import platform
from pathlib import Path

from scripts.check_herdr import inspect_herdr


def test_herdr_pinned_symlink_is_one_owner(tmp_path: Path) -> None:
    binary = tmp_path / ".local/share/mise/installs/herdr/0.9.1/herdr"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"locked binary")
    launcher = tmp_path / ".local/bin/herdr"
    launcher.parent.mkdir(parents=True)
    launcher.symlink_to(binary)
    assert inspect_herdr(tmp_path, system_paths=()) == []


def test_herdr_reports_independent_installs_without_removing_them(
    tmp_path: Path,
) -> None:
    binary = tmp_path / ".local/share/mise/installs/herdr/0.9.1/herdr"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"mise binary")
    brew = tmp_path / "brew/Cellar/herdr/0.9.2/bin/herdr"
    brew.parent.mkdir(parents=True)
    brew.write_bytes(b"brew binary")
    launcher = tmp_path / "brew/bin/herdr"
    launcher.parent.mkdir(parents=True)
    launcher.symlink_to(brew)
    findings = inspect_herdr(tmp_path, system_paths=(launcher,))
    assert [finding.code for finding in findings] == ["herdr.multiple_owners"]
    assert "Homebrew" in findings[0].message
    assert binary.read_bytes() == b"mise binary"
    assert launcher.is_symlink()


def test_herdr_reports_binary_changed_inside_locked_directory(tmp_path: Path) -> None:
    binary = tmp_path / ".local/share/mise/installs/herdr/0.9.0/herdr"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"different version")
    target = (
        "macos-arm64"
        if platform.system() == "Darwin" and platform.machine() == "arm64"
        else "macos-x64"
        if platform.system() == "Darwin"
        else "linux-arm64"
        if platform.machine() in {"aarch64", "arm64"}
        else "linux-x64"
    )
    checksum = hashlib.sha256(b"original locked version").hexdigest()
    lock = tmp_path / ".config/mise/mise.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text(
        '[[tools.herdr]]\nversion = "0.9.0"\n'
        f'[tools.herdr."platforms.{target}"]\nchecksum = "sha256:{checksum}"\n'
    )
    findings = inspect_herdr(tmp_path, system_paths=())
    assert [finding.code for finding in findings] == ["herdr.checksum_mismatch"]
    assert findings[0].path == binary
    assert binary.read_bytes() == b"different version"
