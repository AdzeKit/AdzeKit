# Telegram gateway

A long-running daemon that bridges Telegram messages to a Claude Code
session. Talk to your AdzeKit-aware assistant from any phone, all day.

## Architecture

```
You on Telegram  ─►  Bot (your token)  ─►  Gateway daemon  ─►  Claude Code
                                            │
                                            ├── allowlist (user_ids)
                                            ├── SessionStore (SQLite)
                                            │   {chat_id: claude_session_id}
                                            ├── Runner (Pro or SDK)
                                            └── append > Sessions: line to today
```

## Setup

### 1. Get a bot token

DM `@BotFather` on Telegram, run `/newbot`, follow the prompts. Save the
token it gives you.

### 2. Find your Telegram user ID

DM `@userinfobot` (or any "what's my id" bot). It'll reply with a numeric
ID. That's your `user_id`; the allowlist takes this exact integer.

### 3. Install AdzeKit with telegram extras

```bash
uv pip install -e ".[telegram]"        # from a checkout
# or, when packaged:
pip install "adzekit[telegram]"
```

### 4. Set environment variables

```bash
export ADZEKIT_SHED=~/Repos/adzekit-workspace
export ADZEKIT_TELEGRAM_BOT_TOKEN="123456:ABC..."
export ADZEKIT_TELEGRAM_ALLOWED_USER_IDS="123456789"   # comma-separated for multi
# Optional:
# export ADZEKIT_RUNNER=subprocess   # default: uses Claude Code Pro via `claude -p`
# export ADZEKIT_RUNNER=sdk          # opt-in: uses claude-agent-sdk + ANTHROPIC_API_KEY
# export ADZEKIT_TELEGRAM_DB_PATH=/custom/sessions.sqlite
# export ADZEKIT_GATEWAY_LOG_LEVEL=DEBUG
```

### 5. Run it

```bash
adzekit gateway start
```

The daemon polls Telegram in a loop. Send `hi` to your bot; it'll reply
with a Claude response and remember the conversation. Subsequent messages
resume the same session.

### 6. Background it

For 24/7 operation:

- **macOS (local)**: write a launchd plist that runs `adzekit gateway start`
  under `KeepAlive`. Caveat: the Mac must be awake; networking dies during
  sleep. `caffeinate -ds` keeps it alive at the cost of battery.
- **VPS / Linux**: a systemd unit (see `docs/deployment.md` once written) is
  the reliable answer for true 24/7. ~$5/mo class machine is plenty.

## Runner modes

| Mode | Subprocess (default) | Agent SDK |
|---|---|---|
| Cost | Claude Code Pro subscription | API per-token via `ANTHROPIC_API_KEY` |
| Latency per turn | ~2–5s (subprocess startup) | ~sub-second (in-process) |
| Required deps | `claude` on PATH | `pip install adzekit[sdk]` |
| Rate limits | Pro plan limits apply | Anthropic API quota |
| Best for | Cost-controlled, hands-off | Low-latency, variable usage |

Switch at runtime with `ADZEKIT_RUNNER=sdk`. No code changes; same external
behavior.

## Per-chat sessions

Every Telegram chat gets its own Claude session, persisted in a small
SQLite DB. The daemon survives restarts; conversations resume where they
left off. The DB lives at `{shed}/drafts/.gateway/sessions.sqlite` by
default (gitignored — part of the workbench).

## Daily-note Sessions footer

Each exchange appends one line to today's `daily/YYYY-MM-DD.md`:

```
> Sessions:
> - claude-code:8e22-7f3a 14:20-14:23 /telegram
> - claude-code:b91d-04ce 16:15-16:16 /telegram
```

If today's daily note doesn't exist yet (you haven't run `/daily-start`),
the daemon silently skips the append rather than failing the exchange.

## Allowlist hygiene

The bot token gives anyone with it bot-API access. Treat it like an SSH key
— don't commit, don't share. The Telegram user-ID allowlist is the
primary access gate; the bot will silently refuse messages from anyone
not on it.

To add a user without restarting: edit `ADZEKIT_TELEGRAM_ALLOWED_USER_IDS`
and restart the daemon. (Hot-reload via signal handler is a future
feature.)

## Troubleshooting

- **Bot doesn't reply**: check `adzekit gateway start` logs for runner
  errors. Most common: `claude` not on PATH, or `ANTHROPIC_API_KEY` not
  set when in SDK mode.
- **"Unauthorized" reply**: your user_id isn't in the allowlist. Confirm
  with `@userinfobot` and re-export `ADZEKIT_TELEGRAM_ALLOWED_USER_IDS`.
- **Session forgotten across restart**: check that the SQLite DB path is
  writable. Default is under `drafts/.gateway/` inside the shed.
- **Subprocess Runner is slow**: that's expected (~2–5s startup per
  message). Switch to `ADZEKIT_RUNNER=sdk` for sub-second latency at the
  cost of paying per-token.
