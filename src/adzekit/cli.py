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


# -- review ----------------------------------------------------------------


def cmd_review(args: argparse.Namespace) -> None:
    """Create (if needed) and print the path to this week's review."""
    from adzekit.workspace import create_review

    settings = _resolve_settings(args)
    review_date = date.fromisoformat(args.date) if args.date else None
    path = create_review(target_date=review_date, settings=settings)
    print(path)


# -- sweep -----------------------------------------------------------------


def _log_sweep_to_daily(count: int, settings: "Settings") -> None:
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
    """Move all [x] loops from open.md to closed.md."""
    from adzekit.modules.loops import sweep_closed

    settings = _resolve_settings(args)
    swept = sweep_closed(settings)
    if not swept:
        print("Nothing to sweep -- no closed loops in open.md.")
    else:
        _log_sweep_to_daily(len(swept), settings)
        for loop in swept:
            print(f"  swept: {loop.title}")
        print(f"\n{len(swept)} loop(s) moved to closed.md")


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
            print(f"  {f.relative_to(settings.workspace)}")
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
    # Resolve relative paths against the vault root
    source = raw if raw.is_absolute() else (settings.workspace / raw)
    source = source.expanduser().resolve()

    output = None
    if args.output:
        raw_out = Path(args.output)
        output = raw_out if raw_out.is_absolute() else (settings.workspace / raw_out)
        output = output.expanduser().resolve()

    docx_path = to_docx(source, output)
    print(f"Exported: {docx_path}")


# -- status ----------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> None:
    """Print a summary of vault health."""
    from adzekit.modules.git_age import project_ages
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

    ages = project_ages(settings)
    if ages:
        print("\nProject ages:")
        for a in ages:
            name = a.path.stem
            stale = f"{a.stale_days}d ago" if a.stale_days is not None else "untracked"
            created = f"{a.age_days}d old" if a.age_days is not None else ""
            print(f"  {name}: modified {stale}" + (f", {created}" if created else ""))


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

    # adze
    p_adze = sub.add_parser("adze", help="Print the AdzeKit symbol.")
    p_adze.set_defaults(func=cmd_adze)

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

    # review
    p_review = sub.add_parser("review", help="Create/show this week's review.")
    p_review.add_argument(
        "--date",
        default=None,
        help="Date within the target week (YYYY-MM-DD, default: today).",
    )
    p_review.set_defaults(func=cmd_review)

    # sweep
    p_sweep = sub.add_parser("sweep", help="Move [x] loops from open.md to closed.md.")
    p_sweep.set_defaults(func=cmd_sweep)

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
    p_project.add_argument("slug", help="Project slug (e.g. strathcona-reservoir).")
    p_project.add_argument(
        "--title", default=None, help="Project title (default: slug).",
    )
    p_project.add_argument(
        "--active", action="store_true",
        help="Create in active/ instead of backlog/.",
    )
    p_project.set_defaults(func=cmd_project)

    # status
    p_status = sub.add_parser("status", help="Show vault health summary.")
    p_status.set_defaults(func=cmd_status)

    # poc-init
    p_poc = sub.add_parser("poc-init", help="Generate a POC design document in stock/.")
    p_poc.add_argument("slug", help="Project slug (e.g. citco-columnmapping).")
    p_poc.add_argument(
        "--docx",
        action="store_true",
        help="Also export the generated template to .docx via pandoc.",
    )
    p_poc.set_defaults(func=cmd_poc_init)

    # export
    p_export = sub.add_parser("export", help="Export a markdown file to docx.")
    p_export.add_argument("file", help="Path to the markdown file (relative to vault root, or absolute).")
    p_export.add_argument(
        "-o", "--output",
        default=None,
        help="Output path, relative to vault root or absolute (default: same directory, .docx extension).",
    )
    p_export.set_defaults(func=cmd_export)

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
