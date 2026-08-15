"""Host-owned policy that can make this repository audit-only."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

POLICY_RELATIVE_PATH = Path(".config/dotfiles/policy.toml")
MANAGED_MODE = "managed"
AUDIT_ONLY_MODE = "audit-only"


class HostPolicyError(RuntimeError):
    """The host policy is invalid or refuses the requested mutation."""

    code = "host_policy.invalid"


class HostPolicyMutationError(HostPolicyError):
    """The valid host policy refuses repository-owned mutation."""

    code = "host_policy.audit_only"


@dataclass(frozen=True)
class HostPolicy:
    mode: str = MANAGED_MODE
    mise_path: Path | None = None

    @property
    def audit_only(self) -> bool:
        return self.mode == AUDIT_ONLY_MODE


def host_policy_path(home: Path) -> Path:
    return home / POLICY_RELATIVE_PATH


def _configured_path(value: object, *, home: Path, field: str) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise HostPolicyError(f"host policy {field} must be a non-empty path string")
    if value == "~":
        path = home
    elif value.startswith("~/"):
        path = home / value[2:]
    else:
        path = Path(value)
    if not path.is_absolute():
        raise HostPolicyError(
            f"host policy {field} must be an absolute or home-relative path"
        )
    return path


def load_host_policy(home: Path) -> HostPolicy:
    """Load the machine-local policy; an absent file keeps normal managed mode."""
    path = host_policy_path(home)
    try:
        with path.open("rb") as policy_file:
            document = tomllib.load(policy_file)
    except FileNotFoundError:
        return HostPolicy()
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise HostPolicyError(f"cannot read host policy {path}: {error}") from error

    unknown_fields = set(document) - {"mode", "mise_path"}
    if unknown_fields:
        fields = ", ".join(sorted(unknown_fields))
        raise HostPolicyError(f"host policy contains unknown fields: {fields}")
    mode = document.get("mode", MANAGED_MODE)
    if not isinstance(mode, str) or mode not in {MANAGED_MODE, AUDIT_ONLY_MODE}:
        raise HostPolicyError(
            f"host policy mode must be {MANAGED_MODE!r} or {AUDIT_ONLY_MODE!r}"
        )
    return HostPolicy(
        mode=mode,
        mise_path=_configured_path(
            document.get("mise_path"),
            home=home,
            field="mise_path",
        ),
    )


def configured_mise_path(home: Path) -> Path | None:
    """Return the host-selected Mise path without hiding an invalid policy."""
    return load_host_policy(home).mise_path


def require_mutation_allowed(home: Path) -> None:
    policy = load_host_policy(home)
    if policy.audit_only:
        path = host_policy_path(home)
        raise HostPolicyMutationError(
            f'{path} sets mode = "{AUDIT_ONLY_MODE}"; mutating dotfiles operations '
            "are disabled on this host"
        )
