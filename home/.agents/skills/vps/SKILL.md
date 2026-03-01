---
name: vps
description: "Linux VPS/server security audit, hardening, and maintenance. Triggers: remote Linux host + SSH hardening, firewall rules, Debian/Ubuntu patching, unknown server audit, fail2ban, unattended-upgrades. Not for macOS."
metadata:
  version: "1"
---

# VPS Security & Maintenance Manual

Debian/Ubuntu server hardening and routine maintenance SOP for AI agents.

All commands use `apt-get` for script stability (not `apt`, which is designed for interactive use), include dpkg conffile flags to prevent prompts, and are safe for automated execution.

## General Principles

1. **Always have a fallback path.** Before modifying SSH, firewall, or network settings, confirm you have out-of-band access via cloud console, rescue system, or KVM. At minimum, keep a second login path open such as Tailscale or a separate SSH session. Use `tmux` to survive disconnects.

2. **Read before write.** First round is read-only: collect ports, SSH effective config, firewall rules, service list, cron jobs, and patch status. When modifying, go smallest blast radius first: SSH → firewall → anti-brute-force → updates → sysctl. Verify after each step.

3. **Verify with runtime state, not config files.**
   - SSH: `sshd -T` shows the global merged config without Match blocks applied. Use `sshd -T -C user=...,addr=...,host=...` to see what config a specific connection would get after Match rules activate.
   - Firewall: `nft list ruleset`, `iptables -S`, and `ip6tables -S` show actual loaded rules. Always check IPv6 separately.
   - Services: `systemctl status` + `ss -tlnup` confirms what is actually listening.

4. **Cross-version upgrades require human approval.** This SOP covers same-version patch upgrades only. Upgrading across Debian/Ubuntu major versions requires source list changes, release notes review, third-party repo compatibility checks, and explicit human sign-off.

## 1. Routine Maintenance Checklist

### 1.1 Pre-Maintenance

Identity, uptime, and kernel version:

```bash
whoami && id && date && uptime && uname -r
```

Disk, memory, and CPU snapshot. Abort if resources are tight on `/`, `/var`, or `/boot`:

```bash
df -h && free -h && top -bn1 -o %CPU | head -20
```

Failed services and listening ports:

```bash
systemctl --failed --no-pager
ss -tlnup
```

SSH drift scan — check global effective config and detect Match blocks that may override it:

```bash
sshd -T | grep -E 'permitrootlogin|passwordauthentication|kbdinteractiveauthentication|x11forwarding|port|allowusers|allowgroups|permituserrc'
grep -i '^Match' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null
```

If Match blocks exist, inspect what a specific connection would see:

```bash
sshd -T -C user=root,addr=0.0.0.0,host= | grep -E 'permitrootlogin|passwordauthentication'
```

Firewall still matches expectations:

```bash
nft list ruleset 2>/dev/null | head -50
```

fail2ban operational:

```bash
systemctl is-active fail2ban && fail2ban-client status sshd
```

Preview pending upgrades before applying:

```bash
apt-get update
apt-get -s upgrade | head -50
```

### 1.2 During Maintenance

Apply upgrades non-interactively. The conffile flags prevent dpkg from prompting on config file conflicts by keeping the existing version:

```bash
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get -y \
  -o Dpkg::Options::=--force-confdef \
  -o Dpkg::Options::=--force-confold \
  upgrade
```

For dependency changes within the same release, replace `upgrade` with `full-upgrade` above. Cross-version upgrades are out of scope for automated execution — escalate to human.

Check needrestart version before use. Versions below 3.8 have local privilege escalation vulnerabilities (CVE-2024-48990) where an attacker controlling `PYTHONPATH` can execute code as root. Pin to list-only mode explicitly:

```bash
needrestart --version
NEEDRESTART_MODE=l needrestart -r l
```

Check if kernel reboot is needed by comparing running vs installed kernel:

```bash
echo "Running: $(uname -r)" && echo "Installed: $(dpkg -l "linux-image-$(dpkg --print-architecture)" 2>/dev/null | awk '/^ii/{print $3}')"
```

If they differ, schedule a reboot at a suitable window.

### 1.3 Post-Maintenance

Verify no services broke:

```bash
systemctl --failed --no-pager
ss -tlnup
```

Scan recent error logs for post-upgrade crashes:

```bash
journalctl -p err..alert -b --no-pager | tail -200
journalctl -u ssh -b --no-pager | tail -100
```

Review upgrade logs for evidence chain:

```bash
ls -lt /var/log/apt/history.log* 2>/dev/null | head -5
tail -100 /var/log/apt/history.log
ls -lt /var/log/unattended-upgrades/ 2>/dev/null
```

Confirm automatic updates remain enabled:

```bash
systemctl is-enabled unattended-upgrades
systemctl list-timers --no-pager 'apt-daily*'
```

## 2. Unknown Server Initial Audit

Goal: establish facts about exposure, access, persistence, and patching before deciding what to fix.

### 2.1 Preparation

Create a detached tmux session as a safety net. Keep a second SSH session or console as fallback:

```bash
tmux new -d -s audit
```

### 2.2 System Identification

```bash
cat /etc/os-release && uname -a && uptime && hostnamectl && timedatectl
```

### 2.3 Access & Account Audit

Current user:

```bash
whoami && id
```

Root password status — is password login possible:

```bash
passwd -S root
```

Users with login shells:

```bash
grep -v 'nologin\|false' /etc/passwd
```

SSH authorized keys — the most common backdoor vector is injected keys:

```bash
ls -la /root/.ssh 2>/dev/null
cat /root/.ssh/authorized_keys 2>/dev/null
for d in /home/*/; do echo "=== $d ===" && cat "${d}.ssh/authorized_keys" 2>/dev/null; done
```

Scan for dangerous key options. Backdoors often use `command=`, `from=`, or `environment=` prefixes to execute code or restrict visibility:

```bash
grep -nE 'command=|from=|environment=|permitopen=|tunnel=|principals=' /root/.ssh/authorized_keys 2>/dev/null
for f in /home/*/.ssh/authorized_keys; do
  echo "=== $f ===" && grep -nE 'command=|from=|environment=|permitopen=|tunnel=|principals=' "$f" 2>/dev/null
done
```

### 2.4 SSH Effective Configuration

`sshd -T` shows the global merged config but does not apply Match blocks. Match rules can silently override global settings per user, address, or host — this is where backdoor-style configs hide. Use `-C` to simulate a specific connection:

```bash
sshd -T | grep -E 'port|listenaddress|permitrootlogin|passwordauthentication|pubkeyauthentication|kbdinteractiveauthentication|x11forwarding|allowusers|allowgroups|authenticationmethods|permituserrc'

grep -i '^Match' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null

sshd -T -C user=root,addr=0.0.0.0,host= | grep -E 'permitrootlogin|passwordauthentication|permituserrc'

ls -la /etc/ssh/sshd_config.d/ 2>/dev/null
```

Key questions: Is root direct login allowed? Is password auth enabled? Are there Match blocks that relax security for specific users or addresses? Is PermitUserRC enabled (allows `~/.ssh/rc` execution on login)?

### 2.5 Network Exposure

Listening ports — always check both TCP and UDP:

```bash
ss -tlnp
ss -ulnp
```

IP addresses, routes, DNS, and IPv6. IPv6 is often overlooked and left wide open:

```bash
ip addr && ip route && ip -6 addr && cat /etc/resolv.conf
```

Firewall rules — check nftables, IPv4, and IPv6 separately. If the system uses legacy iptables instead of nft, the IPv6 rules are managed independently by ip6tables:

```bash
nft list ruleset 2>/dev/null
iptables -S 2>/dev/null
ip6tables -S 2>/dev/null
```

Cloud providers may have an additional security group layer. Check the cloud console separately.

### 2.6 Running Services

```bash
systemctl list-units --type=service --state=running --no-pager
systemctl list-unit-files --state=enabled --no-pager
ps auxf --sort=-%cpu | head -50
```

Look for: proxies, tunnels, miners, unfamiliar daemons, suspicious systemd unit names.

### 2.7 Persistence Mechanisms

The most critical part of an unknown server audit.

Cron jobs — system and user level:

```bash
crontab -l 2>/dev/null
ls -la /etc/cron.d/ /etc/cron.daily/ /etc/cron.hourly/ 2>/dev/null
```

Systemd timers:

```bash
systemctl list-timers --all --no-pager
```

Custom systemd units — common hiding spot for backdoors:

```bash
ls -la /etc/systemd/system/
```

User-level systemd units. Miners and reverse shells often hide here to survive reboots without needing root:

```bash
for d in /home/*/; do
  echo "=== ${d} ===" && ls -la "${d}.config/systemd/user/" 2>/dev/null
done
ls -la /root/.config/systemd/user/ 2>/dev/null
```

Login shell persistence and SSH rc scripts. Code in these files runs on every login:

```bash
for d in /home/*/; do
  echo "=== ${d} ===" && ls -la "${d}.ssh/rc" 2>/dev/null
done
ls -la /root/.ssh/rc 2>/dev/null
```

SUID binaries and capabilities — requires experience to distinguish normal from suspicious:

```bash
find /usr/bin /usr/sbin /bin /sbin -perm /6000 -type f 2>/dev/null | sort
getcap -r / 2>/dev/null | head -200
```

### 2.8 Patch Status

Configured package sources:

```bash
ls -la /etc/apt/sources.list.d/
cat /etc/apt/sources.list.d/*.sources 2>/dev/null
```

Upgradable packages:

```bash
apt-get update
apt-get -s upgrade | head -50
```

Automatic security updates:

```bash
systemctl is-enabled unattended-upgrades 2>/dev/null
systemctl list-timers --no-pager 'apt-daily*'
```

### 2.9 Log Analysis

Check for active brute-force or anomalous logins in the last 24 hours:

```bash
journalctl -u ssh --since "24 hours ago" --no-pager | tail -200
last -20
lastb -20 2>/dev/null
```

### 2.10 Remediation Priority

After the read-only audit, fix in this order:

1. **SSH** — disable password auth, restrict root login to key-only, limit source IPs, set `PermitUserRC no`
2. **Firewall** — default drop policy, whitelist only required ports, align TCP + UDP + IPv6 with actual listeners
3. **Anti-brute-force** — fail2ban or CrowdSec
4. **Updates** — enable unattended-upgrades, verify apt-daily timers fire, configure needrestart >= 3.8
5. **Hardening** — sysctl tuning, AppArmor, centralized logging, monitoring, backup

## 3. Best Practices

### Evidence-Based Verification

Never rely on assumptions. Verify with runtime commands:

- `sshd -T` for global SSH config; `sshd -T -C user=...,addr=...` for Match-aware config
- `ss -tlnup` for listening ports
- `nft list ruleset` + `iptables -S` + `ip6tables -S` for firewall rules
- `systemctl status` for service state
- `apt-get -s upgrade` for pending patches

### SSH Hardening Priorities

Changing the port provides minimal security value. Focus on what matters:

- `PasswordAuthentication no`
- `PermitRootLogin prohibit-password` — switch to `no` after creating a non-root admin
- Disable X11 forwarding
- Tighten connection timeouts and max auth retries
- `PermitUserRC no` unless explicitly needed
- Restrict source IPs or use Tailscale for further lockdown
- Audit Match blocks — they can silently override any of the above

### Firewall Modification with Rollback

Before modifying firewall rules, dump the current state and set up automatic rollback. If the new rules break connectivity, the old rules restore automatically after 2 minutes:

```bash
nft list ruleset > /tmp/nft-backup.conf
nft -c -f /path/to/new-rules.conf
systemd-run --on-active=120 --unit=nft-rollback nft -f /tmp/nft-backup.conf
nft -f /path/to/new-rules.conf
```

After verifying connectivity, cancel the rollback timer:

```bash
systemctl stop nft-rollback.timer 2>/dev/null
```

### Firewall Rule Alignment

Always match firewall rules to actual listeners. A common pitfall: a service opens an unexpected UDP port that the firewall does not cover.

Workflow:

1. Run `ss -tlnp` and `ss -ulnp` to discover all listeners
2. Write rules based on discovered ports
3. Dry-run with `nft -c -f <ruleset>` before applying
4. Verify with `nft list ruleset` after applying

### Service Verification After Updates

"Service is running" does not mean "service works correctly":

- fail2ban: verify `banaction` uses the correct backend, such as nft or iptables-nft
- unattended-upgrades: check `apt-daily*` timers actually fire on schedule

### needrestart Safety

Versions below 3.8 have local privilege escalation vulnerabilities (CVE-2024-48990) where attackers controlling `PYTHONPATH` can execute code as root. This is especially dangerous in unattended-upgrades pipelines where needrestart runs as root without supervision.

Always verify the version first: `needrestart --version`. In automated contexts, pin to list-only mode with `NEEDRESTART_MODE=l`. To suppress needrestart during apt hooks entirely, set `NEEDRESTART_SUSPEND=1`.

### Update Lifecycle

Close the loop: patch → restart affected services → verify. If the installed kernel differs from the running kernel, document it and schedule a reboot window.

Upgrade evidence lives in `/var/log/apt/history.log` and `/var/log/unattended-upgrades/`. Review these after each maintenance window.

### Useful Debian Tools

- **needrestart** — identifies services and kernels needing restart after upgrades. Must be >= 3.8 to avoid LPE vulnerabilities
- **debsecan** — cross-references installed packages against known CVEs. May pull in a local MTA like exim4. After installing, verify its listening address with `ss -tlnp` — if it binds to `0.0.0.0:25` or `[::]:25` instead of 127.0.0.1, lock it down immediately
- **debian-security-support** — checks whether packages are within active security support
