"""Tests for the sessions-footer appender."""

from __future__ import annotations

from datetime import date, datetime

from adzekit.gateway.sessions_footer import (
    SESSION_LINE_RE,
    _insert_session_line,
    append_session_line,
    format_session_line,
)


# --- format_session_line ---------------------------------------------------


def test_format_basic():
    line = format_session_line(
        runtime="claude-code",
        session_id="abc12345-7f3a-xyz",
        start=datetime(2026, 5, 22, 8, 14),
        end=datetime(2026, 5, 22, 8, 42),
        command="/telegram",
    )
    assert line == "> - claude-code:abc12345 08:14-08:42 /telegram"


def test_format_with_draft_link(tmp_path):
    from pathlib import Path
    line = format_session_line(
        runtime="claude-code",
        session_id="def67890",
        start=datetime(2026, 5, 22, 8, 14),
        end=datetime(2026, 5, 22, 8, 42),
        command="/daily-start",
        draft_rel=Path("drafts/daily-start-2026-05-22-081400-laptop.md"),
    )
    assert line.endswith("-> drafts/daily-start-2026-05-22-081400-laptop.md")


def test_format_handles_empty_session_id():
    """Defensive: an empty session id shouldn't crash."""
    line = format_session_line(
        runtime="claude-code",
        session_id="",
        start=datetime(2026, 5, 22, 8, 14),
        end=datetime(2026, 5, 22, 8, 42),
        command="/telegram",
    )
    assert line.startswith("> - claude-code:? ")


# --- _insert_session_line --------------------------------------------------


def test_insert_creates_footer_when_absent():
    text = "# 2026-05-22 Friday\n\n## Intention\n- [ ] thing\n"
    result = _insert_session_line(text, "> - claude-code:abc 08:14-08:15 /telegram")
    assert "> Sessions:" in result
    assert "> - claude-code:abc 08:14-08:15 /telegram" in result
    assert result.endswith("\n")


def test_insert_appends_to_existing_footer():
    text = (
        "# Day\n\n"
        "> Sessions:\n"
        "> - claude-code:first 08:14-08:15 /telegram\n"
    )
    new_line = "> - claude-code:second 09:00-09:01 /telegram"
    result = _insert_session_line(text, new_line)
    # Both lines present.
    assert "first" in result
    assert "second" in result
    # New line appears AFTER the old one (chronological order).
    assert result.index("first") < result.index("second")


def test_insert_preserves_content_after_footer():
    text = (
        "# Day\n\n"
        "> Sessions:\n"
        "> - claude-code:abc 08:14-08:15 /x\n"
        "\n"
        "Some trailing text.\n"
    )
    result = _insert_session_line(text, "> - claude-code:new 09:00-09:01 /y")
    assert "Some trailing text." in result
    # The new line lands before the trailing text.
    assert result.index("new") < result.index("Some trailing text.")


def test_insert_does_not_duplicate_footer_heading():
    text = "# Day\n\n> Sessions:\n> - claude-code:abc 08:14-08:15 /x\n"
    result = _insert_session_line(text, "> - claude-code:new 09:00-09:01 /y")
    # Only one "> Sessions:" heading in the result.
    assert result.count("> Sessions:") == 1


# --- append_session_line (end-to-end on real file) -------------------------


def test_append_noop_when_daily_note_missing(workspace):
    """If today's daily note hasn't been created yet, the append is a no-op
    that returns False — the gateway shouldn't crash on first message of
    the day."""
    line = "> - claude-code:abc 08:14-08:15 /telegram"
    appended = append_session_line(workspace.shed, line)
    assert appended is False


def test_append_writes_to_existing_note(workspace):
    """The whole pipeline: create today's note, append a line, read back."""
    today = date.today()
    note = workspace.daily_dir / f"{today.isoformat()}.md"
    note.write_text(
        f"# {today.isoformat()} Test\n\n## Intention\n- [ ] x\n", encoding="utf-8",
    )
    line = "> - claude-code:abc 08:14-08:15 /telegram"
    appended = append_session_line(workspace.shed, line)
    assert appended is True
    body = note.read_text(encoding="utf-8")
    assert "> Sessions:" in body
    assert line in body


def test_append_two_lines_to_same_note(workspace):
    today = date.today()
    note = workspace.daily_dir / f"{today.isoformat()}.md"
    note.write_text(
        f"# {today.isoformat()}\n\n## Intention\n- [ ] x\n", encoding="utf-8",
    )
    append_session_line(workspace.shed, "> - claude-code:one 08:00-08:01 /telegram")
    append_session_line(workspace.shed, "> - claude-code:two 09:00-09:01 /telegram")
    body = note.read_text(encoding="utf-8")
    assert "one" in body
    assert "two" in body
    # Chronological order.
    assert body.index("one") < body.index("two")
    # Only one heading line.
    assert body.count("> Sessions:") == 1


# --- SESSION_LINE_RE -------------------------------------------------------


def test_session_line_regex_basic():
    line = "> - claude-code:abc12345 08:14-08:42 /telegram"
    m = SESSION_LINE_RE.match(line)
    assert m is not None
    assert m.group("runtime") == "claude-code"
    assert m.group("sid") == "abc12345"
    assert m.group("start") == "08:14"
    assert m.group("end") == "08:42"
    assert m.group("command") == "/telegram"
    assert m.group("draft") is None


def test_session_line_regex_with_draft():
    line = "> - claude-code:def 11:02-11:05 /daily-start -> drafts/foo.md"
    m = SESSION_LINE_RE.match(line)
    assert m is not None
    assert m.group("draft") == "drafts/foo.md"
