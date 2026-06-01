"""AdzeKit CLI -- command-line interface for operating on any backbone-conforming shed.

Usage:
    adzekit init [path]                    Initialize a new shed at path (default: cwd)
    adzekit use-workspace <url>            Clone/update a git workspace and set it as shed
    adzekit today                          Open or create today's daily note
    adzekit add-loop                       Add a loop to open.md
    adzekit status                         Show shed health summary
    adzekit sync [pull|push]               Sync shed via git and rclone (stock/ + drafts/)
    adzekit setup-sync                     Configure rclone for Google Drive sync
    adzekit serve                          Start the local web UI
    adzekit agent <message>                Run the agent with a one-shot message
"""

import argparse
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path


def _resolve_settings(args: argparse.Namespace, *, require_init: bool = True):
    """Build a Settings instance from CLI args.

    Resolution order:
      1. --shed flag on the command line
      2. ADZEKIT_SHED environment variable  (handled inside get_settings)
      3. ~/.config/adzekit/config           (written by ``adzekit set-shed``)
      4. Default ~/adzekit

    When require_init is True (the default), raises ShedNotInitializedError
    if the resolved shed directory does not contain a .adzekit marker file.
    Only ``init`` and ``adze`` should pass require_init=False.
    """
    from adzekit.config import Settings, get_settings

    shed = getattr(args, "shed", None)
    if shed:
        # Explicit --shed flag overrides everything
        settings = Settings(shed=Path(shed).expanduser().resolve())
    else:
        # Use get_settings() so ~/.config/adzekit/config is honoured
        settings = get_settings()

    if require_init:
        settings.require_initialized()
    return settings


ADZE = r"""
   //\\
  //  \\
 //
//

 A D Z E K I T
"""


# -- adze ------------------------------------------------------------------


def cmd_adze(args: argparse.Namespace) -> None:
    """Print the AdzeKit symbol."""
    print(ADZE)


# -- init ------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> None:
    """Initialize a new AdzeKit shed with the full backbone structure."""
    from adzekit.config import Settings
    from adzekit.workspace import init_shed

    path = Path(args.path).expanduser().resolve() if args.path else Path.cwd()
    settings = Settings(shed=path)
    root = init_shed(settings)

    # Print the tree that was created
    print(f"Initialized AdzeKit shed at {root}\n")
    _print_tree(root, root)


def _print_tree(root: Path, base: Path, prefix: str = "") -> None:
    """Print a directory tree rooted at base, showing only dirs and .md files."""
    entries = sorted(base.iterdir(), key=lambda p: (not p.is_dir(), p.name))
    # Filter: show dirs (skip hidden) and .md files
    entries = [
        e for e in entries
        if (e.is_dir() and not e.name.startswith("."))
        or e.suffix == ".md"
    ]
    for i, entry in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "
        name = entry.name
        if entry.is_dir():
            print(f"{prefix}{connector}{name}/")
            extension = "    " if is_last else "│   "
            _print_tree(root, entry, prefix + extension)
        else:
            print(f"{prefix}{connector}{name}")


# -- today -----------------------------------------------------------------


def cmd_today(args: argparse.Namespace) -> None:
    """Create (if needed) and print the path to today's daily note."""
    from adzekit.workspace import create_daily_note

    settings = _resolve_settings(args)
    path = create_daily_note(settings=settings)
    print(path)


# -- daily-start -----------------------------------------------------------


def cmd_daily_start(args: argparse.Namespace) -> None:
    """Bootstrap today's daily note from yesterday's context and active loops.

    Also syncs workbench (pull) and refreshes tag autocomplete.
    """
    from adzekit.modules.daily import daily_start

    settings = _resolve_settings(args)
    target = date.fromisoformat(args.date) if args.date else None
    path, summary = daily_start(target_date=target, settings=settings)

    if summary.get("synced"):
        print("Synced workbench from remote (stock is additive-only).")
    if summary.get("tags_refreshed"):
        print("Tag snippets refreshed.")

    if summary.get("already_exists"):
        print(f"Today's note already exists at daily/{summary['date']}.md")
        return

    print(f"Daily Start -- {summary['date']} ({summary['weekday']})")
    print(f"  Proposed tasks: {summary['proposed_tasks']}")
    print(f"  Overdue loops:  {summary['overdue_count']}")
    print(f"  Due today:      {summary['due_today_count']}")
    print(f"  Carried:        {summary['carried_count']}")
    print(f"  Active loops:   {summary['active_loops_total']}")
    print(f"  Written:        {path}")


# -- daily-close -----------------------------------------------------------


def cmd_daily_close(args: argparse.Namespace) -> None:
    """Append reflection line to today's note, sweep loops, and push workbench."""
    from adzekit.modules.daily import daily_close

    settings = _resolve_settings(args)
    target = date.fromisoformat(args.date) if args.date else None
    success, summary = daily_close(target_date=target, settings=settings)

    if summary.get("no_note"):
        print(f"No daily note for {summary['date']}. "
              "Run `adzekit daily-start` first.")
        return
    if summary.get("already_closed"):
        print("Today's note already has an > End: line.")
        return

    print(f"Daily Close -- {summary['date']}")
    print(f"  Done:        {summary['done_count']}")
    print(f"  Open:        {summary['open_count']}")
    print(f"  Log entries: {summary['log_count']}")
    print(f"  Tomorrow:    {summary['tomorrow_suggestion']}")
    if summary.get("swept_count", 0) > 0:
        print(f"  Swept:       {summary['swept_count']} loop(s) to archive")
    if summary.get("synced"):
        print("  Pushed workbench to remote.")
    if summary.get("tags_refreshed"):
        print("  Tag snippets refreshed.")


# -- prune-drafts ----------------------------------------------------------


def cmd_prune_drafts(args: argparse.Namespace) -> None:
    """Delete stale draft files from drafts/."""
    from adzekit.modules.drafts import prune_drafts

    settings = _resolve_settings(args)
    deleted = prune_drafts(days=args.days, settings=settings)

    if not deleted:
        print("No stale drafts to prune.")
    else:
        for p in deleted:
            print(f"  deleted: {p.name}")
        print(f"\n{len(deleted)} draft(s) pruned.")


# -- drafts (accept/dismiss/gc/list) ---------------------------------------


def cmd_drafts(args: argparse.Namespace) -> None:
    """Dispatch the `drafts` subcommand."""
    sub = getattr(args, "drafts_command", None)
    if sub is None:
        # Default: list pending drafts in INBOX
        _drafts_list(args)
        return
    sub(args)


def _drafts_list(args: argparse.Namespace) -> None:
    from adzekit.modules.drafts import parse_inbox

    settings = _resolve_settings(args)
    entries = parse_inbox(settings)
    if not entries:
        print("INBOX is empty.")
        return
    for e in entries:
        prefix = "[x]" if e.state.lower() == "x" else "[ ]"
        summary = f" · {e.summary}" if e.summary else ""
        print(f"  {e.index:>3}. {prefix} {e.date} {e.time} {e.skill}{summary}  ({e.path})")


def _drafts_accept(args: argparse.Namespace) -> None:
    from adzekit.modules.drafts import (
        InboxEntryNotFoundError,
        InboxNotFoundError,
        accept_draft,
    )

    settings = _resolve_settings(args)
    try:
        target_override = Path(args.to).expanduser().resolve() if args.to else None
        promoted, original = accept_draft(
            args.index,
            settings=settings,
            target=target_override,
            preserve_original=not args.no_preserve,
        )
    except (InboxNotFoundError, InboxEntryNotFoundError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print(f"Accepted #{args.index} -> {promoted}")
    if original.name:
        print(f"  original preserved at {original}")


def _drafts_dismiss(args: argparse.Namespace) -> None:
    from adzekit.modules.drafts import (
        InboxEntryNotFoundError,
        InboxNotFoundError,
        dismiss_draft,
    )

    settings = _resolve_settings(args)
    try:
        archived = dismiss_draft(args.index, settings=settings)
    except (InboxNotFoundError, InboxEntryNotFoundError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print(f"Dismissed #{args.index} -> {archived}")


def _drafts_gc(args: argparse.Namespace) -> None:
    from adzekit.modules.drafts import gc_drafts

    settings = _resolve_settings(args)
    archived = gc_drafts(days=args.days, settings=settings)
    if not archived:
        print("No stale drafts to gc.")
        return
    for p in archived:
        print(f"  archived: {p.name}")
    print(f"\n{len(archived)} draft(s) gc'd.")


def _drafts_show(args: argparse.Namespace) -> None:
    from adzekit.modules.drafts import (
        InboxEntryNotFoundError,
        show_draft,
    )

    settings = _resolve_settings(args)
    try:
        result = show_draft(
            args.index,
            settings=settings,
            include_frontmatter=args.with_frontmatter,
        )
    except (InboxEntryNotFoundError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
    # Compact provenance summary, then the body.
    print(f"draft #{result['index']} — {result['path']}")
    print(f"  skill:      {result['skill']}")
    if result["summary"]:
        print(f"  summary:    {result['summary']}")
    if result["triggered"]:
        print(f"  triggered:  {result['triggered']}")
    if result["confidence"]:
        print(f"  confidence: {result['confidence']}")
    if result["inputs"]:
        print(f"  inputs:     {', '.join(result['inputs'])}")
    print()
    print(result["body"].rstrip("\n"))


def _drafts_rollback(args: argparse.Namespace) -> None:
    from adzekit.modules.drafts import rollback_draft

    settings = _resolve_settings(args)
    try:
        result = rollback_draft(
            settings=settings,
            filename=args.filename,
        )
    except (FileNotFoundError, FileExistsError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print(f"Restored draft: {result['restored']}")
    print(f"  INBOX entry:  {result['inbox_entry']}")
    if result["removed_from_backbone"]:
        print(f"  Removed from backbone: {result['removed_from_backbone']}")
    else:
        print(
            "  Note: backbone copy was either absent or edited since accept; "
            "left alone. Inspect manually and remove if desired."
        )


# -- adapter ---------------------------------------------------------------


def cmd_adapter(args: argparse.Namespace) -> None:
    """Install, uninstall, or report status for an AdzeKit adapter."""
    name = args.name

    if name == "claude-code":
        from adzekit.modules.adapters import (
            install_claude_code,
            status_claude_code,
            uninstall_claude_code,
        )

        if args.action == "install":
            result = install_claude_code()
            print(f"Installed claude-code adapter at {result['target']}")
            print(f"  skills: {len(result['skills_copied'])}")
            print(f"  mirrored: {', '.join(result['mirrored_dirs'])}")
        elif args.action == "uninstall":
            result = uninstall_claude_code()
            if result["removed"]:
                print(f"Removed claude-code adapter from {result['target']}")
            else:
                print(f"claude-code adapter not installed at {result['target']}")
        elif args.action == "status":
            result = status_claude_code()
            marker = "✓" if result["installed"] else "✗"
            print(f"  {marker} claude-code  installed={result['installed']}")
            print(f"      target: {result['target']}")
            if result["installed"]:
                print(
                    f"      skills: {result['skills']}, "
                    f"commands: {result['commands']}, "
                    f"agents: {result['agents']}"
                )
    elif name == "gmail":
        from adzekit.modules.adapters_gmail import (
            install_gmail,
            status_gmail,
            uninstall_gmail,
        )
        settings = _resolve_settings(args)
        if args.action == "install":
            result = install_gmail(settings)
            if not result["installed"]:
                print(f"Gmail install failed: {result['reason']}", file=sys.stderr)
                raise SystemExit(1)
            print(f"Gmail adapter installed. {result['labels_total']} labels found.")
            if result["missing_labels"]:
                print(f"  Missing expected labels: {', '.join(result['missing_labels'])}")
                print(
                    "  Create them in Gmail's UI (Settings → Labels) or via the"
                    " Gmail API to unlock inbox-triage's labeling features."
                )
            print(f"  Cache: {result['cache_path']}")
        elif args.action == "status":
            result = status_gmail(settings)
            marker = "✓" if result["ready"] else "✗"
            print(f"  {marker} Gmail ready: {result['ready']}")
            if not result["ready"]:
                print(f"  Reason: {result['reason']}")
            else:
                print(f"  Cache present: {result['cache_present']}")
                if result["missing_labels"]:
                    print(f"  Missing labels: {', '.join(result['missing_labels'])}")
        elif args.action == "uninstall":
            result = uninstall_gmail(settings)
            if result["removed_cache"]:
                print("Removed Gmail label cache.")
            else:
                print("No Gmail cache to remove.")
            print(f"  {result['note']}")
    elif name == "google-calendar":
        from adzekit.modules.adapters_calendar import (
            install_calendar,
            status_calendar,
            uninstall_calendar,
        )
        settings = _resolve_settings(args)
        if args.action == "install":
            result = install_calendar(settings)
            if not result["installed"]:
                print(
                    f"Calendar install failed: {result['reason']}", file=sys.stderr,
                )
                raise SystemExit(1)
            print(
                f"Calendar adapter installed. "
                f"{result['calendars_total']} calendar(s) found."
            )
            if result["primary_id"]:
                print(f"  Primary: {result['primary_id']}")
            print(f"  Cache: {result['cache_path']}")
        elif args.action == "status":
            result = status_calendar(settings)
            marker = "✓" if result["ready"] else "✗"
            print(f"  {marker} Calendar ready: {result['ready']}")
            if not result["ready"]:
                print(f"  Reason: {result['reason']}")
            else:
                print(f"  Cached calendars: {len(result['calendars'])}")
        elif args.action == "uninstall":
            result = uninstall_calendar(settings)
            if result["removed_cache"]:
                print("Removed Calendar list cache.")
            else:
                print("No Calendar cache to remove.")
    else:
        print(f"Unknown adapter: {name}", file=sys.stderr)
        raise SystemExit(2)


# -- calendar (terminal briefing) ------------------------------------------


def cmd_calendar(args: argparse.Namespace) -> None:
    """Print today's calendar briefing to terminal."""
    from adzekit.modules.adapters_calendar import format_today_briefing

    text = format_today_briefing(calendar_id=args.calendar)
    print(text)


# -- gateway ---------------------------------------------------------------


def cmd_gateway(args: argparse.Namespace) -> None:
    """Start the gateway daemon (Telegram bridge by default)."""
    import os
    from pathlib import Path as _Path

    # Auto-load ~/.config/adzekit/gateway.env if present and vars not already set.
    gateway_env = _Path.home() / ".config" / "adzekit" / "gateway.env"
    if gateway_env.exists():
        for _line in gateway_env.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if not _line or _line.startswith("#"):
                continue
            _key, _sep, _val = _line.partition("=")
            if _sep and _key not in os.environ:
                os.environ[_key] = _val

    if args.transport != "telegram":
        print(f"Unknown gateway transport: {args.transport}", file=sys.stderr)
        raise SystemExit(2)
    try:
        from adzekit.gateway.telegram import run
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
    try:
        run()
    except KeyboardInterrupt:
        print("\nGateway stopped.")


# -- mcp -------------------------------------------------------------------


def cmd_mcp(args: argparse.Namespace) -> None:
    """Manage AdzeKit MCP server wiring in ~/.claude/settings.json."""
    from adzekit.modules.mcp_install import (
        install_mcp,
        status_mcp,
        uninstall_mcp,
    )

    settings = _resolve_settings(args)
    only = None
    if args.only:
        only = [s.strip() for s in args.only.split(",") if s.strip()]

    if args.action == "install":
        try:
            result = install_mcp(settings, only=only)
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            raise SystemExit(1)
        if not result["installed"] and not result["skipped"]:
            print("No MCP servers to install.")
            return
        for row in result["installed"]:
            marker = "✓" if row["binary_on_path"] else "⚠"
            print(f"  {marker} installed {row['name']} ({row['command']})")
            if not row["binary_on_path"]:
                print(
                    f"      binary not on PATH yet; "
                    f"run `uv pip install -e .` (or `pip install -e .`)"
                )
        for row in result["skipped"]:
            print(f"  ✗ skipped {row['name']}: {row['reason']}")
        if result["installed"]:
            print(f"\nSettings: {result['settings_path']}")
            print(f"Shed:     {result['shed']}")
            print("Restart Claude Code for changes to take effect.")
    elif args.action == "uninstall":
        try:
            result = uninstall_mcp(only=only)
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            raise SystemExit(1)
        if result["removed"]:
            for name in result["removed"]:
                print(f"  removed {name}")
        else:
            print("No AdzeKit MCP entries present in settings.json.")
    elif args.action == "status":
        result = status_mcp(settings)
        if not result["settings_parseable"]:
            print(f"  ✗ {result['settings_path']} is not valid JSON")
            return
        print(f"  settings: {result['settings_path']}")
        print(f"  shed:     {result['current_shed']}")
        print()
        for row in result["servers"]:
            reg = "✓" if row["registered"] else "✗"
            binm = "✓" if row["binary_on_path"] else "✗"
            ready = "✓" if row["adapter_ready"] else "✗"
            print(
                f"  registered:{reg}  binary:{binm}  adapter:{ready}  {row['name']}"
            )
            if row["registered"] and not row["shed_matches"]:
                print(
                    f"      Warning: configured shed {row['configured_shed']!r} "
                    f"doesn't match current shed."
                )


# -- insight ---------------------------------------------------------------


def cmd_insight(args: argparse.Namespace) -> None:
    """Run the insight extractors and write a draft for the given period."""
    from adzekit.modules.insights import run_insight

    settings = _resolve_settings(args)
    target = None
    if args.date:
        from datetime import date as _date
        try:
            target = _date.fromisoformat(args.date)
        except ValueError as exc:
            print(f"Error: invalid --date {args.date!r}: {exc}", file=sys.stderr)
            raise SystemExit(2)
    try:
        data, draft_path = run_insight(
            period=args.period, settings=settings, target=target,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2)
    if draft_path is None:
        print("Insight rendered (write skipped).")
        return
    print(f"Insight written: {draft_path.relative_to(settings.shed)}")
    print(f"  window: {data.window_start} → {data.window_end}")
    print(
        f"  velocity: {data.velocity.opened} opened / {data.velocity.closed} closed"
    )
    print(f"  carry-forwards: {len(data.carry_forwards)}")
    print(f"  energy samples: {data.energy.samples}")
    print(f"  top tags: {len(data.tags)}")


# -- distill ---------------------------------------------------------------


def cmd_distill(args: argparse.Namespace) -> None:
    """Detect repeated edit patterns in accepted drafts and emit proposals."""
    from adzekit.modules.distill import run_distill

    settings = _resolve_settings(args)
    proposals = run_distill(
        settings=settings,
        min_occurrences=args.min_occurrences,
        window_days=args.window_days,
    )
    if not proposals:
        print("No patterns repeated enough to distill (try lowering --min-occurrences).")
        return
    for p in proposals:
        print(f"  proposed: {p.relative_to(settings.shed)}")
    print(f"\n{len(proposals)} skill proposal(s) written to drafts/skill-proposals/.")
    print("Review with `adzekit drafts list`; promote with `adzekit drafts accept <N>`.")


# -- automate --------------------------------------------------------------


def cmd_automate(args: argparse.Namespace) -> None:
    """Install, uninstall, or check status of launchd cadence plists."""
    from adzekit.modules.automate import (
        LAUNCH_AGENTS_DIR,
        PLIST_PREFIX,
        SCHEDULES,
        in_deep_work_window,
        install,
        uninstall,
    )

    settings = _resolve_settings(args)

    if args.action == "install":
        paths = install(settings)
        for p in paths:
            print(f"  installed: {p.name}")
        print(f"\n{len(paths)} plist(s) installed and loaded.")
    elif args.action == "uninstall":
        paths = uninstall(settings)
        if not paths:
            print("No plists found to uninstall.")
        else:
            for p in paths:
                print(f"  removed: {p.name}")
            print(f"\n{len(paths)} plist(s) unloaded and removed.")
    elif args.action == "status":
        from adzekit.modules.automate import verify_loaded
        loaded = verify_loaded(settings)
        installed_count = 0
        loaded_count = 0
        for name in SCHEDULES:
            path = LAUNCH_AGENTS_DIR / f"{PLIST_PREFIX}.{name}.plist"
            present = path.exists()
            is_loaded = loaded.get(name, False)
            file_marker = "✓" if present else "✗"
            load_marker = "✓" if is_loaded else "✗"
            print(f"  file:{file_marker} loaded:{load_marker} {name:20s} {path}")
            if present:
                installed_count += 1
            if is_loaded:
                loaded_count += 1
        guard = in_deep_work_window(settings=settings)
        print(f"\n{installed_count}/{len(SCHEDULES)} plist file(s) on disk.")
        print(f"{loaded_count}/{len(SCHEDULES)} plist(s) loaded into launchd.")
        if installed_count > loaded_count:
            print(
                "Warning: some plists are on disk but not loaded. "
                "Run `adzekit cadence uninstall && adzekit cadence install` "
                "(check logout status, SIP, permissions)."
            )
        print(f"Deep-work window active right now: {guard}")


# -- review ----------------------------------------------------------------


def cmd_review(args: argparse.Namespace) -> None:
    """Create (if needed) and print the path to this week's review."""
    from adzekit.workspace import create_review

    settings = _resolve_settings(args)
    review_date = date.fromisoformat(args.date) if args.date else None
    path = create_review(target_date=review_date, settings=settings)
    print(path)


def cmd_weekly_review(args: argparse.Namespace) -> None:
    """Cull the shed and write this week's pulse summary."""
    from adzekit.modules.weekly import run_weekly_review

    settings = _resolve_settings(args)
    target = date.fromisoformat(args.date) if args.date else None
    summary = run_weekly_review(settings, target=target)

    if summary["bench_cleared"]:
        print(f"  cleared {summary['bench_cleared']} processed/orphan item(s) from bench")
    if summary["bench_added"]:
        print(f"  added {summary['bench_added']} new draft(s) to bench")
    if summary["archived_dailies"]:
        print(
            f"  archived {len(summary['archived_dailies'])} daily note(s) "
            f"to {settings.daily_archive_dir}"
        )

    print(f"Weekly Review — {summary['week_label']}")
    print(f"  window: {summary['window_start']} → {summary['window_end']}")
    print(f"  pulse:  {summary['pulse_path'].relative_to(settings.shed)}")


# -- sweep -----------------------------------------------------------------


def _log_sweep_to_daily(count: int, settings) -> None:
    """Append a sweep entry to today's daily note under ## Log."""
    from adzekit.workspace import create_daily_note

    path = create_daily_note(settings=settings)
    content = path.read_text(encoding="utf-8")

    entry = f"- Swept {count} loop(s) closed"
    # Insert after the ## Log heading
    marker = "## Log"
    idx = content.find(marker)
    if idx == -1:
        # No Log section -- append to end
        content = content.rstrip() + f"\n\n{entry}\n"
    else:
        insert_at = idx + len(marker)
        # Skip any trailing whitespace/newline right after the heading
        while insert_at < len(content) and content[insert_at] == "\n":
            insert_at += 1
        content = content[:insert_at] + entry + "\n" + content[insert_at:]

    path.write_text(content, encoding="utf-8")


def cmd_sweep(args: argparse.Namespace) -> None:
    """Move all [x] loops from active.md to archive.md."""
    from adzekit.modules.loops import sweep_closed

    settings = _resolve_settings(args)
    swept = sweep_closed(settings)
    if not swept:
        print("Nothing to sweep -- no closed loops in active.md.")
    else:
        _log_sweep_to_daily(len(swept), settings)
        for loop in swept:
            print(f"  swept: {loop.title}")
        print(f"\n{len(swept)} loop(s) moved to archive.md")


# -- cull ------------------------------------------------------------------


def cmd_cull(args: argparse.Namespace) -> None:
    """Scan drafts/ and update bench.md, then archive old daily notes."""
    from adzekit.modules.bench import cull
    from adzekit.modules.daily import archive_old_dailies

    settings = _resolve_settings(args)
    added, cleared = cull(settings)
    archived = archive_old_dailies(settings)

    if not added and not cleared and not archived:
        print("Bench and daily are up to date -- nothing to clear or archive.")
    else:
        if cleared:
            print(f"  cleared {cleared} processed/orphan item(s) from bench")
        if added:
            print(f"  added {added} new draft(s) to bench")
        if archived:
            print(f"  archived {len(archived)} daily note(s) to {settings.daily_archive_dir}")
        print(f"\nBench updated: {settings.bench_path}")


# -- add-loop --------------------------------------------------------------


def cmd_add_loop(args: argparse.Namespace) -> None:
    """Add a new loop to open.md."""
    from adzekit.models import Loop
    from adzekit.modules.loops import add_loop

    settings = _resolve_settings(args)
    due = date.fromisoformat(args.due) if args.due else None
    loop = Loop(
        date=date.today(),
        title=args.title,
        who=args.who or "",
        what=args.what or "",
        due=due,
        status="Open",
        next_action=args.next or "",
        project=args.project or "",
        size=args.size or "",
    )
    add_loop(loop, settings)
    print(f"Added loop: {args.title}")


# -- tags ------------------------------------------------------------------


def cmd_tags(args: argparse.Namespace) -> None:
    """List tags, search by prefix, or generate Cursor autocomplete snippets."""
    from adzekit.modules.tags import all_tags, files_for_tag, generate_cursor_snippets

    settings = _resolve_settings(args)

    if args.completions:
        path = generate_cursor_snippets(settings)
        print(f"Generated Cursor snippets: {path}")
        return

    if args.search:
        files = files_for_tag(args.search, settings)
        if not files:
            print(f"No files tagged #{args.search.lstrip('#')}")
            return
        tag = args.search.lstrip("#").lower()
        print(f"#{tag} ({len(files)} files):")
        for f in files:
            print(f"  {f.relative_to(settings.shed)}")
        return

    tags = all_tags(settings)
    if not tags:
        print("No tags found.")
        return
    for tag in tags:
        print(f"  #{tag}")
    print(f"\n{len(tags)} tags")


# -- project ---------------------------------------------------------------


def cmd_project(args: argparse.Namespace) -> None:
    """Create a new project file from the backbone template."""
    import sys

    from adzekit.modules.wip import can_activate
    from adzekit.workspace import create_project

    settings = _resolve_settings(args)

    if args.active:
        allowed, reason = can_activate(settings)
        if not allowed:
            from adzekit.modules.git_age import project_ages
            ages = [a for a in project_ages(settings)
                    if a.path.parent == settings.active_dir]
            stalest = ages[0] if ages else None
            print(f"Error: {reason}", file=sys.stderr)
            if stalest is not None:
                print(
                    f"Most stale active project: {stalest.path.stem} "
                    f"({stalest.stale_days}d). "
                    f"Try: adzekit demote {stalest.path.stem}",
                    file=sys.stderr,
                )
            raise SystemExit(1)

    path = create_project(
        slug=args.slug,
        title=args.title or "",
        backlog=not args.active,
        settings=settings,
    )
    print(path)


def cmd_demote(args: argparse.Namespace) -> None:
    """Move an active project back to backlog/."""
    import sys

    from adzekit.modules.wip import demote_project

    settings = _resolve_settings(args)
    try:
        path = demote_project(args.slug, settings=settings)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print(path)


def cmd_promote(args: argparse.Namespace) -> None:
    """Move a backlog project to active/ (hard-blocked at WIP cap)."""
    import sys

    from adzekit.modules.wip import activate_project

    settings = _resolve_settings(args)
    try:
        path = activate_project(args.slug, settings=settings)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print(path)


# -- export ----------------------------------------------------------------


def cmd_export(args: argparse.Namespace) -> None:
    """Export a markdown file to docx via pandoc."""
    from adzekit.modules.export import to_docx

    settings = _resolve_settings(args)
    raw = Path(args.file)
    # Resolve relative paths against the shed root
    source = raw if raw.is_absolute() else (settings.shed / raw)
    source = source.expanduser().resolve()

    output = None
    if args.output:
        raw_out = Path(args.output)
        output = raw_out if raw_out.is_absolute() else (settings.shed / raw_out)
        output = output.expanduser().resolve()

    docx_path = to_docx(source, output)
    print(f"Exported: {docx_path}")


# -- status ----------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> None:
    """Print a summary of shed health."""
    from adzekit.modules.git_age import project_ages
    from adzekit.modules.loops import loop_stats
    from adzekit.modules.wip import wip_status

    settings = _resolve_settings(args)
    wip = wip_status(settings)
    loops = loop_stats(settings)

    print(f"Shed: {settings.shed}")
    print(f"Active projects: {wip['active_projects']}/{wip['max_active_projects']}")
    print(f"Daily tasks: {wip['daily_tasks']}/{wip['max_daily_tasks']}")
    print(f"Active loops: {loops['active']}")
    print(f"Overdue loops: {loops['overdue']}")
    print(f"Approaching SLA: {loops['approaching_sla']}")

    ages = project_ages(settings)
    if ages:
        print("\nProject ages:")
        for a in ages:
            name = a.path.stem
            stale = f"{a.stale_days}d ago" if a.stale_days is not None else "untracked"
            created = f"{a.age_days}d old" if a.age_days is not None else ""
            print(f"  {name}: modified {stale}" + (f", {created}" if created else ""))


# -- graph -----------------------------------------------------------------


def cmd_graph(args: argparse.Namespace) -> None:
    """Knowledge graph operations."""
    sub = getattr(args, "graph_command", None)
    if sub == "build":
        _cmd_graph_build(args)
    elif sub == "query":
        _cmd_graph_query(args)
    elif sub == "stats":
        _cmd_graph_stats(args)
    elif sub == "orphans":
        _cmd_graph_orphans(args)
    else:
        print("graph: specify a subcommand (build, query, stats, orphans)")


def _cmd_graph_build(args: argparse.Namespace) -> None:
    from adzekit.modules.graph import build_graph, graph_stats, save_graph

    settings = _resolve_settings(args)
    print("Building knowledge graph...")
    graph = build_graph(settings)
    save_graph(graph, settings)
    stats = graph_stats(graph)
    print(
        f"Graph built: {stats['total_entities']} entities, "
        f"{stats['total_relationships']} relationships"
    )
    print(
        f"  {stats['people']} people  {stats['organizations']} orgs  "
        f"{stats['projects']} projects  {stats['concepts']} concepts  "
        f"{stats['tools']} tools  {stats['loops']} loops"
    )
    print(f"  Written to: {settings.graph_dir}")


def _cmd_graph_query(args: argparse.Namespace) -> None:
    from adzekit.modules.graph import get_context, load_graph

    settings = _resolve_settings(args)
    graph = load_graph(settings)
    if graph is None:
        print("No graph found. Run: adzekit graph build")
        raise SystemExit(1)
    depth = getattr(args, "depth", 2)
    print(get_context(args.entity, graph, depth=depth))


def _cmd_graph_stats(args: argparse.Namespace) -> None:
    from adzekit.modules.graph import graph_stats, load_graph

    settings = _resolve_settings(args)
    graph = load_graph(settings)
    if graph is None:
        print("No graph found. Run: adzekit graph build")
        raise SystemExit(1)
    stats = graph_stats(graph)
    built = graph.built_at.isoformat() if graph.built_at else "unknown"
    print(f"Built:         {built}")
    print(f"Entities:      {stats['total_entities']}")
    print(f"  People:      {stats['people']}")
    print(f"  Orgs:        {stats['organizations']}")
    print(f"  Projects:    {stats['projects']}")
    print(f"  Concepts:    {stats['concepts']}")
    print(f"  Tools:       {stats['tools']}")
    print(f"  Loops:       {stats['loops']}")
    print(f"Relationships: {stats['total_relationships']}")


def _cmd_graph_orphans(args: argparse.Namespace) -> None:
    from adzekit.modules.graph import load_graph

    settings = _resolve_settings(args)
    graph = load_graph(settings)
    if graph is None:
        print("No graph found. Run: adzekit graph build")
        raise SystemExit(1)
    connected = (
        {r.source for r in graph.relationships}
        | {r.target for r in graph.relationships}
    )
    orphans = sorted(
        (e for e in graph.entities.values() if e.name not in connected),
        key=lambda e: (e.entity_type.value, e.name),
    )
    if not orphans:
        print("No orphans -- all entities are connected.")
        return
    print(f"{len(orphans)} orphan(s):")
    for e in orphans:
        print(f"  {e.name} ({e.entity_type.value})")


# -- set-shed --------------------------------------------------------------


def cmd_set_shed(args: argparse.Namespace) -> None:
    """Persist the shed path to ~/.config/adzekit/config for all future sessions."""
    from adzekit.config import GLOBAL_CONFIG_PATH, set_global_shed

    shed_path = Path(args.path).expanduser().resolve()

    if not shed_path.exists():
        print(f"Warning: {shed_path} does not exist yet. Creating config anyway.")
    elif not (shed_path / ".adzekit").exists():
        print(f"Warning: {shed_path} exists but has no .adzekit marker (not an initialized shed).")
        print("  Run `adzekit init` inside that directory to initialize it.")

    set_global_shed(shed_path)
    print(f"Shed configured: {shed_path}")
    print(f"Config saved:    {GLOBAL_CONFIG_PATH}")
    print()
    print("All AdzeKit tools will now use this shed automatically.")
    print("No need to set ADZEKIT_SHED in your environment.")


# -- use-workspace ---------------------------------------------------------


def cmd_use_workspace(args: argparse.Namespace) -> None:
    """Clone or update a git-backed workspace and register it as the active shed."""
    from adzekit.config import Settings, set_global_shed

    git_url: str = args.url

    repo_name = git_url.rstrip("/").split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    local_path = Path(args.path).expanduser() if args.path else Path.home() / repo_name

    if local_path.exists() and (local_path / ".git").is_dir():
        print(f"Updating existing workspace at {local_path} ...")
        subprocess.run(
            ["git", "-C", str(local_path), "pull", "--ff-only"],
            check=True,
        )
    else:
        print(f"Cloning {git_url} -> {local_path} ...")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", git_url, str(local_path)], check=True)

    set_global_shed(local_path)
    print(f"Shed set to: {local_path}")

    settings = Settings(shed=local_path)
    if settings.is_initialized:
        if not settings.git_repo:
            settings.set_config("git_repo", git_url)
            print(f"Recorded git_repo = {git_url}")
        rclone_remote = getattr(args, "rclone_remote", None)
        if rclone_remote and not settings.rclone_remote:
            settings.set_config("rclone_remote", rclone_remote)
            print(f"Recorded rclone_remote = {rclone_remote}")
    else:
        print(f"\nNote: {local_path} is not yet an AdzeKit shed.")
        print(f"  Run: adzekit --shed {local_path} init")

    print("\nDone. Run 'adzekit sync' to pull latest.")


# -- sync ------------------------------------------------------------------


def cmd_sync(args: argparse.Namespace) -> None:
    """Sync shed via git (backbone) and rclone (stock/ + drafts/), then refresh tags."""
    from adzekit.modules.tags import generate_cursor_snippets

    settings = _resolve_settings(args)
    direction = getattr(args, "direction", None)

    if direction in (None, "pull"):
        if settings.is_git_backed:
            print("Pulling backbone from git...")
            try:
                settings.sync_shed()
                print("  git pull done.")
            except subprocess.CalledProcessError as exc:
                print(f"  git pull failed: {exc.stderr.strip()}")
        if settings.has_rclone_remote:
            print("Pulling stock/ and drafts/ from rclone remote...")
            settings.sync_workbench()
            print("  rclone pull done.")
        if direction == "pull":
            generate_cursor_snippets(settings)
            print("Pull complete. Tag snippets refreshed.")
            return

    if direction in (None, "push"):
        if settings.has_rclone_remote:
            print("Pushing stock/ and drafts/ to rclone remote...")
            settings.push_workbench()
            print("  rclone push done.")
        if settings.is_git_backed:
            print("Committing and pushing backbone to git...")
            try:
                committed = settings.commit_shed()
                print("  Committed and pushed." if committed else "  Nothing to commit.")
            except subprocess.CalledProcessError as exc:
                print(f"  git push failed: {exc.stderr.strip()}")
        if direction == "push":
            generate_cursor_snippets(settings)
            print("Push complete. Tag snippets refreshed.")
            return

    generate_cursor_snippets(settings)
    print("Sync complete. Tag snippets refreshed.")


# -- setup-sync ------------------------------------------------------------


def cmd_setup_sync(args: argparse.Namespace) -> None:
    """Guide the user through setting up rclone for Google Drive sync."""
    settings = _resolve_settings(args)

    # Step 1: Check rclone is installed
    if shutil.which("rclone") is None:
        print("rclone is not installed.")
        print("  macOS:  brew install rclone")
        print("  Linux:  curl https://rclone.org/install.sh | sudo bash")
        print("\nInstall rclone, then re-run: adzekit setup-sync")
        raise SystemExit(1)

    print("rclone found.\n")

    # Step 2: Check if a remote named 'gdrive' already exists
    result = subprocess.run(
        ["rclone", "listremotes"],
        capture_output=True, text=True,
    )
    existing_remotes = [r.rstrip(":") for r in result.stdout.strip().splitlines()]

    remote_name = args.remote or "gdrive"

    if remote_name not in existing_remotes:
        print(f"No rclone remote named '{remote_name}' found.")
        print("\nRun the following to create one:\n")
        print(f"  rclone config create {remote_name} drive\n")
        print("This will open a browser for Google OAuth.")
        print(f"Once done, re-run: adzekit setup-sync --remote {remote_name}")
        raise SystemExit(1)

    print(f"rclone remote '{remote_name}' found.\n")

    # Step 3: Determine the remote folder path
    folder = args.folder or "adzekit"
    remote_path = f"{remote_name}:{folder}"

    print(f"Remote base path: {remote_path}")
    print(f"  stock/  -> {remote_path}/stock")
    print(f"  drafts/ -> {remote_path}/drafts\n")

    # Step 4: Save to .adzekit config
    settings.set_config("rclone_remote", remote_path)

    print(f"Saved rclone_remote = {remote_path} to {settings.marker_path}")
    print("\nSetup complete. Run 'adzekit sync' to sync stock/ and drafts/.")


# -- parser ----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adzekit",
        description="AdzeKit -- prehistoric tools, modern brains.",
    )
    parser.add_argument(
        "--shed",
        help="Path to the shed (overrides ADZEKIT_SHED).",
        default=None,
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # adze
    p_adze = sub.add_parser("adze", help="Print the AdzeKit symbol.")
    p_adze.set_defaults(func=cmd_adze)

    # init
    p_init = sub.add_parser("init", help="Initialize a new shed.")
    p_init.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Directory to initialize (default: current directory).",
    )
    p_init.set_defaults(func=cmd_init)

    # today
    p_today = sub.add_parser("today", help="Create/show today's daily note.")
    p_today.set_defaults(func=cmd_today)

    # daily-start
    p_ds = sub.add_parser(
        "daily-start",
        help="Bootstrap today's daily note from context.",
    )
    p_ds.add_argument(
        "--date", default=None,
        help="Target date (YYYY-MM-DD, default: today).",
    )
    p_ds.set_defaults(func=cmd_daily_start)

    # daily-close
    p_dc = sub.add_parser(
        "daily-close",
        help="Close today's note with reflection and sweep.",
    )
    p_dc.add_argument(
        "--date", default=None,
        help="Target date (YYYY-MM-DD, default: today).",
    )
    p_dc.set_defaults(func=cmd_daily_close)

    # review
    p_review = sub.add_parser("review", help="Create/show this week's review.")
    p_review.add_argument(
        "--date",
        default=None,
        help="Date within the target week (YYYY-MM-DD, default: today).",
    )
    p_review.set_defaults(func=cmd_review)

    # weekly-review
    p_weekly = sub.add_parser(
        "weekly-review",
        help="Cull the shed and write this week's pulse summary.",
    )
    p_weekly.add_argument(
        "--date",
        default=None,
        help="Date within the target week (YYYY-MM-DD, default: today).",
    )
    p_weekly.set_defaults(func=cmd_weekly_review)

    # sweep
    p_sweep = sub.add_parser("sweep", help="Move [x] loops from active.md to archive.md.")
    p_sweep.set_defaults(func=cmd_sweep)

    # cull
    p_cull = sub.add_parser("cull", help="Scan drafts/ and update bench with pending items.")
    p_cull.set_defaults(func=cmd_cull)

    # add-loop
    p_loop = sub.add_parser("add-loop", help="Add a loop to open.md.")
    p_loop.add_argument("title", help="Loop title.")
    p_loop.add_argument("--size", default=None, help="T-shirt size (XS, S, M, L, XL).")
    p_loop.add_argument("--who", default=None, help="Who is this commitment with?")
    p_loop.add_argument("--what", default=None, help="What is the commitment?")
    p_loop.add_argument("--due", default=None, help="Due date (YYYY-MM-DD).")
    p_loop.add_argument("--next", default=None, help="Next action.")
    p_loop.add_argument("--project", default=None, help="Project slug.")
    p_loop.set_defaults(func=cmd_add_loop)

    # project
    p_project = sub.add_parser("project", help="Create a new project file.")
    p_project.add_argument("slug", help="Project slug (e.g. acme-migration).")
    p_project.add_argument(
        "--title", default=None, help="Project title (default: slug).",
    )
    p_project.add_argument(
        "--active", action="store_true",
        help="Create in active/ instead of backlog/.",
    )
    p_project.set_defaults(func=cmd_project)

    # demote
    p_demote = sub.add_parser(
        "demote", help="Move an active project back to backlog/.",
    )
    p_demote.add_argument("slug", help="Project slug.")
    p_demote.set_defaults(func=cmd_demote)

    # promote
    p_promote = sub.add_parser(
        "promote",
        help="Move a backlog project to active/ (blocks at WIP cap).",
    )
    p_promote.add_argument("slug", help="Project slug.")
    p_promote.set_defaults(func=cmd_promote)

    # status
    p_status = sub.add_parser("status", help="Show shed health summary.")
    p_status.set_defaults(func=cmd_status)

    # export
    p_export = sub.add_parser("export", help="Export a markdown file to docx.")
    p_export.add_argument(
        "file",
        help="Path to the markdown file (relative to shed root, or absolute).",
    )
    p_export.add_argument(
        "-o", "--output",
        default=None,
        help="Output path, relative to shed or absolute (default: .docx extension).",
    )
    p_export.set_defaults(func=cmd_export)

    # sync
    # use-workspace
    p_use_ws = sub.add_parser(
        "use-workspace",
        help="Clone/update a git workspace and register it as the active shed.",
    )
    p_use_ws.add_argument("url", help="Git URL of the workspace repo.")
    p_use_ws.add_argument(
        "--path",
        default=None,
        help="Local path for the workspace (default: ~/<repo-name>).",
    )
    p_use_ws.add_argument(
        "--rclone-remote",
        default=None,
        dest="rclone_remote",
        help="rclone remote base path for stock/drafts (e.g. 'gdrive:adzekit').",
    )
    p_use_ws.set_defaults(func=cmd_use_workspace)

    p_sync = sub.add_parser(
        "sync",
        help="Sync shed via git (backbone) and rclone (stock/ + drafts/).",
    )
    p_sync.add_argument(
        "direction",
        nargs="?",
        choices=["pull", "push"],
        default=None,
        help="Sync direction (default: pull then push).",
    )
    p_sync.set_defaults(func=cmd_sync)

    # setup-sync
    p_setup = sub.add_parser("setup-sync", help="Configure rclone for Google Drive sync.")
    p_setup.add_argument(
        "--remote",
        default=None,
        help="rclone remote name (default: gdrive).",
    )
    p_setup.add_argument(
        "--folder",
        default=None,
        help="Folder path on the remote (default: adzekit).",
    )
    p_setup.set_defaults(func=cmd_setup_sync)

    # set-shed
    p_set_shed = sub.add_parser(
        "set-shed",
        help="Set the global shed path (persists across sessions and terminal resets).",
    )
    p_set_shed.add_argument(
        "path",
        help="Path to the AdzeKit shed (e.g. ~/Repos/adzekit-workspace).",
    )
    p_set_shed.set_defaults(func=cmd_set_shed)

    # graph
    p_graph = sub.add_parser("graph", help="Knowledge graph operations.")
    p_graph.set_defaults(func=cmd_graph, graph_command=None)
    graph_sub = p_graph.add_subparsers(dest="graph_command")

    p_graph_build = graph_sub.add_parser("build", help="Build knowledge graph from shed content.")
    p_graph_build.set_defaults(func=cmd_graph, graph_command="build")

    p_graph_query = graph_sub.add_parser("query", help="Query graph context for an entity.")
    p_graph_query.add_argument("entity", help="Entity name (slug, e.g. vector-search).")
    p_graph_query.add_argument(
        "--depth", type=int, default=2,
        help="Traversal depth (default: 2).",
    )
    p_graph_query.set_defaults(func=cmd_graph, graph_command="query")

    p_graph_stats = graph_sub.add_parser("stats", help="Show graph statistics.")
    p_graph_stats.set_defaults(func=cmd_graph, graph_command="stats")

    p_graph_orphans = graph_sub.add_parser("orphans", help="List entities with no connections.")
    p_graph_orphans.set_defaults(func=cmd_graph, graph_command="orphans")

    # tags
    p_tags = sub.add_parser("tags", help="List, search, or autocomplete tags.")
    p_tags.add_argument(
        "search",
        nargs="?",
        default=None,
        help="Tag to search for (e.g. vector-search).",
    )
    p_tags.add_argument(
        "--completions",
        action="store_true",
        help="Generate .vscode/adzekit.code-snippets for Cursor autocomplete.",
    )
    p_tags.set_defaults(func=cmd_tags)

    # drafts (subcommand group)
    p_drafts = sub.add_parser("drafts", help="Review and promote drafts from INBOX.")
    p_drafts.set_defaults(func=cmd_drafts, drafts_command=None)
    p_drafts_sub = p_drafts.add_subparsers(dest="drafts_subcommand")

    p_drafts_list = p_drafts_sub.add_parser("list", help="List pending drafts in INBOX.")
    p_drafts_list.set_defaults(func=cmd_drafts, drafts_command=_drafts_list)

    p_drafts_accept = p_drafts_sub.add_parser(
        "accept",
        help="Promote draft #N from INBOX to its backbone location.",
    )
    p_drafts_accept.add_argument("index", type=int, help="1-based INBOX entry index.")
    p_drafts_accept.add_argument(
        "--to",
        default=None,
        help="Override the destination directory (default: per-skill heuristic).",
    )
    p_drafts_accept.add_argument(
        "--no-preserve",
        action="store_true",
        help="Skip preserving the original draft in drafts/archive/originals/.",
    )
    p_drafts_accept.set_defaults(func=cmd_drafts, drafts_command=_drafts_accept)

    p_drafts_dismiss = p_drafts_sub.add_parser(
        "dismiss",
        help="Discard draft #N: move to drafts/archive/.",
    )
    p_drafts_dismiss.add_argument("index", type=int, help="1-based INBOX entry index.")
    p_drafts_dismiss.set_defaults(func=cmd_drafts, drafts_command=_drafts_dismiss)

    p_drafts_gc = p_drafts_sub.add_parser(
        "gc",
        help="Archive drafts older than N days and clean INBOX entries.",
    )
    p_drafts_gc.add_argument(
        "--days",
        type=int,
        default=None,
        help="Age threshold in days (default: stale_draft_days from .adzekit).",
    )
    p_drafts_gc.set_defaults(func=cmd_drafts, drafts_command=_drafts_gc)

    p_drafts_show = p_drafts_sub.add_parser(
        "show",
        help="Preview the body and provenance of draft #N before accepting.",
    )
    p_drafts_show.add_argument("index", type=int, help="1-based INBOX entry index.")
    p_drafts_show.add_argument(
        "--with-frontmatter",
        action="store_true",
        help="Include the `<!-- adzekit-draft -->` header in the output.",
    )
    p_drafts_show.set_defaults(func=cmd_drafts, drafts_command=_drafts_show)

    p_drafts_rollback = p_drafts_sub.add_parser(
        "rollback",
        help="Undo a recent `accept` by restoring the original from drafts/archive/originals/.",
    )
    p_drafts_rollback.add_argument(
        "--filename",
        default=None,
        help="Specific archived original to restore (default: most recently accepted).",
    )
    p_drafts_rollback.set_defaults(func=cmd_drafts, drafts_command=_drafts_rollback)

    # prune-drafts
    p_pd = sub.add_parser("prune-drafts", help="Delete stale draft files.")
    p_pd.add_argument(
        "--days", type=int, default=None,
        help="Delete files older than N days (default: from config or 7).",
    )
    p_pd.set_defaults(func=cmd_prune_drafts)

    # adapter (subcommand: adapter <name> <action>)
    p_adapter = sub.add_parser(
        "adapter",
        help="Install/uninstall/status for runtime and integration adapters.",
    )
    p_adapter.add_argument(
        "name",
        choices=["claude-code", "gmail", "google-calendar"],
        help="Which adapter to operate on.",
    )
    p_adapter.add_argument(
        "action",
        choices=["install", "uninstall", "status"],
        help="install: copy files into the runtime; uninstall: remove; status: report.",
    )
    p_adapter.set_defaults(func=cmd_adapter)

    # gateway
    p_gateway = sub.add_parser(
        "gateway",
        help="Run the gateway daemon (Telegram → Claude Code bridge).",
    )
    p_gateway_sub = p_gateway.add_subparsers(dest="gateway_command", required=True)
    p_gateway_start = p_gateway_sub.add_parser(
        "start",
        help="Start the gateway. Reads ADZEKIT_TELEGRAM_BOT_TOKEN + ADZEKIT_TELEGRAM_ALLOWED_USER_IDS.",
    )
    p_gateway_start.add_argument(
        "--transport",
        default="telegram",
        choices=["telegram"],
        help="Which gateway transport to run (default: telegram).",
    )
    p_gateway_start.set_defaults(func=cmd_gateway)

    # mcp
    p_mcp = sub.add_parser(
        "mcp",
        help="Wire AdzeKit MCP servers (shed, gmail, calendar) into ~/.claude/settings.json.",
    )
    p_mcp.add_argument(
        "action",
        choices=["install", "uninstall", "status"],
        help="install: register in settings.json; uninstall: remove; status: report.",
    )
    p_mcp.add_argument(
        "--only",
        default=None,
        help=(
            "Comma-separated subset of servers to operate on "
            "(shed, gmail, calendar). Without this, all available are processed."
        ),
    )
    p_mcp.set_defaults(func=cmd_mcp)

    # calendar
    p_calendar = sub.add_parser(
        "calendar",
        help="Google Calendar utilities (today briefing).",
    )
    p_calendar_sub = p_calendar.add_subparsers(dest="calendar_command", required=True)
    p_calendar_today = p_calendar_sub.add_parser(
        "today",
        help="Print today's calendar briefing to terminal.",
    )
    p_calendar_today.add_argument(
        "--calendar",
        default="primary",
        help="Calendar ID (default: primary).",
    )
    p_calendar_today.set_defaults(func=cmd_calendar)

    # insight
    p_insight = sub.add_parser(
        "insight",
        help="Synthesize accumulated shed data into a reviewable insight draft.",
    )
    p_insight.add_argument(
        "--period",
        choices=["weekly", "monthly", "quarterly"],
        default="weekly",
        help="Time window to extract over (default: weekly).",
    )
    p_insight.add_argument(
        "--date",
        default=None,
        help="ISO date (YYYY-MM-DD) inside the target window. Defaults to today.",
    )
    p_insight.set_defaults(func=cmd_insight)

    # distill
    p_distill = sub.add_parser(
        "distill",
        help="Scan accepted drafts for repeated edit patterns; emit skill proposals.",
    )
    p_distill.add_argument(
        "--min-occurrences", type=int, default=3,
        help="Minimum pattern occurrences to propose a skill (default: 3).",
    )
    p_distill.add_argument(
        "--window-days", type=int, default=60,
        help="Rolling window in days to search (default: 60).",
    )
    p_distill.set_defaults(func=cmd_distill)

    # automate / cadence (cadence is the preferred name; automate kept for
    # backward compat)
    for cmd_name, help_text in (
        ("cadence", "Manage the launchd cadence layer (daily/weekly rituals)."),
        ("automate", "Alias for `cadence` (deprecated)."),
    ):
        p_cad = sub.add_parser(cmd_name, help=help_text)
        p_cad.add_argument(
            "action", choices=["install", "uninstall", "status"],
            help="install plists, uninstall, or show current cadence status.",
        )
        p_cad.set_defaults(func=cmd_automate)

    return parser


def main(argv: list[str] | None = None) -> None:
    from adzekit.config import ShedNotInitializedError

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except ShedNotInitializedError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
