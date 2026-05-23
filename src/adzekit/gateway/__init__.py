"""Gateway package: bridges external messaging (Telegram today) to Claude Code.

Modules:
- runner: the Runner protocol + ClaudeSubprocessRunner (default; uses Pro
  subscription via `claude --resume -p`) + AgentSDKRunner (opt-in; uses
  claude-agent-sdk with ANTHROPIC_API_KEY).
- session_store: SQLite chat_id → session_id mapping.
- sessions_footer: appends `> - claude-code:<id> HH:MM-HH:MM /telegram` lines
  to today's daily note for cross-runtime session lineage.
- telegram: long-polling daemon using python-telegram-bot. Loaded lazily so
  the gateway module is importable without the optional telegram extras.
"""
