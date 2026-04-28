"""Tests for the bench cull module."""

from adzekit.modules.bench import _parse_bench, _referenced_filenames, cull


def test_cull_adds_new_drafts(workspace):
    drafts = workspace.drafts_dir
    (drafts / "report-2026-03-05.md").write_text("# Test Report\n\nSome content.\n")
    (drafts / "triage-2026-03-05.md").write_text("# Triage Summary\n\nMore content.\n")

    added, cleared = cull(workspace)

    assert added == 2
    assert cleared == 0

    content = workspace.bench_path.read_text()
    assert "report-2026-03-05.md" in content
    assert "triage-2026-03-05.md" in content
    assert "Test Report" in content
    assert "Triage Summary" in content


def test_cull_is_idempotent(workspace):
    drafts = workspace.drafts_dir
    (drafts / "report.md").write_text("# Report\n")

    cull(workspace)
    added, cleared = cull(workspace)

    assert added == 0
    assert cleared == 0


def test_cull_clears_checked_items(workspace):
    workspace.bench_path.write_text(
        "# Bench\n\n"
        "## Pending\n"
        "- [x] [2026-03-05 14:00] Old Report (old-report.md)\n"
        "- [ ] [2026-03-05 15:00] Keep This (keep-this.md)\n\n"
        "## Quick Capture\n"
    )
    drafts = workspace.drafts_dir
    (drafts / "keep-this.md").write_text("# Keep This\n")

    added, cleared = cull(workspace)

    assert cleared == 1
    content = workspace.bench_path.read_text()
    assert "old-report.md" not in content
    assert "keep-this.md" in content


def test_cull_skips_non_md_files(workspace):
    drafts = workspace.drafts_dir
    (drafts / "data.json").write_text("{}")
    (drafts / "notes.md").write_text("# Notes\n")

    added, _ = cull(workspace)

    assert added == 1
    content = workspace.bench_path.read_text()
    assert "data.json" not in content


def test_cull_skips_subdirectories(workspace):
    drafts = workspace.drafts_dir
    sessions = drafts / "sessions"
    sessions.mkdir()
    (sessions / "chat.json").write_text("{}")
    (drafts / "draft.md").write_text("# Draft\n")

    added, _ = cull(workspace)

    assert added == 1


def test_cull_creates_bench_if_missing(workspace):
    workspace.bench_path.unlink()
    assert not workspace.bench_path.exists()

    drafts = workspace.drafts_dir
    (drafts / "new-draft.md").write_text("# New Draft\n")

    added, _ = cull(workspace)

    assert added == 1
    assert workspace.bench_path.exists()
    content = workspace.bench_path.read_text()
    assert "## Pending" in content
    assert "## Quick Capture" in content


def test_cull_preserves_quick_capture(workspace):
    workspace.bench_path.write_text(
        "# Bench\n\n"
        "## Pending\n\n"
        "## Quick Capture\n"
        "- [2026-03-05] Remember to call Alice\n"
    )

    added, _ = cull(workspace)

    content = workspace.bench_path.read_text()
    assert "Remember to call Alice" in content


def test_cull_with_empty_drafts(workspace):
    added, cleared = cull(workspace)

    assert added == 0
    assert cleared == 0


def test_cull_entry_format(workspace):
    drafts = workspace.drafts_dir
    (drafts / "inbox-zero-2026-03-05-1430.md").write_text(
        "# Inbox Zero -- 2026-03-05 14:30\n\nTriage report.\n"
    )

    cull(workspace)

    content = workspace.bench_path.read_text()
    assert "- [ ]" in content
    assert "inbox-zero-2026-03-05-1430.md" in content
    assert "Inbox Zero" in content


def test_parse_bench_structure():
    text = (
        "# Bench\n\n"
        "## Pending\n"
        "- [ ] [2026-03-05 14:00] Item (file.md)\n\n"
        "## Quick Capture\n"
        "- [2026-03-05] A thought\n"
    )
    header, pending, rest = _parse_bench(text)

    assert "## Pending" in header[-1]
    assert any("file.md" in line for line in pending)
    assert any("Quick Capture" in line for line in rest)


def test_referenced_filenames():
    lines = [
        "- [ ] [2026-03-05 14:00] Report (report.md)",
        "- [x] [2026-03-04 10:00] Old (old.md)",
        "",
        "some random text",
    ]
    names = _referenced_filenames(lines)
    assert names == {"report.md", "old.md"}


def test_cli_cull(tmp_path):
    from adzekit.cli import main

    target = tmp_path / "shed"
    main(["init", str(target)])

    drafts = target / "drafts"
    (drafts / "test-draft.md").write_text("# Test Draft\n")

    main(["--shed", str(target), "cull"])

    content = (target / "bench.md").read_text()
    assert "test-draft.md" in content
    assert "Test Draft" in content
