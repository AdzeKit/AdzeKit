"""Per-chat session-id persistence for the gateway daemon.

A tiny SQLite table maps Telegram chat_id → Claude Code session_id so the
daemon can resume the right conversation across daemon restarts and across
days. The DB lives at `{shed}/drafts/.gateway/sessions.sqlite` by default —
inside the workspace so the user can move/copy it with the rest of their
shed if they want, but under drafts/ so it's gitignored.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


class SessionStore:
    """SQLite-backed chat_id -> session_id mapping. Thread-safe within a
    single process (sqlite3 connection has check_same_thread=False)."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(db_path), check_same_thread=False, isolation_level=None,
        )
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                chat_id INTEGER PRIMARY KEY,
                session_id TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def get(self, chat_id: int) -> str | None:
        """Return the most-recent session_id for this chat, or None."""
        row = self._conn.execute(
            "SELECT session_id FROM sessions WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
        return row[0] if row else None

    def set(self, chat_id: int, session_id: str) -> None:
        """Upsert the session_id for this chat."""
        self._conn.execute(
            """
            INSERT INTO sessions (chat_id, session_id, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id) DO UPDATE SET
                session_id = excluded.session_id,
                updated_at = excluded.updated_at
            """,
            (chat_id, session_id),
        )

    def clear(self, chat_id: int) -> bool:
        """Forget the session for this chat (e.g. user typed /reset).
        Returns True if a row was removed."""
        cur = self._conn.execute(
            "DELETE FROM sessions WHERE chat_id = ?", (chat_id,),
        )
        return cur.rowcount > 0

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "SessionStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
