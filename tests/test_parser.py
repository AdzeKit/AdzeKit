"""Tests for the markdown parser.

Design doc Section 2.5: The pre-processor reads markdown files and extracts
structured data. The parser module handles the extraction.
"""

from datetime import date

from adzekit.parser import (
    format_loop,
    format_loops,
    format_tasks,
    parse_daily_note,
    parse_loops,
    parse_tasks,
)


class TestParseLoops:
    def test_single_loop(self):
        text = """\
## [2026-01-15] Client X: API integration estimate

- **Who:** Jane Doe (jane@clientx.com)
- **What:** Provide architecture proposal + timeline
- **Due:** 2026-01-18
- **Status:** Draft in progress
- **Next:** Send by EOD Thursday
"""
        loops = parse_loops(text)
        assert len(loops) == 1
        loop = loops[0]
        assert loop.date == date(2026, 1, 15)
        assert loop.title == "Client X: API integration estimate"
        assert loop.who == "Jane Doe (jane@clientx.com)"
        assert loop.what == "Provide architecture proposal + timeline"
        assert loop.due == date(2026, 1, 18)
        assert loop.status == "Draft in progress"
        assert loop.next_action == "Send by EOD Thursday"

    def test_multiple_loops(self):
        text = """\
## [2026-01-15] First loop

- **Who:** Alice
- **What:** Review doc

## [2026-01-16] Second loop

- **Who:** Bob
- **What:** Send report
- **Due:** 2026-01-20
"""
        loops = parse_loops(text)
        assert len(loops) == 2
        assert loops[0].title == "First loop"
        assert loops[1].title == "Second loop"
        assert loops[1].due == date(2026, 1, 20)

    def test_empty_text(self):
        assert parse_loops("") == []
        assert parse_loops("# Open Loops\n\n") == []

    def test_roundtrip(self):
        text = """\
## [2026-02-01] Test loop

- **Who:** Test Person
- **What:** Test something
- **Due:** 2026-02-05
- **Status:** Open
- **Next:** Do the thing
"""
        loops = parse_loops(text)
        output = format_loops(loops)
        reparsed = parse_loops(output)
        assert len(reparsed) == 1
        assert reparsed[0].title == loops[0].title
        assert reparsed[0].who == loops[0].who
        assert reparsed[0].due == loops[0].due


class TestParseTasks:
    def test_checklist(self):
        text = """\
- [ ] First task
- [x] Second task (done)
- [ ] Third task
"""
        tasks = parse_tasks(text)
        assert len(tasks) == 3
        assert not tasks[0].done
        assert tasks[1].done
        assert tasks[2].description == "Third task"

    def test_empty(self):
        assert parse_tasks("") == []

    def test_roundtrip(self):
        text = "- [ ] Alpha\n- [x] Beta\n"
        tasks = parse_tasks(text)
        output = format_tasks(tasks)
        reparsed = parse_tasks(output)
        assert len(reparsed) == 2
        assert reparsed[0].description == "Alpha"
        assert reparsed[1].done


class TestParseDailyNote:
    def test_full_daily_note(self):
        text = """\
# 2026-02-15 Sunday

## Morning: Intention
- [ ] Deep work: Project X (2h block, 9-11am)
- [ ] Close loop: Client Y estimate
- [x] Review: Open loops > 48h old

## Log
- 09:15 Started API design doc
- 10:30 Call with Jane re: timeline
- 14:00 Drafted estimate, sent for review

## Evening: Reflection
- **Finished:** API design doc v1
- **Blocked:** Waiting on security review
- **Tomorrow:** Client Z kickoff, finish estimate
"""
        daily = parse_daily_note(text, date(2026, 2, 15))
        assert daily.date == date(2026, 2, 15)
        assert len(daily.intentions) == 3
        assert daily.intentions[2].done
        assert len(daily.log) == 3
        assert daily.log[0].time == "09:15"
        assert daily.log[0].text == "Started API design doc"
        assert daily.finished == ["API design doc v1"]
        assert daily.blocked == ["Waiting on security review"]
        assert daily.tomorrow == ["Client Z kickoff, finish estimate"]

    def test_empty_daily_note(self):
        daily = parse_daily_note("", date(2026, 1, 1))
        assert daily.intentions == []
        assert daily.log == []
        assert daily.finished == []
