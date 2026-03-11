---
name: prek
description: "Optimize prek (pre-commit) hook configuration: priority-based parallelism, pass_filenames tuning, startup overhead reduction, and benchmarking. Triggers: prek, pre-commit optimization, hook performance, priority tuning."
metadata:
  version: "1"
---

# Optimizing prek Hooks

Guide for configuring, testing, and optimizing prek (pre-commit) hooks for maximum speed and correctness.

## Core Concepts

### Priority-Based Parallelism

prek runs hooks concurrently when they share the same `priority` value. Different priorities run sequentially from lowest to highest.

```toml
# Hooks at priority 20 run concurrently with each other
{ id = "ruff-check", priority = 20 }
{ id = "typos", priority = 20 }
# This hook waits for all priority-20 hooks to finish first
{ id = "integration-test", priority = 30 }
```

**Key rule: splitting a parallel group into sequential phases is never faster.** `max(A) + max(B) >= max(A ∪ B)`. Keep all independent checks at the same priority unless there is a correctness reason to separate them.

### Three Hook Categories

| Category | Behavior | Priority Strategy |
|---|---|---|
| Gate checks | Fast, fail-fast guards (branch protection, email check) | Lowest priority (e.g., 0), concurrent |
| Fixers | Modify files in place (trailing-whitespace, end-of-file-fixer) | Each gets a **unique** priority (e.g., 10, 11, 12) to avoid write conflicts |
| Read-only checks | Lint, type-check, scan | All share the **same** priority (e.g., 20), fully concurrent |

Fixers **must** run before checks so that checks validate the fixed state.

## Configuration Patterns

### Official Repo Hooks vs Local System Hooks

Prefer official pre-commit repo hooks when available. They manage their own toolchain and are faster.

```toml
# ✅ Official repo — manages its own ruff binary
[[repos]]
repo = "https://github.com/astral-sh/ruff-pre-commit"
rev = "v0.15.4"
hooks = [{ id = "ruff-check" }]

# ❌ Local system hook — slower due to mise/uv startup overhead
[[repos]]
repo = "local"
hooks = [{ id = "ruff", entry = "mise exec -- uv run ruff check .", language = "system" }]
```

### Check-Only vs Auto-Fix

Format hooks in official repos often **modify files by default**. For pre-commit (check-only) use, add `--check`:

```toml
# ruff-format default: formats in place
# Add --check for pre-commit: only report, don't modify
{ id = "ruff-format", args = ["--check"] }
```

Verify with: commit a badly formatted file, run the hook, then check `git status` and file hash — no changes should appear.

### pass_filenames Tuning

| Scenario | Setting | Why |
|---|---|---|
| Tool needs full-project context (type checkers like ty, mypy) | `pass_filenames = false` | Must analyze cross-file dependencies |
| Tool has high startup overhead (Node.js-based: markdownlint, eslint) | `pass_filenames = false` | Avoids N × startup cost from file batching |
| Tool is fast per-file, low startup (ruff, typos, shellcheck, ripsecrets) | `pass_filenames = true` (default) | Incremental: only checks changed files |

**Pitfall**: prek splits file lists into batches when they exceed OS command-line length limits. Each batch triggers a separate process. For Node.js tools (~1s startup), 12 batches = 12s instead of 1.2s.

### types Filter for Skipping

Use `types` to skip hooks when no relevant files changed:

```toml
# Only triggers when Python files are in the changeset
{ id = "ty", types = ["python"], pass_filenames = false }
# Only triggers when shell scripts are in the changeset
{ id = "shellcheck", types = ["shell"] }
```

Remove `always_run = true` when adding `types` — they are mutually exclusive in intent.

### Removing Wrapper Overhead

Each wrapper layer adds startup latency:

```
mise exec -- uv run ty check .    # ~4.2s (mise + uv overhead)
uv run ty check .                 # ~2.5s (uv overhead only)
.venv/bin/ty check .              # ~1.7s (direct, fastest)
ty check .                        # ~1.7s (if on PATH)
```

For hooks in prek, the environment is already set up. Prefer direct invocation:

```toml
# ❌ Slow
entry = "mise exec -- uv run ty check ."
# ✅ Fast
entry = "uv run ty check ."
# ✅ Fastest (if tool is on PATH)
entry = "ty check ."
```

### Hidden Files (.dotfiles)

Some tools skip dotfiles by default (e.g., `autocorrect --fix .` skips `.agents/`, `.mise/`). But prek passes individual file paths including dotfiles.

**Symptom**: hook fails in prek but passes when run manually.
**Fix**: explicitly include dotfile directories in manual/CI commands:

```bash
autocorrect --fix . .agents/ .mise/
autocorrect --lint . .agents/ .mise/
```

### require_serial Clarification

`require_serial = true` controls **within-hook** file batching (one batch at a time), NOT inter-hook exclusivity. A `require_serial` hook still runs concurrently with other hooks at the same priority. For true exclusivity, assign a unique priority.

## Testing Workflow

### 1. Validate Configuration

```bash
prek validate-config
prek run --all-files --dry-run    # Check ordering without executing
```

### 2. Trigger Test

Create a file that violates the hook, commit with `--no-verify`, then test:

```bash
# Create violation
cat > _test.py << 'EOF'
import os          # unused import (F401)
x = {  "a":1}     # bad formatting
EOF

# Commit without hooks
git add _test.py && git commit --no-verify -m "test"

# Record file hash
md5sum _test.py

# Run specific hooks
prek run ruff-check --all-files
prek run ruff-format --all-files

# Verify no file modification (check-only mode)
md5sum _test.py           # Must match
git status --short        # Must show no unstaged changes
git diff                  # Must be empty

# Clean up
git reset HEAD~1 --hard
```

### 3. Benchmark

```bash
# Baseline
hyperfine 'prek run --all-files'

# After changes
hyperfine 'prek run --all-files'

# Compare two configurations
hyperfine 'prek run --all-files' --warmup 1 --runs 5

# With verbose output to identify bottlenecks
time prek run --all-files --verbose
```

### 4. Analyze Parallelism

From `--verbose` output, check:

- **Wall time vs sum of durations**: high ratio = good parallelism
- **CPU usage** (`time` output): 400%+ means multi-core utilization
- **Bottleneck hook**: the slowest hook in a priority group determines that group's wall time

### 5. Per-Hook Profiling

Measure bare execution time and CPU intensity:

```bash
time <tool> <args>
```

CPU intensity = user time / wall time:

- `> 300%`: CPU-heavy (ty, ripsecrets, ast-grep)
- `50-150%`: IO-bound (typos, markdownlint, ls-lint)
- `< 50%`: lightweight (check-yaml, detect-private-key)

## Common Pitfalls

1. **Format hooks modify files**: Always add `--check` to format hooks in pre-commit. Without it, hooks silently rewrite staged files, creating unstaged changes.
2. **Node.js batch explosion**: Tools like markdownlint-cli2 with default `pass_filenames = true` get split into many batches. Each Node.js startup costs ~1s. Use `pass_filenames = false`.
3. **Priority splitting fallacy**: Splitting checks into CPU-heavy (priority 20) and IO-bound (priority 21) groups is **always slower** than running everything at the same priority. The math: `max(group_A) + max(group_B) >= max(all_together)`.
4. **`always_run` with `types`**: Using both is contradictory. `always_run = true` overrides `types` filtering. Pick one.
5. **Stale tool versions**: Official repo hooks pin their own tool version via `rev`. Local system hooks use whatever is on PATH — version skew can cause CI vs local differences.
6. **Hidden file mismatch**: prek passes dotfile paths to hooks, but some tools skip dotfiles when run manually with `.` as argument. This causes "passes locally, fails in prek" or vice versa.
7. **`mise exec` overhead in hooks**: Each `mise exec --` adds ~1-2s of startup. Since prek already runs in an activated environment, the wrapper is unnecessary.

## Recommended Priority Layout

```toml
# Priority 0:  Gate checks (instant, fail-fast)
# Priority 10: Fixer A (modifies files)
# Priority 11: Fixer B (modifies files)
# Priority 12: Fixer C (modifies files)
# Priority 20: ALL read-only checks (maximum concurrency)
```
