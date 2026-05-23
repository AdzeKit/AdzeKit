"""Telegram long-polling daemon.

Loaded lazily so the gateway package is importable without the optional
`python-telegram-bot` extra. The actual import happens inside `run()`.

Configuration (env vars):
  ADZEKIT_TELEGRAM_BOT_TOKEN     — required; BotFather token
  ADZEKIT_TELEGRAM_ALLOWED_USER_IDS — required; comma-separated user IDs
  ADZEKIT_TELEGRAM_DB_PATH       — optional; sessions DB path
                                   (default: {shed}/drafts/.gateway/sessions.sqlite)
  ADZEKIT_RUNNER                 — optional; "subprocess" (default) or "sdk"

The daemon prints one line per message handled (concise log) and reads
each turn through a Runner. Conversations resume by chat_id.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from adzekit.config import Settings, get_settings
from adzekit.gateway.runner import Runner, RunnerError, make_runner
from adzekit.gateway.session_store import SessionStore
from adzekit.gateway.sessions_footer import (
    append_session_line,
    format_session_line,
)

log = logging.getLogger("adzekit.gateway.telegram")


# Telegram's per-message length limit.
TELEGRAM_MESSAGE_LIMIT = 4096
# We send slightly smaller chunks to leave a small margin (and for cleaner
# breaks on word boundaries when we split).
CHUNK_TARGET = 4000


@dataclass
class TelegramConfig:
    bot_token: str
    allowed_user_ids: frozenset[int]
    shed_path: Path
    session_db_path: Path
    runner_name: str | None = None  # None → uses ADZEKIT_RUNNER env

    @classmethod
    def from_env(cls, settings: Settings | None = None) -> "TelegramConfig":
        settings = settings or get_settings()

        token = os.environ.get("ADZEKIT_TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "ADZEKIT_TELEGRAM_BOT_TOKEN is not set. Get a token from "
                "@BotFather on Telegram and export it before running "
                "`adzekit gateway start`."
            )

        ids_raw = os.environ.get("ADZEKIT_TELEGRAM_ALLOWED_USER_IDS", "").strip()
        if not ids_raw:
            raise RuntimeError(
                "ADZEKIT_TELEGRAM_ALLOWED_USER_IDS is not set. Set it to a "
                "comma-separated list of Telegram numeric user IDs you want "
                "to allow (e.g. `123456789,987654321`)."
            )
        try:
            ids = frozenset(int(x.strip()) for x in ids_raw.split(",") if x.strip())
        except ValueError as exc:
            raise RuntimeError(
                f"ADZEKIT_TELEGRAM_ALLOWED_USER_IDS contains a non-numeric "
                f"value: {exc}"
            )

        db_path_raw = os.environ.get("ADZEKIT_TELEGRAM_DB_PATH", "")
        if db_path_raw:
            db_path = Path(db_path_raw).expanduser()
        else:
            db_path = settings.drafts_dir / ".gateway" / "sessions.sqlite"

        return cls(
            bot_token=token,
            allowed_user_ids=ids,
            shed_path=settings.shed,
            session_db_path=db_path,
        )


def chunk_for_telegram(text: str, *, limit: int = CHUNK_TARGET) -> list[str]:
    """Split a long response into Telegram-safe chunks.

    Prefers newline boundaries; falls back to hard cuts when no good
    boundary is available. Each chunk is ≤ limit bytes (Telegram counts
    UTF-16 code units but limit is generous enough for safety).
    """
    if len(text) <= limit:
        return [text] if text else []
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        # Try to break at the last newline within `limit`.
        cut = remaining.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks


async def _handle_chat(
    *,
    chat_id: int,
    user_id: int,
    text: str,
    config: TelegramConfig,
    runner: Runner,
    store: SessionStore,
) -> tuple[bool, list[str]]:
    """Pure handler: returns (authorized, response_chunks).

    Extracted from the python-telegram-bot handler so it's unit-testable
    without spinning up the framework.
    """
    if user_id not in config.allowed_user_ids:
        log.warning("rejected message from unauthorized user_id=%s", user_id)
        return False, [
            "Unauthorized. This bot is allowlisted to specific Telegram users."
        ]

    # Resolve session id.
    session_id = store.get(chat_id) or ""

    start = datetime.now()
    try:
        result = await runner.chat(session_id, text, cwd=config.shed_path)
    except RunnerError as exc:
        log.error("runner error: %s", exc)
        return True, [f"Error talking to Claude: {exc}"]
    end = datetime.now()

    # Persist the (possibly new) session id.
    if result.session_id:
        store.set(chat_id, result.session_id)

    # Append a line to today's daily-note Sessions footer.
    line = format_session_line(
        runtime="claude-code",
        session_id=result.session_id,
        start=start,
        end=end,
        command="/telegram",
    )
    appended = append_session_line(config.shed_path, line)
    if not appended:
        log.debug(
            "today's daily note doesn't exist yet; sessions footer not written"
        )

    response_text = result.text or "(empty response)"
    return True, chunk_for_telegram(response_text)


def run() -> None:
    """Start the Telegram long-polling daemon.

    Blocks until interrupted. Should be invoked from a process supervisor
    (launchd, systemd, tmux) for 24/7 operation.
    """
    try:
        from telegram import Update
        from telegram.ext import (
            Application,
            ContextTypes,
            MessageHandler,
            filters,
        )
    except ImportError as exc:
        raise RuntimeError(
            "The Telegram gateway requires `python-telegram-bot`. Install "
            "with `pip install adzekit[telegram]` (or `pip install "
            "python-telegram-bot[ext]>=21.0`)."
        ) from exc

    logging.basicConfig(
        level=os.environ.get("ADZEKIT_GATEWAY_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    config = TelegramConfig.from_env()
    runner = make_runner(config.runner_name)
    store = SessionStore(config.session_db_path)

    log.info(
        "starting Telegram gateway (allowlist=%d users, shed=%s, runner=%s)",
        len(config.allowed_user_ids),
        config.shed_path,
        type(runner).__name__,
    )

    async def handler(update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not update.effective_chat or not update.effective_user or not update.message:
            return
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        text = update.message.text or ""

        authorized, chunks = await _handle_chat(
            chat_id=chat_id,
            user_id=user_id,
            text=text,
            config=config,
            runner=runner,
            store=store,
        )
        for chunk in chunks:
            await update.message.reply_text(chunk)
        if authorized:
            log.info(
                "chat=%s user=%s sent %d chars; replied in %d chunk(s)",
                chat_id, user_id, len(text), len(chunks),
            )

    app = Application.builder().token(config.bot_token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler))
    app.run_polling()
