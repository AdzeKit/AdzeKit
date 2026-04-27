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
    """Save content to a backbone file."""
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
    return {"status": "saved", "path": name}


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
