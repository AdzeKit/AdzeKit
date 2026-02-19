"""AdzeKit CLI -- command-line interface for operating on any backbone-conforming vault.

Usage:
    adzekit init [path]          Initialize a new vault at path (default: cwd)
    adzekit today                Open or create today's daily note
    adzekit add-loop             Add a loop to open.md
    adzekit status               Show vault health summary
"""

import argparse
import sys
from datetime import date
from pathlib import Path


def _resolve_settings(args: argparse.Namespace):
    """Build a Settings instance from CLI args."""
    from adzekit.config import Settings

    kwargs: dict = {}
    vault = getattr(args, "vault", None)
    if vault:
        kwargs["workspace"] = Path(vault).expanduser().resolve()
    return Settings(**kwargs)


# -- init ------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> None:
    """Initialize a new AdzeKit vault with the full backbone structure."""
    from adzekit.config import Settings
    from adzekit.workspace import init_workspace

    path = Path(args.path).expanduser().resolve() if args.path else Path.cwd()
    settings = Settings(workspace=path)
    root = init_workspace(settings)

    # Print the tree that was created
    print(f"Initialized AdzeKit vault at {root}\n")
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
        who=args.who,
        what=args.what,
        due=due,
        status="Open",
        next_action=args.next or "",
        project=args.project or "",
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
            print(f"  {f.relative_to(settings.workspace)}")
        return

    tags = all_tags(settings)
    if not tags:
        print("No tags found.")
        return
    for tag in tags:
        print(f"  #{tag}")
    print(f"\n{len(tags)} tags")


# -- status ----------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> None:
    """Print a summary of vault health."""
    from adzekit.modules.loops import loop_stats
    from adzekit.modules.wip import wip_status

    settings = _resolve_settings(args)
    wip = wip_status(settings)
    loops = loop_stats(settings)

    print(f"Vault: {settings.workspace}")
    print(f"Active projects: {wip['active_projects']}/{wip['max_active_projects']}")
    print(f"Daily tasks: {wip['daily_tasks']}/{wip['max_daily_tasks']}")
    print(f"Open loops: {loops['open']}")
    print(f"Overdue loops: {loops['overdue']}")
    print(f"Approaching SLA: {loops['approaching_sla']}")


# -- parser ----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adzekit",
        description="AdzeKit -- prehistoric tools, modern brains.",
    )
    parser.add_argument(
        "--vault",
        help="Path to the vault (overrides ADZEKIT_WORKSPACE).",
        default=None,
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Initialize a new vault.")
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

    # add-loop
    p_loop = sub.add_parser("add-loop", help="Add a loop to open.md.")
    p_loop.add_argument("title", help="Loop title.")
    p_loop.add_argument("--who", required=True, help="Who is this commitment with?")
    p_loop.add_argument("--what", required=True, help="What is the commitment?")
    p_loop.add_argument("--due", default=None, help="Due date (YYYY-MM-DD).")
    p_loop.add_argument("--next", default=None, help="Next action.")
    p_loop.add_argument("--project", default=None, help="Project slug.")
    p_loop.set_defaults(func=cmd_add_loop)

    # status
    p_status = sub.add_parser("status", help="Show vault health summary.")
    p_status.set_defaults(func=cmd_status)

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

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
