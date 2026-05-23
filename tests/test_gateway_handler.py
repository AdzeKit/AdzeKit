"""Tests for the gateway _handle_chat function (pure handler logic).

The python-telegram-bot framework is NOT imported here; we test the
handler in isolation by passing fake Runner + SessionStore objects.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

from adzekit.gateway.runner import RunnerError, RunnerResult
from adzekit.gateway.session_store import SessionStore
from adzekit.gateway.telegram import (
    CHUNK_TARGET,
    TelegramConfig,
    _handle_chat,
    chunk_for_telegram,
)


class FakeRunner:
    """Records the last call and returns a canned response."""

    def __init__(self, *, text: str = "ok", session_id: str = "sess-1"):
        self.text = text
        self.session_id = session_id
        self.calls: list[tuple[str, str]] = []
        self.should_raise: Exception | None = None

    async def chat(self, session_id: str, message: str, *, cwd=None) -> RunnerResult:
        self.calls.append((session_id, message))
        if self.should_raise:
            raise self.should_raise
        return RunnerResult(
            text=self.text,
            session_id=self.session_id,
            duration_s=0.01,
        )


def _make_config(workspace, allowed_ids=frozenset({100})) -> TelegramConfig:
    return TelegramConfig(
        bot_token="fake",
        allowed_user_ids=allowed_ids,
        shed_path=workspace.shed,
        session_db_path=workspace.drafts_dir / ".gateway" / "sessions.sqlite",
    )


# --- _handle_chat ----------------------------------------------------------


def test_handler_refuses_unauthorized_user(workspace, tmp_path):
    config = _make_config(workspace, allowed_ids=frozenset({100}))
    runner = FakeRunner()
    store = SessionStore(tmp_path / "s.sqlite")

    authorized, chunks = asyncio.run(_handle_chat(
        chat_id=42,
        user_id=999,  # NOT in allowlist
        text="hi",
        config=config,
        runner=runner,
        store=store,
    ))
    assert authorized is False
    assert any("Unauthorized" in c for c in chunks)
    # Runner was NOT invoked.
    assert runner.calls == []


def test_handler_authorizes_listed_user_and_calls_runner(workspace, tmp_path):
    config = _make_config(workspace, allowed_ids=frozenset({100}))
    runner = FakeRunner(text="hello", session_id="new-sess")
    store = SessionStore(tmp_path / "s.sqlite")

    authorized, chunks = asyncio.run(_handle_chat(
        chat_id=42,
        user_id=100,  # IN allowlist
        text="ping",
        config=config,
        runner=runner,
        store=store,
    ))
    assert authorized is True
    assert chunks == ["hello"]
    # Runner was called with empty session id (no prior turn).
    assert runner.calls == [("", "ping")]
    # Session was persisted.
    assert store.get(42) == "new-sess"


def test_handler_resumes_existing_session(workspace, tmp_path):
    config = _make_config(workspace, allowed_ids=frozenset({100}))
    store = SessionStore(tmp_path / "s.sqlite")
    store.set(42, "prior-sess")
    runner = FakeRunner(text="reply", session_id="prior-sess")

    asyncio.run(_handle_chat(
        chat_id=42, user_id=100, text="follow-up",
        config=config, runner=runner, store=store,
    ))
    assert runner.calls == [("prior-sess", "follow-up")]


def test_handler_surfaces_runner_errors_as_message(workspace, tmp_path):
    config = _make_config(workspace, allowed_ids=frozenset({100}))
    runner = FakeRunner()
    runner.should_raise = RunnerError("backend crashed")
    store = SessionStore(tmp_path / "s.sqlite")

    authorized, chunks = asyncio.run(_handle_chat(
        chat_id=42, user_id=100, text="hi",
        config=config, runner=runner, store=store,
    ))
    assert authorized is True
    assert any("backend crashed" in c for c in chunks)
    # Session was NOT updated (we don't have a valid id from a failed call).
    assert store.get(42) is None


def test_handler_appends_to_sessions_footer(workspace, tmp_path):
    """End-to-end: today's daily note exists, handler appends a footer line."""
    today = date.today()
    note = workspace.daily_dir / f"{today.isoformat()}.md"
    note.write_text(
        f"# {today.isoformat()}\n\n## Intention\n- [ ] x\n", encoding="utf-8",
    )
    config = _make_config(workspace, allowed_ids=frozenset({100}))
    runner = FakeRunner(text="resp", session_id="footer-test-sess")
    store = SessionStore(tmp_path / "s.sqlite")

    asyncio.run(_handle_chat(
        chat_id=42, user_id=100, text="hi",
        config=config, runner=runner, store=store,
    ))
    body = note.read_text(encoding="utf-8")
    assert "> Sessions:" in body
    assert "claude-code:footer-t" in body  # first 8 chars of session id
    assert "/telegram" in body


def test_handler_handles_empty_response(workspace, tmp_path):
    """A blank response from the runner should send a placeholder, not nothing."""
    config = _make_config(workspace, allowed_ids=frozenset({100}))
    runner = FakeRunner(text="", session_id="x")
    store = SessionStore(tmp_path / "s.sqlite")
    _, chunks = asyncio.run(_handle_chat(
        chat_id=42, user_id=100, text="hi",
        config=config, runner=runner, store=store,
    ))
    assert chunks == ["(empty response)"]


# --- chunk_for_telegram ----------------------------------------------------


def test_chunk_short_text_one_chunk():
    assert chunk_for_telegram("hello") == ["hello"]


def test_chunk_empty_text():
    assert chunk_for_telegram("") == []


def test_chunk_splits_at_newline_boundary():
    line = "x" * 100
    text = "\n".join([line] * 50)  # ~5000 chars with newlines
    chunks = chunk_for_telegram(text, limit=200)
    assert len(chunks) > 1
    # Most chunks should end at a clean newline-separated boundary.
    assert all(len(c) <= 200 for c in chunks)


def test_chunk_hard_cuts_when_no_newline():
    text = "x" * 10000
    chunks = chunk_for_telegram(text, limit=500)
    assert len(chunks) == 20
    assert all(len(c) <= 500 for c in chunks)


def test_chunk_default_limit():
    text = "a" * (CHUNK_TARGET + 100)
    chunks = chunk_for_telegram(text)
    assert len(chunks) == 2


# --- TelegramConfig.from_env ----------------------------------------------


def test_from_env_requires_bot_token(workspace, monkeypatch):
    monkeypatch.delenv("ADZEKIT_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("ADZEKIT_TELEGRAM_ALLOWED_USER_IDS", "1")
    with pytest.raises(RuntimeError, match="BOT_TOKEN"):
        TelegramConfig.from_env(workspace)


def test_from_env_requires_allowlist(workspace, monkeypatch):
    monkeypatch.setenv("ADZEKIT_TELEGRAM_BOT_TOKEN", "fake")
    monkeypatch.delenv("ADZEKIT_TELEGRAM_ALLOWED_USER_IDS", raising=False)
    with pytest.raises(RuntimeError, match="ALLOWED_USER_IDS"):
        TelegramConfig.from_env(workspace)


def test_from_env_parses_user_ids(workspace, monkeypatch):
    monkeypatch.setenv("ADZEKIT_TELEGRAM_BOT_TOKEN", "fake")
    monkeypatch.setenv("ADZEKIT_TELEGRAM_ALLOWED_USER_IDS", "100, 200,300")
    config = TelegramConfig.from_env(workspace)
    assert config.allowed_user_ids == frozenset({100, 200, 300})


def test_from_env_rejects_nonnumeric_id(workspace, monkeypatch):
    monkeypatch.setenv("ADZEKIT_TELEGRAM_BOT_TOKEN", "fake")
    monkeypatch.setenv("ADZEKIT_TELEGRAM_ALLOWED_USER_IDS", "100,not-a-number")
    with pytest.raises(RuntimeError, match="non-numeric"):
        TelegramConfig.from_env(workspace)
