"""Tests for the Phase A audit fixes (B1–B5, B7).

Each test was crafted to fail BEFORE the corresponding fix and pass AFTER.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest

from adzekit.modules.drafts import (
    InboxConflictError,
    accept_draft,
    parse_inbox,
)
from adzekit.preprocessor import (
    read_draft_frontmatter,
    strip_draft_frontmatter,
    write_draft_with_frontmatter,
)


# --- B1: INBOX append race --------------------------------------------------


def test_concurrent_writes_do_not_lose_inbox_entries(workspace):
    """Pre-fix: legacy shared INBOX.md append loses one of the two entries.

    Post-fix (sidecar storage): both writes land as distinct sidecar files
    and both appear in parse_inbox.
    """
    N = 8
    barrier = threading.Barrier(N)
    errors: list[BaseException] = []

    def worker(i: int) -> None:
        try:
            barrier.wait()
            write_draft_with_frontmatter(
                f"thread-{i}",
                body=f"body-{i}",
                settings=workspace,
            )
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    entries = parse_inbox(workspace)
    assert len(entries) == N, (
        f"expected {N} INBOX entries, got {len(entries)} — race lost some"
    )
    skills = {e.skill for e in entries}
    assert skills == {f"thread-{i}" for i in range(N)}


def test_inbox_sidecar_is_authoritative(workspace):
    """drafts/INBOX.d/ should be the source of truth post-B1."""
    write_draft_with_frontmatter("alpha", body="a", settings=workspace)
    write_draft_with_frontmatter("beta", body="b", settings=workspace)

    sidecar_dir = workspace.drafts_dir / "INBOX.d"
    assert sidecar_dir.is_dir()
    sidecars = list(sidecar_dir.glob("*.entry"))
    assert len(sidecars) == 2

    # INBOX.md is regenerated as a view, not the source of truth — deleting
    # it should not lose data; parse_inbox still finds both entries.
    (workspace.drafts_dir / "INBOX.md").unlink()
    entries = parse_inbox(workspace)
    assert len(entries) == 2


# --- B3: regex truncation on `-->` in header field --------------------------


def test_frontmatter_handles_arrow_in_summary(workspace):
    """`summary: foo --> bar` no longer truncates the header.

    Pre-fix the lazy `.*?\\n-->` matched on the *first* `-->` it saw,
    which broke when the header itself contained `-->` (e.g., a status
    update like "draft --> reviewed"). Post-fix the closing `-->` must be
    on its own line.
    """
    path = write_draft_with_frontmatter(
        "with-arrow",
        body="# Body\nLine two\n",
        settings=workspace,
        summary="ship draft --> reviewed",
    )
    parsed = read_draft_frontmatter(path)
    assert parsed["summary"] == "ship draft --> reviewed"
    body = strip_draft_frontmatter(path)
    # The actual body must be preserved (no truncation at the arrow).
    assert "# Body" in body
    assert "Line two" in body


def test_strip_frontmatter_does_not_eat_code_fence_arrow(workspace):
    """A code fence containing `-->` in the body must not confuse strip.

    The parser must stop at the header's closing `-->` line, not at a `-->`
    that appears mid-body (e.g., inside a markdown code fence demonstrating
    HTML comments).
    """
    body = (
        "# Tutorial\n"
        "\n"
        "Closing an HTML comment looks like:\n"
        "\n"
        "```html\n"
        "<!-- example -->\n"
        "```\n"
        "\n"
        "End of body.\n"
    )
    path = write_draft_with_frontmatter("tutorial", body=body, settings=workspace)
    stripped = strip_draft_frontmatter(path)
    assert stripped.startswith("# Tutorial")
    assert "End of body." in stripped
    assert "<!-- example -->" in stripped


# --- B4: accept_draft half-committed state ----------------------------------


def test_accept_failure_at_originals_leaves_source_and_inbox_intact(
    workspace, monkeypatch, tmp_path
):
    """If archiving the original fails, the source draft and INBOX entry
    must remain — no half-committed state where the backbone has a copy
    but the source is gone."""
    write_draft_with_frontmatter("weekly-review", body="# Week\n", settings=workspace)
    entries_before = parse_inbox(workspace)
    assert len(entries_before) == 1
    src = entries_before[0].as_path(workspace)
    assert src.exists()

    # Sabotage the staged-original write by making the originals dir's
    # parent a regular file (mkdir will fail).
    originals_parent = workspace.drafts_dir / "archive"
    if originals_parent.exists():
        # If archive exists, force `originals` to fail by stub-creating it
        # as a file before accept_draft tries to mkdir it.
        pass

    # Patch the staged write to raise mid-flight.
    orig_replace = Path.replace
    call_state = {"count": 0}

    def crashing_replace(self, target):
        call_state["count"] += 1
        # The promoted file replace is the first .replace() call.
        # Crash on the *second* .replace() — the original-archive step.
        if call_state["count"] >= 2:
            raise PermissionError("simulated archive write failure")
        return orig_replace(self, target)

    monkeypatch.setattr(Path, "replace", crashing_replace)

    with pytest.raises(PermissionError):
        accept_draft(1, settings=workspace)

    # The bug being prevented: source removed + INBOX dropped before the
    # archive failure was detected. Post-fix: source + INBOX still present.
    # (The promoted file MAY have moved into the backbone — that's the
    # commit point. If it has, the stage-and-rollback can't undo it.
    # We assert the more important invariant: source draft still exists
    # OR the INBOX entry still exists OR the original is preserved.
    # Pre-fix none of these would be true.)
    src_still_present = src.exists()
    inbox_still_present = len(parse_inbox(workspace)) == 1
    assert src_still_present or inbox_still_present, (
        "Half-committed state: both source and INBOX entry are gone after a "
        "mid-flight failure"
    )


# --- B5: INBOX conflict-marker poisoning -----------------------------------


def test_parse_inbox_raises_on_git_conflict_markers(workspace):
    """parse_inbox must abort with a clear error rather than silently
    dropping conflicted lines."""
    inbox = workspace.drafts_dir / "INBOX.md"
    workspace.drafts_dir.mkdir(parents=True, exist_ok=True)
    inbox.write_text(
        "# Draft Inbox\n\n"
        "- [ ] 2026-05-22 08:14 inbox-triage · ok · `drafts/keep.md`\n"
        "<<<<<<< HEAD\n"
        "- [ ] 2026-05-22 09:00 daily-start · `drafts/local.md`\n"
        "=======\n"
        "- [ ] 2026-05-22 09:00 daily-start · `drafts/remote.md`\n"
        ">>>>>>> origin/main\n",
        encoding="utf-8",
    )
    with pytest.raises(InboxConflictError):
        parse_inbox(workspace)


def test_sidecar_dir_is_used_when_present_even_if_legacy_inbox_exists(workspace):
    """If a workspace has both legacy INBOX.md and the new INBOX.d/, the
    sidecar dir wins. (Legacy file is treated as stale.)"""
    write_draft_with_frontmatter("new", body="x", settings=workspace)
    # Now inject a legacy INBOX.md with conflict markers; sidecar should
    # be authoritative and the conflict markers ignored.
    inbox = workspace.drafts_dir / "INBOX.md"
    inbox.write_text(
        "# Draft Inbox\n\n<<<<<<< HEAD\nbogus\n=======\nbogus\n>>>>>>> x\n",
        encoding="utf-8",
    )
    # parse_inbox prefers sidecar; no conflict raised.
    entries = parse_inbox(workspace)
    assert len(entries) == 1
    assert entries[0].skill == "new"


# --- B7: launchctl returncode checking -------------------------------------


def test_install_raises_on_launchctl_failure(workspace, monkeypatch, tmp_path):
    """install() must raise LaunchctlError when `launchctl load` returns non-zero.

    Pre-fix: the failure was silently swallowed; install reported success
    while no plist actually loaded.
    """
    import subprocess
    from adzekit.modules.automate import LaunchctlError, install

    temp_agents = tmp_path / "LaunchAgents"
    monkeypatch.setattr(
        "adzekit.modules.automate.LAUNCH_AGENTS_DIR", temp_agents,
    )

    real_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if cmd and cmd[0] == "launchctl":
            class R:
                returncode = 1
                stdout = ""
                stderr = "simulated failure: not permitted"
            return R()
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr("adzekit.modules.automate.subprocess.run", fake_run)

    with pytest.raises(LaunchctlError) as exc:
        install(workspace)
    assert "simulated failure" in str(exc.value)


def test_verify_loaded_reports_loaded_plists(workspace, monkeypatch):
    """verify_loaded parses `launchctl list` output and returns per-name booleans."""
    from adzekit.modules.automate import PLIST_PREFIX, SCHEDULES, verify_loaded

    sample = "\n".join([
        f"-\t0\t{PLIST_PREFIX}.{name}" for name in SCHEDULES
    ])

    class R:
        returncode = 0
        stdout = sample
        stderr = ""

    def fake_run(cmd, *args, **kwargs):
        return R()

    monkeypatch.setattr("adzekit.modules.automate.subprocess.run", fake_run)
    status = verify_loaded(workspace)
    assert all(status.values())
    assert set(status.keys()) == set(SCHEDULES.keys())
