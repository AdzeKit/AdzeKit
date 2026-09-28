"""``adzekit`` command line. Deterministic helpers; no network, no AI."""

from __future__ import annotations

import argparse
import sys
from datetime import date

from adzekit import daily, loops, projects, review
from adzekit.sync import sync
from adzekit.workspace import Workspace, WorkspaceError


def _date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {text!r}") from exc


def cmd_init(args: argparse.Namespace) -> None:
    ws, created = Workspace.init(args.path or args.workspace or ".")
    print(f"Workspace: {ws.root}")
    for name in created:
        print(f"  created {name}")
    if not created:
        print("  already initialized; nothing changed")
    claude = ws.root / "CLAUDE.md"
    if "@AGENTS.md" not in claude.read_text(encoding="utf-8"):
        print("  note: CLAUDE.md does not import AGENTS.md; add `@AGENTS.md` so Claude "
              "reads the shared instructions")


def cmd_today(args: argparse.Namespace) -> None:
    ws = Workspace.find(args.workspace)
    result = daily.today(ws, args.date)
    if result.created:
        print(f"Created {result.path.relative_to(ws.root)}"
              + (f", carried {len(result.carried)} intention(s)" if result.carried else ""))
        if result.left_behind:
            print(f"Left {len(result.left_behind)} behind (daily cap); choose deliberately:")
            for task in result.left_behind:
                print(f"  - {task}")
        print()
    print(result.path.read_text(encoding="utf-8"), end="")


def cmd_log(args: argparse.Namespace) -> None:
    ws = Workspace.find(args.workspace)
    path = daily.log(ws, " ".join(args.text), args.date)
    print(f"Logged to {path.relative_to(ws.root)}")


def _describe(loop: loops.Loop, today: date) -> str:
    notes = []
    if loop.overdue(today):
        notes.append(f"OVERDUE {loop.due}")
    elif loop.due:
        notes.append(f"due {loop.due}")
    age = loop.age(today)
    if age is not None:
        notes.append(f"{age}d")
    return f"{loop.title}" + (f"  [{', '.join(notes)}]" if notes else "")


def cmd_loop(args: argparse.Namespace) -> None:
    ws = Workspace.find(args.workspace)
    today = date.today()
    action = args.action or "list"
    if action == "add":
        print(loops.add(ws, " ".join(args.text), today=today, size=args.size or "", due=args.due))
    elif action == "close":
        print(f"Closed: {loops.close(ws, ' '.join(args.text)).title}")
    elif action == "sweep":
        swept = loops.sweep(ws, today=today)
        print(f"Swept {len(swept)} closed loop(s) to loops/archive.md")
    else:
        open_ = loops.open_loops(ws)
        for n, loop in enumerate(open_, 1):
            print(f"{n:>3}. {_describe(loop, today)}")
        if not open_:
            print("No open loops.")


def cmd_project(args: argparse.Namespace) -> None:
    ws = Workspace.find(args.workspace)
    today = date.today()
    action = args.action or "list"
    if action == "new":
        state = "backlog" if args.backlog else "active"
        path = projects.new(ws, args.slug, today=today, title=args.title or "", state=state,
                            force=args.force)
        print(f"Created {path.relative_to(ws.root)}")
    elif action == "move":
        path = projects.move(ws, args.slug, args.state, force=args.force)
        print(f"Moved to {path.relative_to(ws.root)}")
    else:
        for state in ("active", "backlog"):
            items = projects.load(ws, state, today)
            print(f"{state} ({len(items)})")
            for p in items:
                print(f"  {p.slug:<28} {p.last_touched or '-'}  {p.title}")


def cmd_status(args: argparse.Namespace) -> None:
    ws = Workspace.find(args.workspace)
    today = date.today()
    print(f"Workspace: {ws.root}")

    note = ws.daily_path(today)
    if note.is_file():
        open_, done = daily.intentions(note.read_text(encoding="utf-8"))
        print(f"Today:     {len(done)}/{len(open_) + len(done)} intentions done")
    else:
        print("Today:     no note yet (adzekit today)")

    open_loops = loops.open_loops(ws)
    overdue = [lp for lp in open_loops if lp.overdue(today)]
    stale = [lp for lp in open_loops if (lp.age(today) or 0) > ws.setting("stale_loop_days")]
    print(f"Loops:     {len(open_loops)} open, {len(overdue)} overdue, {len(stale)} stale")

    active = projects.load(ws, "active", today)
    cap = ws.setting("max_active_projects")
    quiet_days = ws.setting("stale_project_days")
    quiet = [p for p in active if not p.last_touched or (today - p.last_touched).days > quiet_days]
    flag = "  OVER CAP" if len(active) > cap else ""
    print(f"Projects:  {len(active)}/{cap} active{flag}, {len(quiet)} quiet >{quiet_days}d")

    for loop in overdue:
        print(f"  overdue: {loop.title}")


def cmd_review(args: argparse.Namespace) -> None:
    ws = Workspace.find(args.workspace)
    path, created = review.write(ws, args.date)
    print(f"{'Created' if created else 'Exists'}: {path.relative_to(ws.root)}")


def cmd_sync(args: argparse.Namespace) -> None:
    ws = Workspace.find(args.workspace)
    for step in sync(ws, args.message):
        print(step)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adzekit", description="Markdown habits for people and their agents."
    )
    parser.add_argument("-w", "--workspace", "--shed", help="workspace folder")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create or repair a workspace")
    p.add_argument("path", nargs="?")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("today", help="create/show today's note")
    p.add_argument("--date", type=_date, default=date.today())
    p.set_defaults(func=cmd_today)

    p = sub.add_parser("log", help="append a line to today's Log")
    p.add_argument("text", nargs="+")
    p.add_argument("--date", type=_date, default=date.today())
    p.set_defaults(func=cmd_log)

    p = sub.add_parser("loop", help="list, add, close, or sweep loops")
    p.add_argument("action", nargs="?", choices=["list", "add", "close", "sweep"])
    p.add_argument("text", nargs="*")
    p.add_argument("--size", choices=["XS", "S", "M", "L", "XL"])
    p.add_argument("--due", type=_date)
    p.set_defaults(func=cmd_loop)

    p = sub.add_parser("project", help="list, create, or move projects")
    p.add_argument("action", nargs="?", choices=["list", "new", "move"])
    p.add_argument("slug", nargs="?")
    p.add_argument("state", nargs="?", choices=projects.STATES)
    p.add_argument("--title")
    p.add_argument("--backlog", action="store_true", help="create in backlog")
    p.add_argument("--force", action="store_true", help="exceed the active cap")
    p.set_defaults(func=cmd_project)

    p = sub.add_parser("status", help="one-screen health check")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("review", help="write this week's review scaffold")
    p.add_argument("--date", type=_date, default=date.today())
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("sync", help="git commit, pull --rebase, push")
    p.add_argument("-m", "--message")
    p.set_defaults(func=cmd_sync)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "loop" and args.action in {"add", "close"} and not args.text:
        parser.error(f"loop {args.action} needs text")
    if args.command == "project" and args.action in {"new", "move"} and not args.slug:
        parser.error(f"project {args.action} needs a slug")
    if args.command == "project" and args.action == "move" and not args.state:
        parser.error("project move needs a state: active, backlog, or archive")
    try:
        args.func(args)
    except WorkspaceError as exc:
        print(f"adzekit: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
