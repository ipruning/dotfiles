---
name: surge
description: "macOS network proxy diagnostics via Surge (China). Triggers: macOS + network hang/timeout (brew, npm, docker, curl), proxy misconfiguration, enhanced mode toggle. Not for Linux servers."
metadata:
  version: "1"
---

# Surge Skill

This machine is in mainland China. International traffic (GitHub, Homebrew, npm, Docker Hub, etc.) will fail without a proxy. Surge is the network control plane — it runs as a macOS app with a CLI and HTTP API.

## Two Proxy Layers

| Layer | Mechanism | Scope | Toggle |
|---|---|---|---|
| Shell env vars | `http_proxy`/`https_proxy`/`all_proxy` | Per-shell, only tools that respect env vars | `set-all-proxy` / `unset-all-proxy` (see below) |
| Surge Enhanced Mode | System-wide TUN (virtual NIC) | ALL traffic, every process | HTTP API only (see below) |

**Neither is always correct:**

- No proxy + no enhanced mode → international requests hang.
- Env vars set + Surge unhealthy → worse than no proxy (everything hangs on dead upstream).
- Enhanced mode on → great coverage but intercepts everything, breaks direct-connection debugging.

## Step 1: Diagnose Before Acting

Always check current state before changing anything:

```bash
# Network health (DNS, proxy RTT, UDP relay) — no auth needed
/Applications/Surge.app/Contents/Applications/surge-cli diagnostics

# What outbound mode? (0=direct, 1=global, 2=rule)
/Applications/Surge.app/Contents/Applications/surge-cli environment

# Shell proxy vars set?
env | grep -i proxy
```

## Step 2: Identify the Scenario

| Symptom | Likely Cause | Fix |
|---|---|---|
| `brew install` / `npm install` / `docker pull` hangs | No proxy for international traffic | Set shell proxy OR enable enhanced mode |
| `curl` to a remote server hangs despite proxy vars | Surge upstream is dead | Run `surge diagnostics`, check proxy RTT |
| Need direct connection (e.g. debugging latency to a server) | Enhanced mode is intercepting | Disable enhanced mode, unset proxy vars |
| Everything suddenly broken | Surge crashed or proxy nodes down | `surge diagnostics` first |
| Intermittent timeouts | Wrong outbound mode (direct instead of rule) | Switch outbound to `rule` |

## Surge CLI (no auth, always available)

The CLI is at `/Applications/Surge.app/Contents/Applications/surge-cli`, aliased as `surge`.

```bash
surge diagnostics              # full network health check
surge dump active              # active connections (process name, host, speed)
surge dump request             # recent 200 requests
surge dump dns                 # DNS cache
surge dump policy              # all proxies and policy groups
surge dump event               # event log
surge test-policy <name>       # test single proxy node latency
surge test-all-policies        # test ALL nodes
surge flush dns                # clear DNS cache
surge reload                   # reload config file
surge switch-profile <name>    # switch to another profile
surge watch request            # BLOCKING: live stream of all requests (use tmux)
surge --raw dump <subcommand>  # JSON output for scripting
```

## Surge HTTP API (required for toggling features)

The CLI **cannot** toggle features like enhanced mode — only the HTTP API can.

### Extract API Key

The key is in the Surge config file. Extract it inline:

```bash
x_key=$(perl -ne 'print $1 if /http-api = (.*?)@/' "$HOME/Library/Application Support/Surge/Profiles/default.conf")
```

### Toggle Operations

```bash
# Enhanced mode (system-wide TUN)
xh GET  https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key
xh POST https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key enabled:=true
xh POST https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key enabled:=false

# System proxy (macOS system-level HTTP proxy)
xh GET  https://localhost:6171/v1/features/system_proxy X-Key:$x_key
xh POST https://localhost:6171/v1/features/system_proxy X-Key:$x_key enabled:=true

# Outbound mode (rule / direct / proxy)
xh GET  https://localhost:6171/v1/outbound X-Key:$x_key
xh POST https://localhost:6171/v1/outbound X-Key:$x_key mode=rule
xh POST https://localhost:6171/v1/outbound X-Key:$x_key mode=direct

# Other toggleable features
xh GET https://localhost:6171/v1/features/mitm X-Key:$x_key
xh GET https://localhost:6171/v1/features/capture X-Key:$x_key
xh GET https://localhost:6171/v1/features/rewrite X-Key:$x_key
xh GET https://localhost:6171/v1/features/scripting X-Key:$x_key
```

### Other API Operations

```bash
# Reload profile
xh POST https://localhost:6171/v1/profiles/reload X-Key:$x_key

# Flush DNS
xh POST https://localhost:6171/v1/dns/flush X-Key:$x_key

# List modules
xh GET https://localhost:6171/v1/modules X-Key:$x_key

# Switch policy group selection
xh POST https://localhost:6171/v1/policy_groups/select X-Key:$x_key group_name='GroupName' policy='ProxyName'
```

## Common Operations

### Set/Unset Shell Proxy

```bash
# Set proxy (Surge listens on 6152/6153)
export http_proxy=http://127.0.0.1:6152
export https_proxy=http://127.0.0.1:6152
export all_proxy=socks5://127.0.0.1:6153

# Unset proxy
unset http_proxy https_proxy all_proxy
```

### Toggle Enhanced Mode

```bash
x_key=$(perl -ne 'print $1 if /http-api = (.*?)@/' "$HOME/Library/Application Support/Surge/Profiles/default.conf")
current=$(xh --body GET https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key | jq -r '.enabled')
if [ "$current" = "false" ]; then
  xh --quiet POST https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key enabled:=true
else
  xh --quiet POST https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key enabled:=false
fi
sleep 1
echo "Enhanced Mode: $(xh --body GET https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key | jq -r '.enabled')"
```

### Quick Status Check

```bash
x_key=$(perl -ne 'print $1 if /http-api = (.*?)@/' "$HOME/Library/Application Support/Surge/Profiles/default.conf")
echo "Outbound:      $(xh --body GET https://localhost:6171/v1/outbound X-Key:$x_key | jq -r '.mode')"
echo "System Proxy:  $(xh --body GET https://localhost:6171/v1/features/system_proxy X-Key:$x_key | jq -r '.enabled')"
echo "Enhanced Mode: $(xh --body GET https://localhost:6171/v1/features/enhanced_mode X-Key:$x_key | jq -r '.enabled')"
```

## File Locations

- Surge app: `/Applications/Surge.app/`
- Surge CLI: `/Applications/Surge.app/Contents/Applications/surge-cli` (aliased as `surge`)
- Config profiles: `~/Library/Application Support/Surge/Profiles/`
- Primary config: `~/Library/Application Support/Surge/Profiles/default.conf`
- Config repo AGENTS.md: `~/Library/Application Support/Surge/AGENTS.md`
- Shell helpers (if available): `~/dotfiles/modules/zsh/surge.zsh`

## Gotchas

- `xh` is required for API calls. It's a Rust httpie clone installed via mise/brew.
- `jq` is required for JSON parsing in the inline scripts.
- The API uses HTTPS with a self-signed cert (`http-api-tls = true`). `xh` handles this fine.
- The API key changes per config file — always extract it dynamically, never hardcode.
- Surge proxy ports: HTTP = `6152`, SOCKS5 = `6153`, API = `6171`.
- Enhanced mode takes ~1 second to fully activate — add `sleep 1` before checking status.
