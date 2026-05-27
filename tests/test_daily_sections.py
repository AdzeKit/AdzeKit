"""Tests for the four-section daily note format (Triage / Intention / Log / Reflection)."""

from __future__ import annotations

from datetime import date

from adzekit.parser import parse_daily_note


def test_parser_extracts_triage_section():
    text = (
        "# 2026-05-22 Friday\n\n"
        "## Triage\n"
        "- [ ] OVERDUE 12d: Manulife POC → kill / defer / promote\n"
        "- [ ] STALE 9d: aer-compliance → kill / defer / commit\n\n"
        "## Intention\n"
        "- [ ] Top priority\n\n"
        "## Log\n"
        "- 09:00 stuff\n\n"
        "## Reflection\n"
    )
    note = parse_daily_note(text, date(2026, 5, 22))
    assert any("OVERDUE 12d: Manulife POC" in line for line in note.triage)
    assert any("STALE 9d: aer-compliance" in line for line in note.triage)
    assert len(note.intentions) == 1
    assert note.intentions[0].description == "Top priority"
    assert len(note.log) == 1
    assert note.log[0].time == "09:00"


def test_parser_canonical_section_names():
    text = (
        "# 2026-05-22 Friday\n\n"
        "## Triage\n"
        "## Intention\n- [ ] Item\n"
        "## Log\n"
        "## Reflection\n"
    )
    note = parse_daily_note(text, date(2026, 5, 22))
    assert len(note.intentions) == 1


def test_parser_legacy_headings_still_work():
    """Backward compat: existing daily notes with the old headings still parse."""
    text = (
        "# 2026-05-22 Friday\n\n"
        "## Morning: Intention\n- [ ] Legacy item\n"
        "## Log\n"
        "## Evening: Reflection\n- **Tomorrow:** legacy carry\n"
    )
    note = parse_daily_note(text, date(2026, 5, 22))
    assert len(note.intentions) == 1
    assert note.intentions[0].description == "Legacy item"
    assert "legacy carry" in note.tomorrow


def test_parser_triage_excluded_from_intentions():
    """Unchecked items in ## Triage must NOT count as intentions."""
    text = (
        "# 2026-05-22 Friday\n\n"
        "## Triage\n"
        "- [ ] OVERDUE 5d: pseudo-intention → kill / defer / promote\n\n"
        "## Intention\n"
        "- [ ] real intention\n"
    )
    note = parse_daily_note(text, date(2026, 5, 22))
    descriptions = [t.description for t in note.intentions]
    assert "real intention" in descriptions
    assert not any("pseudo-intention" in d for d in descriptions)


def test_parser_empty_triage_section():
    text = (
        "# 2026-05-22 Friday\n\n"
        "## Triage\n\n"
        "## Intention\n- [ ] x\n"
        "## Log\n"
        "## Reflection\n"
    )
    note = parse_daily_note(text, date(2026, 5, 22))
    assert note.triage == []
    assert len(note.intentions) == 1
