"""Host profiles shared by inspection and explicit setup commands."""

from __future__ import annotations

import platform
from enum import StrEnum


class HostProfile(StrEnum):
    AUTO = "auto"
    LINUX_LITE = "linux-lite"
    MACOS = "macos"
    FULL = "full"


LINUX_LITE_APPLICATIONS = frozenset({"git", "mise", "skillshare"})


def resolve_profile(
    profile_name: str | HostProfile,
    system_name: str | None = None,
) -> HostProfile:
    """Resolve auto to the smallest useful profile for the active platform."""
    requested = HostProfile(profile_name)
    if requested is not HostProfile.AUTO:
        return requested
    active_system = system_name or platform.system()
    return HostProfile.LINUX_LITE if active_system == "Linux" else HostProfile.MACOS


def profile_applications(profile: HostProfile) -> frozenset[str] | None:
    """Return the Mackup applications relevant to a profile, or all applications."""
    if profile is HostProfile.LINUX_LITE:
        return LINUX_LITE_APPLICATIONS
    return None
