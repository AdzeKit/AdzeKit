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

| Field        | Value        |
|--------------|--------------|
| Last Updated | {date_created} |
| Status       | Not Started  |

**TL;DR**
Problem:
Solution:
Goal:

## Goals & Non-Goals

| | Description |
|---|---|
| **Goal 1** | |
| **Goal 2** | |
| **Goal 3** | |
| **Non-Goal 1** | |
| **Non-Goal 2** | |

## Problem

{context}

### Why Now

-
-
-

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| | | |
| | | |
| This approach | | |

## Solution Overview

### Component Map

| Component | Technology | Role |
|-----------|------------|------|
| | | |
| | | |
| | | |

## Requirements

| ID | Requirement | Priority | Scope |
|----|-------------|----------|-------|
| R-1 | | Must | PoC |
| R-2 | | Must | PoC |
| R-3 | | Should | PoC |
| R-4 | | Could | Post-PoC |

## Data & Prerequisites

### Source Data

| ID | Name / System | Format | Est. Rows | Owner | Access |
|----|---------------|--------|-----------|-------|--------|
| DS-1 | | | | | |
| DS-2 | | | | | |

### Prerequisites Checklist

- [ ] Access credentials for all data sources
- [ ] Target schema or output format defined
- [ ] API keys configured and rate limits reviewed
- [ ] Development environment validated
- [ ] Sample data available
- [ ] Storage path for artifacts defined

## Design Notes

## Implementation Plan

### Milestones

| Phase | Description | Start | End | Status |
|-------|-------------|-------|-----|--------|
| 0 | Setup & infra | | | Not Started |
| 1 | Core pipeline | | | Not Started |
| 2 | Integration & testing | | | Not Started |
| 3 | Evaluation & readout | | | Not Started |

### Tasks

{tasks}

## Key Performance Indicators

| ID | Metric | Target | Result |
|----|--------|--------|--------|
| KPI-1 | | | TBD |
| KPI-2 | | | TBD |
| KPI-3 | | | TBD |

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| | | | |
| | | | |
| Scope creep | High | Medium | Enforce non-goals; weekly scope check |

## Stakeholders

| Name | Role | Contact |
|------|------|---------|
| | Sponsor | |
| | Engineer | |
| | Domain SME | |

## Results

> *Populate after PoC execution.*

| Metric | Result | Notes |
|--------|--------|-------|
| KPI-1 | | |
| KPI-2 | | |

**Key observations:**
- What worked:
- What didn't:
- Open questions for next phase:

## Open Questions

| # | Question | Owner | Due | Answer |
|---|----------|-------|-----|--------|
| 1 | | | | |

## Appendix

### Glossary

| Term | Definition |
|------|------------|
| | |

### Resources

| Resource | Link |
|----------|------|
| | |
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
            title = " ".join(
                w for w in raw_title.split() if not w.startswith("#")
            ).strip() or raw_title
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

    if project_path:
        fields = _extract_project_fields(project_path)
    else:
        fields = {
            "title": slug,
            "context": "",
            "tasks": [],
        }

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
