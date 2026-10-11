"""Native CLI self-updaters and the install roots that prove their ownership."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from .update_models import UpdateStep

MANAGER_ROOTS = (Path("/opt/homebrew"), Path("/usr/bin"))


@dataclass(frozen=True)
class NativeUpdater:
    step: UpdateStep
    # Home-relative paths; the resolved executable must live under one of them.
    roots: tuple[str, ...]


def native_updaters(home: Path) -> tuple[NativeUpdater, ...]:
    local_bin = str(home / ".local/bin")
    return (
        NativeUpdater(
            UpdateStep(
                "sprite.version",
                "sprite",
                ("sprite", "upgrade"),
                300,
                # `sprite upgrade` treats a declined/closed prompt as exit 0. An
                # explicit update --apply is the operator's confirmation, so feed
                # the affirmative response instead of reporting a no-op as success.
                stdin_text="y\n",
            ),
            (".local/bin",),
        ),
        NativeUpdater(UpdateStep("amp", "amp", ("amp", "update"), 300), (".amp/bin",)),
        NativeUpdater(
            UpdateStep(
                "claude",
                "claude",
                ("claude", "update"),
                # Let Claude's updater own its download deadline and report its
                # actual error instead of killing a valid slow download at 5m.
                1800,
                failure_note=(
                    "retry `claude update`; failed downloads may remain under "
                    f"{home}/.cache/claude/staging and "
                    f"{home}/.local/share/claude/versions and are not cleaned "
                    "automatically"
                ),
            ),
            (".local/share/claude/versions",),
        ),
        NativeUpdater(
            UpdateStep(
                "tigris",
                "tigris",
                ("tigris", "update"),
                300,
                # `tigris update` re-runs the official install.sh, which defaults
                # to the root-owned /usr/local/bin (sudo prompt), edits shell
                # profiles outside that default, and writes
                # ~/.claude/skills/tigris whenever ~/.claude exists. Pin the user
                # install, skip profile edits, and give the installer an empty
                # HOME so Dotfiles never writes global harness skills.
                environment=(
                    ("TIGRIS_INSTALL_DIR", local_bin),
                    ("TIGRIS_SKIP_PATH", "1"),
                    ("HOME", "/var/empty"),
                ),
            ),
            (".local/bin",),
        ),
        NativeUpdater(
            UpdateStep("herdr", "herdr", ("herdr", "update"), 900),
            (".local/bin/herdr",),
        ),
        NativeUpdater(
            UpdateStep("pi", "pi", ("pi", "update"), 1800),
            (".pi/agent/install", ".pi/agent/bin"),
        ),
        NativeUpdater(
            UpdateStep("pi.extensions", "pi", ("pi", "update", "--extensions"), 300),
            (".pi/agent/install", ".pi/agent/bin"),
        ),
        NativeUpdater(
            UpdateStep("codex", "codex", ("codex", "update"), 900),
            (".codex/packages/standalone",),
        ),
        NativeUpdater(
            UpdateStep(
                "droid",
                "droid",
                ("droid", "update"),
                900,
                # Standalone droid builds default autoUpdateEnabled to false and
                # then exit 0 with npm advice, so enable the native updater.
                environment=(("FACTORY_DROID_AUTO_UPDATE_ENABLED", "true"),),
            ),
            (".local/bin",),
        ),
        NativeUpdater(
            UpdateStep("grok", "grok", ("grok", "update"), 600),
            (".grok",),
        ),
        NativeUpdater(
            UpdateStep(
                "claude-science",
                "claude-science",
                ("claude-science", "update"),
                900,
            ),
            (".claude-science/bin",),
        ),
        NativeUpdater(
            UpdateStep("ntn", "ntn", ("ntn", "update"), 300),
            (".local/bin",),
        ),
        NativeUpdater(
            UpdateStep("rotom", "rotom", ("rotom", "update"), 300),
            (".local/bin",),
        ),
        NativeUpdater(
            UpdateStep("jh", "jh", ("jh", "upgrade"), 300),
            (".local/bin",),
        ),
    )


def resolve_native_step(
    step: UpdateStep, roots: tuple[str, ...], home: Path, resolved: str
) -> tuple[UpdateStep, str | None]:
    """Bind the step to its executable, or return why self-update must be skipped."""
    path = Path(resolved)
    target = path.resolve()
    mise_root = home / ".local/share/mise"
    if (
        target.is_relative_to(mise_root)
        or path.is_relative_to(mise_root)
        or "Cellar" in target.parts
        or any(target.is_relative_to(root) for root in MANAGER_ROOTS)
    ):
        return step, (f"{path} is package-manager owned; native self-update is skipped")
    home_root = home.resolve()
    if not any(target.is_relative_to(home_root / root) for root in roots):
        return step, (
            f"{path} has no verified native owner; inspect its installation "
            "before self-update"
        )
    return replace(step, command=(str(path), *step.command[1:])), None
