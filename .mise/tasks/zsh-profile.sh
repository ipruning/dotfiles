#!/usr/bin/env bash
#MISE description="Profile zsh startup time"
#MISE alias="zp"

set -euo pipefail

RUNS="${1:-50}"
WARMUP="${2:-10}"
TRACE_FILE=""

cleanup() { [[ -n "$TRACE_FILE" && -f "$TRACE_FILE" ]] && rm -f "$TRACE_FILE"; true; }
trap cleanup EXIT

# Clean up any old trace files first
rm -f /tmp/zsh_profile_*.log

printf "\033[34m==> Benchmarking zsh startup (%d runs, %d warmup)...\033[0m\n" "$RUNS" "$WARMUP"
hyperfine "zsh -i -c exit" --warmup "$WARMUP" --runs "$RUNS"

printf "\n\033[34m==> Generating trace profile (interactive shell)...\033[0m\n"
TRACE_FILE="/tmp/zsh_profile_$$.log"
ZSH_TRACE_STARTUP=1 ZSH_TRACE_FILE="$TRACE_FILE" zsh -i -c exit 2>&1

if [[ ! -f "$TRACE_FILE" ]]; then
  echo "Error: No trace file found at $TRACE_FILE. Ensure ~/.zshrc has the ZSH_TRACE_STARTUP hook."
  exit 1
fi

python3 - "$TRACE_FILE" << 'PYEOF'
import re
import sys
from collections import defaultdict

trace_file = sys.argv[1]

times = []
with open(trace_file, 'r') as f:
    for line in f:
        match = re.match(r'\+(\d+\.\d+)> (.+)', line)
        if match:
            times.append((float(match.group(1)), match.group(2)[:120]))

if len(times) < 2:
    print("No trace data found")
    sys.exit(1)

total_ms = (times[-1][0] - times[0][0]) * 1000

print("\n\033[34m=== TOP 20 Slowest Commands ===\033[0m")
durations = []
for i in range(len(times)-1):
    dur = (times[i+1][0] - times[i][0]) * 1000
    durations.append((dur, times[i][1]))

for dur, cmd in sorted(durations, key=lambda x: -x[0])[:20]:
    if dur >= 5:
        color = "\033[31m"  # red
    elif dur >= 1:
        color = "\033[33m"  # yellow
    else:
        color = "\033[0m"
    print(f"{color}{dur:8.2f} ms\033[0m | {cmd[:70]}")

keywords = [
    'brew', 'mise', 'atuin', 'starship', 'zoxide', 'compinit', 'zcompdump',
    'fzf', 'ftb', 'fast-syntax', 'FAST_HIGHLIGHT', 'autosuggestions'
]

cats = defaultdict(float)
for dur, cmd in durations:
    cmd_lower = cmd.lower()
    for kw in keywords:
        if kw.lower() in cmd_lower:
            if kw in ['compinit', 'zcompdump']:
                cats['compinit'] += dur
            elif kw in ['fzf', 'ftb']:
                cats['fzf-tab'] += dur
            elif kw in ['fast-syntax', 'FAST_HIGHLIGHT']:
                cats['syntax-hl'] += dur
            elif kw == 'autosuggestions':
                cats['autosuggestions'] += dur
            else:
                cats[kw] += dur
            break

print(f"\n\033[34m=== Total (trace): {total_ms:.1f} ms ===\033[0m")
print("\033[90mNote: xtrace adds overhead; treat values as relative, not absolute.\033[0m")
print("\n\033[34m=== By Category ===\033[0m")
for c, t in sorted(cats.items(), key=lambda x: -x[1]):
    pct = t / total_ms * 100
    if pct >= 10:
        color = "\033[31m"
    elif pct >= 5:
        color = "\033[33m"
    else:
        color = "\033[0m"
    print(f"{color}{t:7.1f} ms ({pct:4.1f}%)\033[0m | {c}")

other = total_ms - sum(cats.values())
print(f"{other:7.1f} ms ({other/total_ms*100:4.1f}%) | other")
PYEOF

rm -f "$TRACE_FILE"
