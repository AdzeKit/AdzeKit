"""AdzeKit CLI -- command-line interface for operating on any backbone-conforming shed.

Usage:
    adzekit init [path]          Initialize a new shed at path (default: cwd)
    adzekit today                Open or create today's daily note
    adzekit add-loop             Add a loop to open.md
    adzekit status               Show shed health summary
    adzekit sync [pull|push]     Sync stock/ and drafts/ via rclone
    adzekit setup-sync           Configure rclone for Google Drive sync
    adzekit serve                Start the local web UI
    adzekit agent <message>      Run the agent with a one-shot message
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
    """Bootstrap today's daily note from yesterday's context and active loops."""
    from adzekit.modules.daily import daily_start

    settings = _resolve_settings(args)
    target = date.fromisoformat(args.date) if args.date else None
    path, summary = daily_start(target_date=target, settings=settings)

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
    """Append reflection line to today's note and sweep closed loops."""
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


# -- automate --------------------------------------------------------------


def cmd_automate(args: argparse.Namespace) -> None:
    """Install or uninstall launchd automation."""
    from adzekit.modules.automate import install, uninstall

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


# -- review ----------------------------------------------------------------


def cmd_review(args: argparse.Namespace) -> None:
    """Create (if needed) and print the path to this week's review."""
    from adzekit.workspace import create_review

    settings = _resolve_settings(args)
    review_date = date.fromisoformat(args.date) if args.date else None
    path = create_review(target_date=review_date, settings=settings)
    print(path)


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
    """Scan drafts/ and update bench.md with pending items."""
    from adzekit.modules.bench import cull

    settings = _resolve_settings(args)
    added, cleared = cull(settings)

    if not added and not cleared:
        print("Bench is up to date -- no new drafts, nothing to clear.")
    else:
        if cleared:
            print(f"  cleared {cleared} processed item(s)")
        if added:
            print(f"  added {added} new draft(s) to bench")
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
    from adzekit.workspace import create_project

    settings = _resolve_settings(args)
    path = create_project(
        slug=args.slug,
        title=args.title or "",
        backlog=not args.active,
        settings=settings,
    )
    print(path)


# -- poc-init --------------------------------------------------------------


def cmd_poc_init(args: argparse.Namespace) -> None:
    """Generate a POC design document template in stock/."""
    import sys

    from adzekit.modules.export import to_docx
    from adzekit.modules.poc import generate_poc

    settings = _resolve_settings(args)
    try:
        path = generate_poc(args.slug, settings)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)

    print(f"Generated POC template: {path}")

    if args.docx:
        docx_path = to_docx(path)
        print(f"Exported to docx: {docx_path}")


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


# -- serve -----------------------------------------------------------------


def cmd_serve(args: argparse.Namespace) -> None:
    """Start the local web UI."""
    import uvicorn

    print(f"Starting AdzeKit UI at http://{args.host}:{args.port}")
    uvicorn.run(
        "adzekit.ui.app:app",
        host=args.host,
        port=args.port,
        reload=False,
    )


# -- agent -----------------------------------------------------------------


def cmd_agent(args: argparse.Namespace) -> None:
    """Run the agent with a one-shot message.

    DEPRECATED: Use Claude Code instead.
    """
    import warnings

    warnings.warn(
        "`adzekit agent` is deprecated and will be removed in a future release.\n"
        "Use Claude Code with AdzeKit instead.",
        DeprecationWarning,
        stacklevel=1,
    )
    print(
        "Deprecated: `adzekit agent` is superseded by Claude Code.\n"
    )
    import adzekit.agent.shed_tools  # noqa: F401
    from adzekit.agent.orchestrator import run_agent

    print(f"Agent processing: {args.message}\n")
    try:
        result = run_agent(args.message)
        print(result.response)
        if result.tool_calls_made > 0:
            print(f"\n({result.tool_calls_made} tool calls made across {len(result.turns)} turns)")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)


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


# -- sync ------------------------------------------------------------------


def cmd_sync(args: argparse.Namespace) -> None:
    """Sync stock/ and drafts/ with the rclone remote."""
    settings = _resolve_settings(args)

    direction = getattr(args, "direction", None)

    if direction in (None, "pull"):
        print("Pulling stock/ and drafts/ from remote...")
        settings.sync_workbench()
        if direction == "pull":
            print("Pull complete.")
            return

    if direction in (None, "push"):
        print("Pushing stock/ and drafts/ to remote...")
        settings.push_workbench()
        if direction == "push":
            print("Push complete.")
            return

    print("Sync complete (pull + push).")


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

    # status
    p_status = sub.add_parser("status", help="Show shed health summary.")
    p_status.set_defaults(func=cmd_status)

    # poc-init
    p_poc = sub.add_parser("poc-init", help="Generate a POC design document in stock/.")
    p_poc.add_argument("slug", help="Project slug (e.g. acme-datamigration).")
    p_poc.add_argument(
        "--docx",
        action="store_true",
        help="Also export the generated template to .docx via pandoc.",
    )
    p_poc.set_defaults(func=cmd_poc_init)

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
    p_sync = sub.add_parser("sync", help="Sync stock/ and drafts/ via rclone.")
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

    # serve
    p_serve = sub.add_parser("serve", help="Start the local web UI.")
    p_serve.add_argument(
        "--port", type=int, default=8742,
        help="Port to serve on (default: 8742).",
    )
    p_serve.add_argument(
        "--host", default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1).",
    )
    p_serve.set_defaults(func=cmd_serve)

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

    # agent
    p_agent = sub.add_parser("agent", help="Run the agent with a one-shot message.")
    p_agent.add_argument("message", help="Message to send to the agent.")
    p_agent.set_defaults(func=cmd_agent)

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

    # prune-drafts
    p_pd = sub.add_parser("prune-drafts", help="Delete stale draft files.")
    p_pd.add_argument(
        "--days", type=int, default=None,
        help="Delete files older than N days (default: from config or 7).",
    )
    p_pd.set_defaults(func=cmd_prune_drafts)

    # automate
    p_auto = sub.add_parser(
        "automate", help="Install/uninstall launchd automation.",
    )
    p_auto.add_argument(
        "action", choices=["install", "uninstall"],
        help="install or uninstall launchd plists.",
    )
    p_auto.set_defaults(func=cmd_automate)

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
