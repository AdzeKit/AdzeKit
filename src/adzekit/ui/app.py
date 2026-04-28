"""AdzeKit local web UI.

A FastAPI application that serves a dashboard for shed status,
open loops, projects, and an agent chat interface. Also provides
a file editor for direct manipulation of backbone markdown files.

Run with: adzekit serve
"""

import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from adzekit.config import Settings, get_settings

TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="AdzeKit", docs_url="/api/docs")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _settings() -> Settings:
    return get_settings()


# -- Pages ------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Dashboard page."""
    return templates.TemplateResponse(request, "index.html", {"active_page": "dashboard"})


@app.get("/agent", response_class=HTMLResponse)
async def agent_page(request: Request):
    """Agent chat page."""
    return templates.TemplateResponse(request, "agent.html", {"active_page": "agent"})


@app.get("/guide", response_class=HTMLResponse)
async def guide_page(request: Request):
    """Philosophy and backbone guide."""
    return templates.TemplateResponse(request, "guide.html", {"active_page": "guide"})


@app.get("/graph", response_class=HTMLResponse)
async def graph_page(request: Request):
    """Knowledge graph browser."""
    return templates.TemplateResponse(request, "graph.html", {"active_page": "graph"})


# -- API endpoints -----------------------------------------------------------


@app.get("/api/status")
async def api_status():
    """Shed status summary."""
    from adzekit.modules.loops import loop_stats
    from adzekit.modules.wip import wip_status

    settings = _settings()
    wip = wip_status(settings)
    loops = loop_stats(settings)
    return {
        "shed": str(settings.shed),
        "active_projects": wip["active_projects"],
        "max_active_projects": wip["max_active_projects"],
        "daily_tasks": wip["daily_tasks"],
        "max_daily_tasks": wip["max_daily_tasks"],
        "open_loops": loops["active"],
        "overdue_loops": loops["overdue"],
        "approaching_sla": loops["approaching_sla"],
    }


@app.get("/api/loops")
async def api_loops():
    """Active loops."""
    from adzekit.preprocessor import load_active_loops

    settings = _settings()
    loops = load_active_loops(settings)
    return [
        {
            "title": loop.title,
            "date": loop.date.isoformat(),
            "size": loop.size,
            "due": loop.due.isoformat() if loop.due else None,
            "status": loop.status,
            "who": loop.who,
        }
        for loop in loops
    ]


@app.get("/api/projects")
async def api_projects():
    """All projects."""
    from adzekit.preprocessor import load_projects

    settings = _settings()
    projects = load_projects(settings=settings)
    return [
        {
            "slug": p.slug,
            "title": p.title,
            "state": p.state.value,
            "progress": round(p.progress, 2),
            "total_tasks": len(p.tasks),
            "done_tasks": sum(1 for t in p.tasks if t.done),
        }
        for p in projects
    ]


@app.get("/api/today")
async def api_today():
    """Today's daily note."""
    from adzekit.preprocessor import load_daily_note

    settings = _settings()
    note = load_daily_note(settings=settings)
    if note is None:
        return {"exists": False}
    return {
        "exists": True,
        "date": note.date.isoformat(),
        "intentions": [{"desc": t.description, "done": t.done} for t in note.intentions],
        "log_entries": [{"time": e.time, "text": e.text} for e in note.log],
        "raw_content": note.raw_content,
    }


@app.get("/api/bench")
async def api_bench():
    """Shed bench contents (triage queue)."""
    settings = _settings()
    if not settings.bench_path.exists():
        return {"content": ""}
    content = settings.bench_path.read_text(encoding="utf-8")
    return {"content": content}


@app.get("/api/agent/status")
async def api_agent_status():
    """Check availability of Isaac."""
    from adzekit.agent.isaac_client import check_isaac

    return {"isaac": check_isaac()}


# -- Graph API --------------------------------------------------------------


@app.get("/api/graph/stats")
async def api_graph_stats():
    """Stats from the built graph, plus the orphans list and top-connected nodes."""
    from adzekit.modules.graph import graph_stats, load_graph

    settings = _settings()
    graph = load_graph(settings)
    if graph is None:
        return {"built": False}

    stats = graph_stats(graph)

    degree: dict[str, int] = {}
    for rel in graph.relationships:
        degree[rel.source] = degree.get(rel.source, 0) + 1
        degree[rel.target] = degree.get(rel.target, 0) + 1
    top = sorted(degree.items(), key=lambda x: -x[1])[:10]

    connected = (
        {r.source for r in graph.relationships}
        | {r.target for r in graph.relationships}
    )
    orphans = sorted(n for n in graph.entities if n not in connected)

    entities_by_type: dict[str, list[dict]] = {}
    for e in graph.entities.values():
        entities_by_type.setdefault(e.entity_type.value, []).append({
            "name": e.name,
            "sources": e.sources[:3],
        })
    for v in entities_by_type.values():
        v.sort(key=lambda x: x["name"])

    built_at = graph.built_at.isoformat() if graph.built_at else None
    return {
        "built": True,
        "built_at": built_at,
        "stats": stats,
        "top_connected": [{"name": n, "degree": d} for n, d in top],
        "orphans": orphans,
        "entities_by_type": entities_by_type,
    }


@app.get("/api/graph/entities")
async def api_graph_entities():
    """Flat list of entity names (for editor wikilink autocomplete)."""
    from adzekit.modules.graph import load_graph

    graph = load_graph(_settings())
    if graph is None:
        return []
    return sorted(graph.entities.keys())


@app.get("/api/graph/entity/{name}")
async def api_graph_entity(name: str, depth: int = 2):
    """Compressed graph context for a single entity."""
    from adzekit.modules.graph import get_context, load_graph

    graph = load_graph(_settings())
    if graph is None:
        raise HTTPException(status_code=404, detail="Graph not built. Run: adzekit graph build")
    return {
        "name": name,
        "depth": depth,
        "context": get_context(name, graph, depth=depth),
    }


@app.get("/api/graph/network")
async def api_graph_network():
    """Cytoscape-shaped graph: {nodes: [...], edges: [...]} for the visualizer.

    Each node carries entity_type, degree, and source files. Each edge carries
    its relation_type so the client can colour and filter."""
    from adzekit.modules.graph import load_graph

    graph = load_graph(_settings())
    if graph is None:
        return {"built": False, "nodes": [], "edges": []}

    degree: dict[str, int] = {}
    for rel in graph.relationships:
        degree[rel.source] = degree.get(rel.source, 0) + 1
        degree[rel.target] = degree.get(rel.target, 0) + 1

    nodes = []
    for entity in graph.entities.values():
        nodes.append({
            "data": {
                "id": entity.name,
                "label": entity.name,
                "entity_type": entity.entity_type.value,
                "degree": degree.get(entity.name, 0),
                "sources": entity.sources[:5],
            }
        })

    edges = []
    seen: set[tuple[str, str, str]] = set()
    for i, rel in enumerate(graph.relationships):
        key = (rel.source, rel.target, rel.relation_type.value)
        if key in seen:
            continue
        seen.add(key)
        # Drop self-loops — they're noise on the canvas.
        if rel.source == rel.target:
            continue
        # Skip edges referencing entities that aren't in the registry.
        if rel.source not in graph.entities or rel.target not in graph.entities:
            continue
        edges.append({
            "data": {
                "id": f"e{i}",
                "source": rel.source,
                "target": rel.target,
                "relation": rel.relation_type.value,
            }
        })

    return {
        "built": True,
        "built_at": graph.built_at.isoformat() if graph.built_at else None,
        "nodes": nodes,
        "edges": edges,
    }


@app.get("/api/graph/duplicates")
async def api_graph_duplicates(threshold: float = 0.85):
    """Deterministic duplicate clusters across the graph. No LLM."""
    from adzekit.modules.graph import load_graph
    from adzekit.modules.graph_dedup import find_duplicates

    graph = load_graph(_settings())
    if graph is None:
        return {"built": False, "groups": []}

    groups = find_duplicates(graph, threshold=threshold)
    return {
        "built": True,
        "threshold": threshold,
        "groups": [
            {
                "entity_type": g.entity_type,
                "members": [
                    {"name": m.name, "degree": m.degree, "sources": m.sources}
                    for m in g.members
                ],
                "similarity": round(g.similarity, 3),
                "suggested_canonical": g.suggested_canonical,
            }
            for g in groups
        ],
    }


@app.post("/api/graph/duplicates/merge")
async def api_graph_dedup_merge(request: Request):
    """Apply find-and-replace merges across the backbone.

    Body: {merges: [{from, to}, ...], dry_run: bool}
    Returns per-file replacement counts. Rebuilds the graph after a real
    (non-dry-run) merge so the UI immediately reflects the consolidated state.
    """
    from adzekit.modules.graph import build_graph, save_graph
    from adzekit.modules.graph_dedup import apply_merges

    body = await request.json()
    raw = body.get("merges", []) or []
    merges = [
        (m.get("from", "").strip(), m.get("to", "").strip())
        for m in raw
        if m.get("from") and m.get("to")
    ]
    if not merges:
        raise HTTPException(status_code=400, detail="No merges specified")

    settings = _settings()
    dry_run = bool(body.get("dry_run", False))

    result = await asyncio.to_thread(apply_merges, merges, settings, dry_run)

    if not dry_run and result["total_replacements"] > 0:
        try:
            graph = await asyncio.to_thread(build_graph, settings)
            await asyncio.to_thread(save_graph, graph, settings)
        except Exception:
            pass

    return result


@app.post("/api/graph/build")
async def api_graph_build():
    """Synchronously rebuild the graph from current backbone."""
    from adzekit.modules.graph import build_graph, graph_stats, save_graph

    settings = _settings()
    graph = await asyncio.to_thread(build_graph, settings)
    await asyncio.to_thread(save_graph, graph, settings)
    return {"status": "built", "stats": graph_stats(graph)}


# -- Triage API -------------------------------------------------------------


@app.get("/api/triage")
async def api_triage():
    """Items requiring decisions: overdue loops, stale active projects, stale bench items."""
    from datetime import date

    from adzekit.modules.bench import stale_bench_items
    from adzekit.modules.wip import stale_active_projects
    from adzekit.preprocessor import load_active_loops

    settings = _settings()
    today = date.today()

    loops = load_active_loops(settings)
    overdue = [
        {
            "title": loop.title,
            "due": loop.due.isoformat() if loop.due else None,
            "days_overdue": (today - loop.due).days if loop.due else None,
            "size": loop.size,
            "who": loop.who,
        }
        for loop in loops
        if loop.due and loop.due < today and loop.status.lower() != "closed"
    ]

    stale = [
        {"slug": p.slug, "title": p.title, "days_inactive": days}
        for p, days in stale_active_projects(settings)
    ]

    bench_stale = stale_bench_items(settings)

    return {
        "overdue_loops": overdue,
        "stale_projects": stale,
        "stale_bench_items": bench_stale,
    }


# -- Demote / promote API ---------------------------------------------------


@app.post("/api/files/projects/{slug}/demote")
async def api_demote_project(slug: str):
    """Move an active project back to backlog."""
    from adzekit.modules.wip import demote_project

    settings = _settings()
    try:
        path = demote_project(slug, settings=settings)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"status": "demoted", "path": str(path.relative_to(settings.projects_dir))}


@app.post("/api/files/projects/{slug}/promote")
async def api_promote_project(slug: str):
    """Move a backlog project to active. Hard-blocked at WIP cap."""
    from adzekit.modules.wip import activate_project

    settings = _settings()
    try:
        path = activate_project(slug, settings=settings)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"status": "promoted", "path": str(path.relative_to(settings.projects_dir))}


def _sessions_dir() -> Path:
    return _settings().drafts_dir / "sessions"


def _load_session(session_id: str) -> dict:
    path = _sessions_dir() / f"{session_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _save_session(data: dict) -> None:
    d = _sessions_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{data['id']}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


@app.get("/api/sessions")
async def api_list_sessions():
    """List all chat sessions, newest first."""
    d = _sessions_dir()
    if not d.exists():
        return []
    sessions = []
    for f in sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            msgs = data.get("messages", [])
            first_user = next((m["content"] for m in msgs if m["role"] == "user"), "")
            sessions.append({
                "id": data["id"],
                "created": data.get("created", ""),
                "updated": data.get("updated", ""),
                "message_count": len(msgs),
                "preview": first_user[:80],
            })
        except Exception:
            continue
    return sessions


@app.post("/api/sessions")
async def api_create_session():
    """Create a new empty session."""
    ts = datetime.now(timezone.utc)
    session_id = ts.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)
    data = {
        "id": session_id,
        "created": ts.isoformat(),
        "updated": ts.isoformat(),
        "messages": [],
    }
    _save_session(data)
    return {"id": session_id}


@app.get("/api/sessions/{session_id}")
async def api_get_session(session_id: str):
    """Get a session with all its messages."""
    return _load_session(session_id)


@app.put("/api/sessions/{session_id}")
async def api_save_session(session_id: str, request: Request):
    """Replace a session's message list."""
    body = await request.json()
    data = _load_session(session_id)
    data["messages"] = body.get("messages", [])
    data["updated"] = datetime.now(timezone.utc).isoformat()
    _save_session(data)
    return {"status": "saved"}


@app.delete("/api/sessions/{session_id}")
async def api_delete_session(session_id: str):
    path = _sessions_dir() / f"{session_id}.json"
    if path.exists():
        path.unlink()
    return {"status": "deleted"}


@app.get("/api/tags")
async def api_tags():
    """Return all unique #tags found across backbone markdown files."""
    import re

    settings = _settings()
    tag_pattern = re.compile(r"#([a-zA-Z][a-zA-Z0-9_-]*)")
    tags: set[str] = set()

    dirs_to_scan = [
        settings.daily_dir,
        settings.loops_dir,
        settings.projects_dir,
        settings.knowledge_dir,
        settings.reviews_dir,
    ]
    for d in dirs_to_scan:
        if not d.exists():
            continue
        for f in d.rglob("*.md"):
            try:
                for match in tag_pattern.finditer(f.read_text(encoding="utf-8", errors="ignore")):
                    tags.add(match.group(1))
            except OSError:
                continue

    return sorted(tags)


@app.post("/api/agent/chat")
async def api_agent_chat(request: Request):
    """Send a message to the agent via Isaac and get a response."""
    body = await request.json()
    user_message = body.get("message", "")
    if not user_message:
        return JSONResponse({"error": "No message provided"}, status_code=400)
    history = body.get("history", [])  # [{role, content}, ...] last N turns

    from adzekit.agent.isaac_client import AgentNotAvailableError
    from adzekit.agent.isaac_client import run_agent as _run_agent

    settings = _settings()

    prompt = user_message
    if history:
        ctx_lines = ["[Previous conversation -- continue naturally]\n"]
        for m in history[-10:]:
            role = "User" if m["role"] == "user" else "Assistant"
            ctx_lines.append(f"{role}: {m['content']}")
        ctx_lines.append(f"\n[New message]\nUser: {user_message}")
        prompt = "\n".join(ctx_lines)

    try:
        response, used_backend = await _run_agent(
            prompt, timeout=settings.agent_timeout
        )
        return {"response": response, "tool_calls_made": 0, "backend": used_backend}
    except AgentNotAvailableError as exc:
        return JSONResponse({"error": f"Isaac unavailable: {exc}"}, status_code=503)
    except Exception as exc:
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"}, status_code=500)


# -- Backbone editor pages ---------------------------------------------------

EDITOR_SECTIONS = {
    "daily": "Daily Notes",
    "loops": "Loops",
    "projects": "Projects",
    "knowledge": "Knowledge",
    "reviews": "Reviews",
    "bench": "Bench",
}


@app.get("/daily", response_class=HTMLResponse)
async def daily_page(request: Request):
    return templates.TemplateResponse(
        request,
        "editor.html",
        {"active_page": "daily", "section": "daily", "section_title": "Daily Notes"},
    )


@app.get("/loops", response_class=HTMLResponse)
async def loops_page(request: Request):
    return templates.TemplateResponse(
        request,
        "editor.html",
        {"active_page": "loops", "section": "loops", "section_title": "Loops"},
    )


@app.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request):
    return templates.TemplateResponse(
        request,
        "editor.html",
        {"active_page": "projects", "section": "projects", "section_title": "Projects"},
    )


@app.get("/knowledge", response_class=HTMLResponse)
async def knowledge_page(request: Request):
    return templates.TemplateResponse(
        request,
        "editor.html",
        {"active_page": "knowledge", "section": "knowledge", "section_title": "Knowledge"},
    )


@app.get("/reviews", response_class=HTMLResponse)
async def reviews_page(request: Request):
    return templates.TemplateResponse(
        request,
        "editor.html",
        {"active_page": "reviews", "section": "reviews", "section_title": "Reviews"},
    )


@app.get("/bench", response_class=HTMLResponse)
async def bench_page(request: Request):
    return templates.TemplateResponse(
        request,
        "editor.html",
        {"active_page": "bench", "section": "bench", "section_title": "Bench"},
    )


# -- File API: list, read, write --------------------------------------------


def _validate_section(section: str) -> None:
    if section not in EDITOR_SECTIONS:
        raise HTTPException(status_code=404, detail=f"Unknown section: {section}")


def _resolve_file(section: str, name: str, settings: Settings) -> Path:
    """Resolve a relative filename to an absolute path within the section,
    with validation to prevent path traversal."""
    base = {
        "daily": settings.daily_dir,
        "loops": settings.loops_dir,
        "projects": settings.projects_dir,
        "knowledge": settings.knowledge_dir,
        "reviews": settings.reviews_dir,
        "bench": settings.shed,
    }[section]

    if section == "bench":
        if name != "bench.md":
            raise HTTPException(status_code=400, detail="Invalid bench path")
        return settings.bench_path

    base_resolved = base.resolve()
    resolved = (base / name).resolve()
    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        raise HTTPException(status_code=403, detail="Path traversal not allowed")
    if not resolved.suffix == ".md":
        raise HTTPException(status_code=400, detail="Only .md files are supported")
    return resolved


@app.get("/api/files/{section}")
async def api_list_files(section: str):
    """List files available for editing in a backbone section."""
    _validate_section(section)
    settings = _settings()

    if section == "daily":
        files = sorted(settings.daily_dir.glob("*.md"), reverse=True)
        return [
            {"path": f.name, "label": f.stem, "group": None}
            for f in files
        ]

    if section == "loops":
        result = []
        if settings.loops_active.exists():
            result.append({"path": "active.md", "label": "Active Loops", "group": "Active"})
        if settings.loops_backlog.exists():
            result.append({"path": "backlog.md", "label": "Backlog Loops", "group": "Backlog"})
        archive_flat = settings.loops_dir / "archive.md"
        if archive_flat.exists():
            result.append({"path": "archive.md", "label": "Archive (all)", "group": "Archive"})
        archive_dir = settings.loops_archive_dir
        if archive_dir.exists():
            for f in sorted(archive_dir.glob("*.md"), reverse=True):
                result.append({
                    "path": f"archive/{f.name}",
                    "label": f.stem,
                    "group": "Archive",
                })
        return result

    if section == "projects":
        result = []
        for state, label in [
            (settings.active_dir, "Active"),
            (settings.backlog_dir, "Backlog"),
            (settings.archive_dir, "Archive"),
        ]:
            if not state.exists():
                continue
            for f in sorted(state.glob("*.md")):
                rel = f.relative_to(settings.projects_dir)
                result.append({
                    "path": str(rel),
                    "label": f.stem,
                    "group": label,
                })
        return result

    if section == "knowledge":
        files = sorted(settings.knowledge_dir.glob("*.md"))
        return [
            {"path": f.name, "label": f.stem, "group": None}
            for f in files
        ]

    if section == "reviews":
        files = sorted(settings.reviews_dir.glob("*.md"), reverse=True)
        return [
            {"path": f.name, "label": f.stem, "group": None}
            for f in files
        ]

    if section == "bench":
        if settings.bench_path.exists():
            return [{"path": "bench.md", "label": "Bench", "group": None}]
        return []

    return []


@app.get("/api/files/{section}/{name:path}")
async def api_read_file(section: str, name: str):
    """Read the content of a backbone file."""
    _validate_section(section)
    settings = _settings()
    path = _resolve_file(section, name, settings)

    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {name}")

    content = path.read_text(encoding="utf-8")
    return {"content": content, "path": name}


@app.put("/api/files/{section}/{name:path}")
async def api_write_file(section: str, name: str, request: Request):
    """Save content to a backbone file. Triggers an async graph rebuild."""
    _validate_section(section)
    settings = _settings()
    path = _resolve_file(section, name, settings)

    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {name}")

    body = await request.json()
    content = body.get("content")
    if content is None:
        raise HTTPException(status_code=400, detail="Missing 'content' field")

    path.write_text(content, encoding="utf-8")

    if section in ("daily", "loops", "projects", "knowledge"):
        _schedule_graph_rebuild(settings)

    return {"status": "saved", "path": name}


# -- Graph rebuild (debounced background task) ------------------------------

import asyncio  # noqa: E402

_graph_rebuild_task: asyncio.Task | None = None
_graph_rebuild_lock = asyncio.Lock()
_GRAPH_DEBOUNCE_SECONDS = 2.0


def _schedule_graph_rebuild(settings: Settings) -> None:
    """Debounced background graph rebuild. Multiple saves within the debounce
    window collapse into a single rebuild. Failures are silent — graph build
    must never break a save."""
    global _graph_rebuild_task
    if _graph_rebuild_task and not _graph_rebuild_task.done():
        _graph_rebuild_task.cancel()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    _graph_rebuild_task = loop.create_task(_debounced_graph_rebuild(settings))


async def _debounced_graph_rebuild(settings: Settings) -> None:
    try:
        await asyncio.sleep(_GRAPH_DEBOUNCE_SECONDS)
    except asyncio.CancelledError:
        return
    async with _graph_rebuild_lock:
        try:
            from adzekit.modules.graph import build_graph, save_graph
            graph = await asyncio.to_thread(build_graph, settings)
            await asyncio.to_thread(save_graph, graph, settings)
        except Exception:
            pass


# -- File API: create -------------------------------------------------------


@app.post("/api/files/daily/create-today")
async def api_create_today():
    """Create today's daily note (or return existing)."""
    from adzekit.workspace import create_daily_note

    settings = _settings()
    settings.require_initialized()
    path = create_daily_note(settings=settings)
    return {"name": path.name, "status": "created"}


@app.post("/api/files/reviews/create-this-week")
async def api_create_this_week():
    """Create this week's review (or return existing)."""
    from adzekit.workspace import create_review

    settings = _settings()
    settings.require_initialized()
    path = create_review(settings=settings)
    return {"name": path.name, "status": "created"}


@app.post("/api/files/knowledge/create")
async def api_create_knowledge(request: Request):
    """Create a new knowledge file."""
    settings = _settings()
    settings.require_initialized()

    body = await request.json()
    slug = body.get("slug", "").strip()
    if not slug:
        raise HTTPException(status_code=400, detail="Slug is required")
    if not re.match(r"^[a-z0-9][a-z0-9\-]*$", slug):
        raise HTTPException(
            status_code=400,
            detail="Slug must be lowercase alphanumeric with hyphens (e.g. my-topic)",
        )

    path = settings.knowledge_dir / f"{slug}.md"
    if path.exists():
        raise HTTPException(status_code=409, detail=f"Knowledge file already exists: {slug}.md")

    settings.knowledge_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {slug.replace('-', ' ').title()}\n\n", encoding="utf-8")
    return {"name": path.name, "status": "created"}


@app.post("/api/files/projects/create")
async def api_create_project(request: Request):
    """Create a new project file."""
    from adzekit.workspace import create_project

    settings = _settings()
    settings.require_initialized()

    body = await request.json()
    slug = body.get("slug", "").strip()
    title = body.get("title", "").strip() or slug
    state = body.get("state", "backlog")

    if not slug:
        raise HTTPException(status_code=400, detail="Slug is required")
    if not re.match(r"^[a-z0-9][a-z0-9\-]*$", slug):
        raise HTTPException(
            status_code=400,
            detail="Slug must be lowercase alphanumeric with hyphens (e.g. my-project)",
        )
    if state not in ("active", "backlog"):
        raise HTTPException(status_code=400, detail="State must be 'active' or 'backlog'")

    if state == "active":
        from adzekit.modules.wip import can_activate
        allowed, reason = can_activate(settings)
        if not allowed:
            raise HTTPException(status_code=409, detail=reason)

    path = create_project(
        slug=slug,
        title=title,
        backlog=(state == "backlog"),
        settings=settings,
    )
    rel = path.relative_to(settings.projects_dir)
    return {"name": str(rel), "status": "created"}


def create_app() -> FastAPI:
    """Factory for the FastAPI app (used by uvicorn)."""
    return app
