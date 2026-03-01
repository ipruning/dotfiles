---
name: vps
description: "Linux VPS/server security audit, hardening, and maintenance. Triggers: remote Linux host + SSH hardening, firewall rules, Debian/Ubuntu patching, unknown server audit, fail2ban, unattended-upgrades. Not for macOS."
metadata:
  version: "3"
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

5. **Separate audit from apply.** Audit steps use only read-only commands (`sshd -T`, `ss`, `nft list ruleset`, `apt-get -s upgrade`). Apply steps modify system state and require explicit human sign-off. Any command containing `-y`, `install`, `upgrade` (without `-s`), `nft -f`, `systemctl restart/reload`, or config file writes belongs in the apply phase. This boundary prevents "health check that accidentally became hardening."

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

nftables boot persistence — confirm rules survive reboot and the on-disk file is syntactically valid:

```bash
systemctl is-enabled nftables
systemctl is-active nftables
nft -c -f /etc/nftables.conf
```

Exposure surface consistency — compare allowed ports against actual listeners. Any port allowed by the firewall but not actively listening is unnecessary exposure (e.g. 80/443 open in nftables but nothing bound):

```bash
echo "=== Listening ===" && ss -tlnp | awk 'NR>1{print $4}' | sort -u
echo "=== Allowed ===" && nft list ruleset 2>/dev/null | grep -oP 'dport \K\S+' | sort -u
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

Identify whether iptables uses the legacy kernel backend or the nf_tables translation layer. Mixed backends cause silent rule conflicts and confuse anyone using `iptables` commands expecting them to be authoritative:

```bash
iptables -V
update-alternatives --display iptables 2>/dev/null
```

If the system uses nftables as its primary firewall, document this as policy and do not install competing firewall managers (ufw, firewalld, iptables-persistent).

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
cat /etc/apt/sources.list.d/*.list 2>/dev/null
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

Search for evidence of successful access — "no evidence" is not proof of absence, but finding only your own IPs is a strong positive signal. Focus on `Accepted` lines and cross-reference source IPs against known-good:

```bash
journalctl -u ssh --since "7 days ago" --no-pager | grep -E 'Accepted (publickey|password|keyboard-interactive)' | tail -50
last -50
```

Check for authorized_keys and SSH config tampering (mtime/content drift):

```bash
stat /root/.ssh/authorized_keys 2>/dev/null
for f in /home/*/.ssh/authorized_keys; do stat "$f" 2>/dev/null; done
stat /etc/ssh/sshd_config
ls -la /etc/ssh/sshd_config.d/ 2>/dev/null
```

### 2.10 Remediation Priority

After the read-only audit, fix in this order:

1. **SSH** — disable password auth, restrict root login to key-only, override Debian defaults (`X11Forwarding no`, `PermitUserRC no`), limit source IPs via `AllowUsers`
2. **Firewall** — default drop policy, whitelist only required ports, align allowed ports with actual listeners (both directions), verify nftables boot persistence
3. **Anti-brute-force** — fail2ban or CrowdSec. When password auth is already disabled, the primary value shifts from brute-force prevention to log noise reduction and connection-layer DoS mitigation. If SSH is further restricted to known source IPs or a VPN, this becomes optional
4. **Updates** — enable unattended-upgrades, verify apt-daily timers fire, confirm Allowed-Origins covers security updates, configure needrestart >= 3.8
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
- `X11Forwarding no` — Debian's openssh-server defaults to `yes`; disable on all headless servers
- `PermitUserRC no` — Debian defaults to `yes`, providing a login-time persistence vector via `~/.ssh/rc`
- Tighten connection timeouts and max auth retries. **Client-side pitfall:** if `MaxAuthTries` is low (e.g. 3) and the local SSH agent has multiple keys loaded, the correct key may never be attempted before the server disconnects with `Too many authentication failures`. Fix: use `IdentitiesOnly yes` in `~/.ssh/config` or `ssh -i` to pin the correct key
- `AllowUsers` / `AllowGroups` to restrict who can log in (supports `user@host` and CIDR for source restriction). **Maintenance trap:** when adding a new user to a hardened server, you must also add them to the `AllowUsers` directive — otherwise SSH rejects the connection silently. Diagnose with `journalctl -u ssh` (look for `not allowed because not listed in AllowUsers`)
- Restrict source IPs or use Tailscale for further lockdown
- Audit Match blocks — they can silently override any of the above

**Debian default pitfall:** several openssh-server defaults are designed for general-purpose usability, not hardened servers. After overriding them via `/etc/ssh/sshd_config.d/`, always verify with `sshd -T` (not by reading config files) and test Match-aware resolution with `sshd -T -C user=root,addr=...`.

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

Match firewall rules to actual listeners in both directions:

- **Listening but not allowed** — a service opens a port the firewall does not cover (common with unexpected UDP listeners)
- **Allowed but not listening** — the firewall permits traffic to a port with no active service. This is unnecessary exposure: scanners can fingerprint the host more precisely, and any accidentally started service (container, panel, daemon) becomes instantly reachable

Workflow:

1. Run `ss -tlnp` and `ss -ulnp` to discover all listeners
2. Extract allowed ports from `nft list ruleset` (`grep -oP 'dport \K\S+'`)
3. Flag any mismatch: listeners without allow rules, and allow rules without listeners
4. If containers are present (Docker, Podman), check the `forward` chain for bridge interface rules — see §3 nftables Forward Chain and Containers
5. Write/adjust rules based on actual + planned ports only
6. Dry-run with `nft -c -f <ruleset>` before applying
7. Verify with `nft list ruleset` after applying

### nftables Forward Chain and Containers

When nftables uses `policy drop` on the `forward` chain in an `inet filter` table, container networking (Docker, Podman) breaks silently. Containers report `Network is unreachable` on outbound connections; ACME challenges and API calls fail with timeouts.

**Why this happens:** Docker manages its own rules in the `ip filter` table (legacy iptables). However, if an `inet filter` table exists in nftables with a `forward` hook, **both** must allow the traffic. The nftables drop policy discards packets that the Docker iptables rules have already "accepted" — nftables `inet` hooks and iptables `ip` hooks are independent chains evaluated in parallel.

**Diagnosis:**

```bash
nft list chain inet filter forward 2>/dev/null
docker run --rm alpine ping -c1 1.1.1.1
```

If the chain exists with `policy drop` and no container interface rules, that's the cause.

**Fix — add explicit forward rules for container bridges:**

```bash
nft add rule inet filter forward iifname "br-*" accept
nft add rule inet filter forward oifname "br-*" accept
nft add rule inet filter forward iifname "docker0" accept
nft add rule inet filter forward oifname "docker0" accept
```

Then persist to `/etc/nftables.conf` and verify with `nft -c -f /etc/nftables.conf`.

**Prevention:** when designing nftables rules for a host that will run containers, include forward rules for container interfaces from the start. The firewall alignment workflow (§3 Firewall Rule Alignment) should check FORWARD rules against container bridge interfaces, not just INPUT against listeners.

### iptables/nftables Coexistence

On Debian, `iptables` may use the legacy kernel backend or the nf_tables translation layer (`iptables-nft`). When nftables is the primary firewall, having iptables with default ACCEPT policies creates two risks:

- Tools or team members may use `iptables`/`ufw`/`firewalld` thinking they control the firewall, while the actual rules live in nftables
- Mixed backends can cause silent rule conflicts or bypass

Verify the active backend:

```bash
iptables -V
update-alternatives --display iptables 2>/dev/null
```

Designate one firewall framework as authoritative and enforce it as policy. Do not install competing managers on the same host.

### nftables Boot Persistence

`nft list ruleset` proves rules are loaded in the running kernel but does not prove they survive reboot. Always verify the full chain:

```bash
systemctl is-enabled nftables
systemctl is-active nftables
nft -c -f /etc/nftables.conf
sha256sum /etc/nftables.conf
```

The `-c` flag dry-runs the rule file without loading it, catching syntax errors before they cause a reboot into an unprotected state. The hash provides an evidence trail for config drift detection.

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

### Hetzner Control Plane Security

OS-level hardening is necessary but not sufficient. If the hosting provider's control panel is compromised, an attacker can bypass all OS defenses via Rescue System, KVM, or disk re-imaging.

**Must do (requires console access, cannot be done via SSH):**

- **2FA**: Enable two-factor authentication on the Hetzner account
- **Login-OTP / Support-OTP**: Configure one-time passwords for login and support channel verification (anti-social-engineering)
- **Rescue System familiarity**: Understand how to activate Rescue (PXE-booted Debian live environment in RAM that does not touch your disks) and upload SSH keys to it — this is the recovery path when SSH or firewall changes lock you out

**Optional (Robot firewall):**

Hetzner's Robot firewall is a stateless filter at the switch port level with a 10-rule limit per direction. Trade-offs:

- Stateless: you must manually write return traffic rules (ACK + ephemeral ports)
- IPv6 filtering requires separate activation; enabling without rules blocks all IPv6
- ICMPv6 cannot be filtered (required for IPv6 neighbor discovery)
- The "Hetzner Services" checkbox prevents accidentally blocking Rescue, DHCP, DNS, and monitoring

If the OS-level nftables firewall is stable and well-tested, the Robot firewall is optional. If used, configure only inbound minimal allow and avoid outbound filtering to prevent self-lockout.

### Non-Root Admin User Transition

The standard hardening path after Day-0 bootstrap (firewall + key-only SSH as root):

**Create admin user with sudo:**

```bash
useradd -m -s /bin/bash -G sudo alex
```

**Set a local password for sudo** — SSH is key-only, but sudo still needs a password. Locking the password (`passwd -l`) forces you into either `NOPASSWD: ALL` (insecure) or being unable to sudo at all:

```bash
passwd alex
```

**Copy SSH public key:**

```bash
mkdir -p /home/alex/.ssh
cp /root/.ssh/authorized_keys /home/alex/.ssh/authorized_keys
chown -R alex:alex /home/alex/.ssh
chmod 700 /home/alex/.ssh && chmod 600 /home/alex/.ssh/authorized_keys
```

**Verify in a NEW session** (keep the root session open as fallback):

```bash
ssh alex@host
sudo -i
```

**Lock down SSH** — only after verifying the new user works:

```bash
# In /etc/ssh/sshd_config.d/hardening.conf:
# PermitRootLogin no
# AllowUsers alex
# X11Forwarding no
# PermitUserRC no
sshd -T | grep -E 'permitrootlogin|allowusers|x11forwarding|permituserrc'
systemctl reload ssh
```

**Verify root is locked out** from a third session — should be rejected.

**Password strategy pitfall:** "SSH key-only" and "no system password" are different things. SSH `PasswordAuthentication no` prevents remote password login. But the local user password is still used by `sudo`, `su`, and console login. Deleting or locking the admin password while SSH password auth is disabled creates a dead end where key compromise = immediate root (via `NOPASSWD` sudo) with no second factor.

### SSH Key Separation

Do not reuse the same SSH key across privilege levels. Recommended minimum for a single admin:

- **Daily admin key** — used for `ssh alex@host`, the key you carry on your workstation
- **Break-glass key** — stored offline or in a hardware token, used only for emergency recovery (e.g., temporarily re-enabling root login). Never loaded in your SSH agent day-to-day

If the admin key is compromised, the attacker gets user-level access + sudo (still needs password). The break-glass key remains uncompromised and can be used to rotate the admin key.

For multi-person teams: one key per person, never shared accounts or shared keys. Revocation = delete that person's key and account.

### Docker Group Privilege Escalation

Adding a user to the `docker` group grants root-equivalent access to the host. Any member can `docker run -v /:/host` to read/write the entire filesystem, extract `/etc/shadow`, inject SSH keys, or install rootkits — all without `sudo`.

**Rules for multi-user hosts:**

- Do not add users to the `docker` group by default
- Users who need container access should use `sudo docker ...` (auditable via syslog)
- For untrusted users, consider rootless Docker or Podman (runs containers in user namespaces without root privileges)
- When auditing an unknown server, check `getent group docker` for unexpected members

### Useful Debian Tools

- **needrestart** — identifies services and kernels needing restart after upgrades. Must be >= 3.8 to avoid LPE vulnerabilities
- **debsecan** — cross-references installed packages against known CVEs. May pull in a local MTA like exim4. After installing, verify its listening address with `ss -tlnp` — if it binds to `0.0.0.0:25` or `[::]:25` instead of 127.0.0.1, lock it down immediately
- **debian-security-support** — checks whether packages are within active security support
