# Deployment

Where to actually run the AdzeKit Telegram gateway so your assistant is
reachable from your phone 24/7. Two paths; the daemon code is identical
between them.

| Path | Cost | Reachability | Best for |
|---|---|---|---|
| **Local Mac** (mini, desktop, laptop with `caffeinate`) | $0 (already own) | Drops during sleep / network changes | Tinkering, low-stakes use, full local shed |
| **Small VPS** ($5/mo class) | ~$5/month | 24/7, reliable | Real always-on assistant |

Pick one and skip to that section.

---

## Path 1 — Local Mac (always-on machine)

### Prerequisites

- macOS with `claude` CLI installed and Pro subscription (or
  `ANTHROPIC_API_KEY` exported if using `ADZEKIT_RUNNER=sdk`)
- `gcloud` if you want Gmail / Calendar adapters
- AdzeKit installed:

```bash
cd ~/Repos
git clone https://github.com/your-org/AdzeKit.git
cd AdzeKit
uv pip install -e ".[telegram]"
```

### Initial setup

```bash
adzekit init ~/Repos/adzekit-workspace
export ADZEKIT_SHED=~/Repos/adzekit-workspace
adzekit cadence install                        # morning/evening/weekly rituals
adzekit mcp install                            # wire Shed MCP into Claude Code
adzekit adapter install gmail                  # if you use inbox-triage
adzekit adapter install google-calendar        # if you want briefings
```

### Telegram daemon

Get a bot token from `@BotFather` and your user ID from `@userinfobot`.

Create a launchd plist at `~/Library/LaunchAgents/com.adzekit.gateway.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.adzekit.gateway</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/YOU/Repos/AdzeKit/.venv/bin/adzekit</string>
    <string>gateway</string>
    <string>start</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>ADZEKIT_SHED</key>
    <string>/Users/YOU/Repos/adzekit-workspace</string>
    <key>ADZEKIT_TELEGRAM_BOT_TOKEN</key>
    <string>YOUR_BOT_TOKEN_FROM_BOTFATHER</string>
    <key>ADZEKIT_TELEGRAM_ALLOWED_USER_IDS</key>
    <string>YOUR_TELEGRAM_USER_ID</string>
  </dict>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/com.adzekit.gateway.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/com.adzekit.gateway.err</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.adzekit.gateway.plist
tail -f /tmp/com.adzekit.gateway.err   # watch startup
```

Test: DM your bot from Telegram. It should reply with a Claude response.

### The sleep caveat

macOS puts your machine to sleep, which kills networking. Your bot
silently stops responding until you wake the laptop.

Options:

- **Keep awake while plugged in**: System Settings → Battery → Power
  Adapter → "Prevent automatic sleeping when the display is off." Closing
  the lid still sleeps unless display stays on.
- **`caffeinate`**: run `caffeinate -dimsu` in a `tmux` session to keep
  the machine awake. Annoying for laptops, fine for a Mac mini.
- **Live with the gap**: if you're OK with the bot being unreachable when
  you're away from home, ignore this. The cadence layer still fires
  morning/evening tasks because launchd batches missed jobs on wake.

If 24/7 reliability matters, skip to Path 2 (VPS).

### Maintenance

- Logs: `/tmp/com.adzekit.gateway.{log,err}` (rotate manually; `/tmp` is
  cleared on reboot)
- Update: `cd ~/Repos/AdzeKit && git pull && uv pip install -e ".[telegram]"`
  then `launchctl kickstart -k gui/$(id -u)/com.adzekit.gateway`
- Disable: `launchctl unload ~/Library/LaunchAgents/com.adzekit.gateway.plist`

---

## Path 2 — VPS ($5/mo class)

DigitalOcean, Hetzner, Linode, AWS Lightsail — any 1-CPU / 1-GB box.
Ubuntu 24.04 LTS is the path of least resistance.

### Initial setup on the VPS

```bash
# As a non-root user (e.g. `adzekit`):
sudo apt-get update && sudo apt-get install -y python3-venv git
git clone https://github.com/your-org/AdzeKit.git ~/AdzeKit
python3 -m venv ~/AdzeKit/.venv
~/AdzeKit/.venv/bin/pip install -e "~/AdzeKit[telegram]"
```

Install `claude` if using the subprocess Runner (or skip and use
`ADZEKIT_RUNNER=sdk` with `claude-agent-sdk` + `ANTHROPIC_API_KEY`).

### Shed strategy

Two options for where the shed lives:

**(a) Pull-only**: the daemon `git pull`s the shed on a schedule. The
daemon's drafts are visible only on the VPS until you ssh in or set up
push (option b). Simplest. Works if you're OK with reviewing drafts only
when you're at your main machine.

**(b) Pull + push**: the daemon commits any new drafts and pushes them
back to the workspace's git remote. Your laptop pulls them. Slightly
more setup; needs an SSH key for the daemon to push.

Option (a) for the MVP:

```bash
cd ~
git clone git@github.com:YOU/adzekit-workspace.git
# Cron: pull every 15 minutes
( crontab -l 2>/dev/null; echo "*/15 * * * * cd ~/adzekit-workspace && git pull --quiet" ) | crontab -
```

### Secrets

DON'T put the bot token in the shed (it's a public repo by design). The
shed contains your prose; secrets belong in environment variables only.

Create `/etc/adzekit/env`:

```bash
sudo mkdir -p /etc/adzekit
sudo tee /etc/adzekit/env > /dev/null <<EOF
ADZEKIT_SHED=/home/adzekit/adzekit-workspace
ADZEKIT_TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
ADZEKIT_TELEGRAM_ALLOWED_USER_IDS=YOUR_TELEGRAM_USER_ID
# Pick a runner:
ADZEKIT_RUNNER=sdk
ANTHROPIC_API_KEY=sk-ant-...
EOF
sudo chmod 600 /etc/adzekit/env
sudo chown adzekit:adzekit /etc/adzekit/env
```

### systemd unit

`/etc/systemd/system/adzekit-gateway.service`:

```ini
[Unit]
Description=AdzeKit Telegram gateway
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=adzekit
EnvironmentFile=/etc/adzekit/env
WorkingDirectory=/home/adzekit/AdzeKit
ExecStart=/home/adzekit/AdzeKit/.venv/bin/adzekit gateway start
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable + start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now adzekit-gateway
sudo systemctl status adzekit-gateway      # confirm it's running
sudo journalctl -u adzekit-gateway -f      # tail logs
```

Test: DM the bot. Should reply within a few seconds.

### Updates

```bash
cd ~/AdzeKit && git pull && ~/AdzeKit/.venv/bin/pip install -e ".[telegram]"
sudo systemctl restart adzekit-gateway
```

### Bidirectional shed (Option b)

If you want drafts the daemon produces (cron-fired daily-start, insights,
inbox-triage) to push back to git automatically, add a commit + push cron:

```bash
( crontab -l 2>/dev/null; cat <<'EOF' ) | crontab -
*/15 * * * * cd ~/adzekit-workspace && git pull --quiet
30 17 * * 1-5 cd ~/adzekit-workspace && git add . && git commit -m "vps: daily drafts $(date +%Y-%m-%d)" --quiet && git push --quiet || true
EOF
```

Caveat: this commits everything in the shed (including potentially
sensitive drafts). Review what's in `.gitignore` — by default `drafts/`
and `stock/` are ignored, so the commit covers only backbone changes
(daily notes, loop edits). That's typically what you want.

---

## Picking between Pro Runner and SDK Runner

| Runner | Cost | Latency | Setup |
|---|---|---|---|
| **`subprocess`** (default) | Pro subscription | ~2–5s startup per turn | `brew install claude` (or however you install Claude Code) |
| **`sdk`** | Pay-per-token API | ~sub-second | `pip install adzekit[sdk]`; export `ANTHROPIC_API_KEY` |

VPS: tends to favor the SDK runner (no Claude Code CLI to install on
Linux; pay-per-token is fine for low-volume).

Local Mac: tends to favor the subprocess runner (you already have Claude
Code and a Pro sub).

Swap with one env var: `ADZEKIT_RUNNER=sdk`. No code change, same
external behavior.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Bot doesn't reply | Daemon not running | `systemctl status adzekit-gateway` or `launchctl list \| grep adzekit` |
| `claude: command not found` (subprocess mode) | Claude Code CLI not on PATH for the daemon's user | Use absolute path in the unit/plist `ExecStart`, or switch to SDK runner |
| `ANTHROPIC_API_KEY not set` (SDK mode) | Env var missing for the daemon | Add to `/etc/adzekit/env` (systemd) or `EnvironmentVariables` (launchd) |
| "Unauthorized" reply | Your Telegram user ID isn't in the allowlist | Double-check via `@userinfobot`; update `ADZEKIT_TELEGRAM_ALLOWED_USER_IDS` and restart |
| Daemon crashes immediately on start | Usually a config validation failure | Run `adzekit gateway start` interactively to see the error |
| Today's daily note has no `> Sessions:` footer | Daily note doesn't exist for today yet | Run `adzekit daily-start` (or wait for the morning cadence) |
| Drafts on VPS not visible on laptop | Shed pull/push cron not configured | See "Bidirectional shed (Option b)" above |
