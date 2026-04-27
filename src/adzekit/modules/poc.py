"""POC design document generator.

Generates a proof-of-concept design document template in the stock/
directory. If a matching project markdown file exists, the title and
context are pre-filled. Everything else is left blank for the human
or LLM to complete.
"""

from datetime import date
from pathlib import Path

from adzekit.config import Settings, get_settings

POC_TEMPLATE = """\
# [POC] {title}

*Created {date_created} · Status: Not Started*

## TL;DR

**Problem:**
**Solution:**
**Goal:**

## Problem & Why Now

{context}

## What We'll Build

Describe the approach -- what are we building, how does it work,
and why this design over alternatives?

### Databricks Features Used

- **Feature** -- Role in the POC.

## Success Criteria

We evaluate the POC against these. If we hit them, the POC succeeded.

| # | What we're proving | How we'll measure it |
|---|-------------------|---------------------|
| 1 |                   |                     |
| 2 |                   |                     |
| 3 |                   |                     |

## Commitments

This works if both sides commit. Here's what each side owns.

**Databricks will:**
- Build the core solution in 2-3 working sessions
- Provide architecture guidance and best practices
- Deliver documentation so the customer team can operate independently

**Customer will:**
- Provide a named champion with dedicated time for the POC period
- Load data into Databricks (or provide access) before Phase 1
- Make SMEs available for 1-2 evaluation sessions
- Commit to a production decision within 2 weeks of readout

| Who | Role | Commitment |
|-----|------|-----------|
|     |      |           |
|     |      |           |

## Plan

| Phase | What happens | Target |
|-------|-------------|--------|
| 0 -- Align | Review data, confirm scope, validate access | Week 1 |
| 1 -- Build | Core pipeline end-to-end | Weeks 2-3 |
| 2 -- Refine | SME evaluation, iterate to success criteria | Week 4 |
| 3 -- Readout | Present results, discuss production path | Week 5 |

### Tasks

{tasks}

## Results

> *Populate after POC execution.*

- What worked:
- What didn't:
- Path to production:
"""


def _find_project(slug: str, settings: Settings) -> Path | None:
    """Search for a project markdown file by slug across all project dirs."""
    candidates = [
        settings.active_dir / f"{slug}.md",
        settings.backlog_dir / f"{slug}.md",
        settings.archive_dir / f"{slug}.md",
        settings.projects_dir / f"{slug}.md",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _extract_project_fields(project_path: Path) -> dict[str, str]:
    """Pull title and context from a project markdown file."""
    text = project_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    title = project_path.stem
    context = ""
    tasks: list[str] = []

    section = ""
    context_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("# ") and not stripped.startswith("## "):
            raw_title = stripped.lstrip("# ").strip()
            title = (
                " ".join(w for w in raw_title.split() if not w.startswith("#")).strip()
                or raw_title
            )
            continue

        lower = stripped.lower()
        if lower == "## context":
            section = "context"
            continue
        elif lower == "## log":
            section = "log"
            continue
        elif lower == "## notes":
            section = "notes"
            continue
        elif stripped.startswith("## "):
            section = ""
            continue

        if section == "context" and stripped:
            context_lines.append(stripped)
        elif section == "log" and stripped:
            tasks.append(stripped)

    if context_lines:
        context = "\n".join(context_lines)

    return {
        "title": title,
        "context": context,
        "tasks": tasks,
    }


def generate_poc(
    slug: str,
    settings: Settings | None = None,
) -> Path:
    """Generate a POC design document in stock/<slug>/.

    If a project file exists for the slug, pre-fills title, context,
    and tasks from it. Otherwise generates a blank template.
    """
    settings = settings or get_settings()

    project_path = _find_project(slug, settings)

    if not project_path:
        raise FileNotFoundError(
            f"No project file found for '{slug}'. "
            f"Create one first with: adzekit project {slug}"
        )

    fields = _extract_project_fields(project_path)

    task_lines = fields["tasks"]
    if task_lines:
        tasks_str = "\n".join(task_lines)
    else:
        tasks_str = "- [ ]\n- [ ]\n- [ ]"

    content = POC_TEMPLATE.format(
        title=fields["title"],
        date_created=date.today().isoformat(),
        context=fields["context"],
        tasks=tasks_str,
    )

    stock_dir = settings.stock_dir / slug
    stock_dir.mkdir(parents=True, exist_ok=True)
    doc_path = stock_dir / "poc-design.md"
    doc_path.write_text(content, encoding="utf-8")
    return doc_path
