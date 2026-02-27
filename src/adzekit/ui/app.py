"""AdzeKit local web UI.

A FastAPI application that serves a dashboard for shed status,
open loops, projects, and an agent chat interface.

Run with: adzekit serve
"""

from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request
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
    return templates.TemplateResponse(request, "index.html")


@app.get("/agent", response_class=HTMLResponse)
async def agent_page(request: Request):
    """Agent chat page."""
    return templates.TemplateResponse(request, "agent.html")


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
        "open_loops": loops["open"],
        "overdue_loops": loops["overdue"],
        "approaching_sla": loops["approaching_sla"],
    }


@app.get("/api/loops")
async def api_loops():
    """Open loops."""
    from adzekit.preprocessor import load_open_loops

    settings = _settings()
    loops = load_open_loops(settings)
    return [
        {
            "title": l.title,
            "date": l.date.isoformat(),
            "size": l.size,
            "due": l.due.isoformat() if l.due else None,
            "status": l.status,
            "who": l.who,
        }
        for l in loops
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


@app.get("/api/inbox")
async def api_inbox():
    """Shed inbox contents."""
    settings = _settings()
    if not settings.inbox_path.exists():
        return {"content": ""}
    content = settings.inbox_path.read_text(encoding="utf-8")
    return {"content": content}


@app.post("/api/agent/chat")
async def api_agent_chat(request: Request):
    """Send a message to the agent and get a response."""
    body = await request.json()
    user_message = body.get("message", "")
    if not user_message:
        return JSONResponse({"error": "No message provided"}, status_code=400)

    # Import agent tools to register them
    import adzekit.agent.gmail_tools  # noqa: F401
    import adzekit.agent.shed_tools  # noqa: F401
    from adzekit.agent.orchestrator import run_agent

    try:
        result = run_agent(user_message)
        return {
            "response": result.response,
            "tool_calls_made": result.tool_calls_made,
            "turns": len(result.turns),
        }
    except Exception as exc:
        return JSONResponse(
            {"error": f"{type(exc).__name__}: {exc}"},
            status_code=500,
        )


def create_app() -> FastAPI:
    """Factory for the FastAPI app (used by uvicorn)."""
    return app
