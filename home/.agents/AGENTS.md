# Skills Directory

AI agent skills (SKILL.md files) for Amp/Claude Code. Each subdirectory is a standalone skill.

## Structure

- `surge/SKILL.md` — macOS Surge proxy diagnostics (China network). Covers shell proxy vars, Enhanced Mode toggle via HTTP API, and CLI diagnostics.
- `vps/SKILL.md` — Linux VPS security audit, hardening, and maintenance SOPs for Debian/Ubuntu. Covers SSH, nftables, fail2ban, patching.

## Conventions

- Each skill lives in its own directory with a single `SKILL.md`.
- SKILL.md frontmatter uses YAML (`name`, `description`, `metadata.version`).
- Write in imperative, runbook style: diagnose → identify scenario → act → verify.
- Use fenced code blocks for all commands. Group by phase (read-only audit vs. apply).
- Prefer concrete commands over prose. Include flags for non-interactive/automated use.
- Security: never hardcode secrets or API keys — always extract dynamically.

## Build / Test

- No build or test tooling. Skills are plain Markdown — validate by reading.
- Parent repo uses `mise` for tasks; see `~/dotfiles/AGENTS.md` for repo-wide guidance.

## Adding a New Skill

- Create `<skill-name>/SKILL.md` with YAML frontmatter (`name`, `description`, `metadata.version`).
- Use the `building-skills` Amp skill for the canonical structure and naming rules.
- Keep scope narrow — one skill per domain. Split if a skill exceeds ~200 lines.
