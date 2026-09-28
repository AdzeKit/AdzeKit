# Agent contract

AdzeKit does not require a particular model, prompt format, or agent runtime.
An integration only needs to implement this small contract:

1. Open one explicit workspace path.
2. Read Markdown or the JSON-safe workspace snapshot.
3. Put generated work in `drafts/` as a proposal.
4. Let a person accept or dismiss the proposal.

That is the whole agent boundary. Reading, reasoning, parallelism, and tool
selection belong to the host runtime. AdzeKit owns storage and review.

## Preferred interfaces

- **Python:** `from adzekit import Workspace`
- **Any MCP client:** run `adzekit-mcp` (the old `adzekit-mcp-shed` name remains)
- **Any process:** use the `adzekit` CLI
- **Web application:** construct `Workspace(path)` in a request dependency and
  return its dictionaries directly as JSON

Do not give an agent direct write access to `daily/`, `loops/`, `projects/`,
`knowledge/`, or `reviews/`. Give it the `propose` operation instead. A runtime
may use sub-agents, but AdzeKit neither requires nor orchestrates them.

## Minimal prompt

```text
You are working with an AdzeKit workspace.
Read the supplied workspace snapshot and source Markdown.
Never change human-owned files directly.
Put proposed changes in the proposal inbox with a short summary.
State what you used and what remains uncertain.
```

## Web example

AdzeKit deliberately does not bundle a web framework. The same object works in
FastAPI, Flask, Django, Starlette, serverless functions, or a background job.

```python
from fastapi import FastAPI
from adzekit import Workspace

app = FastAPI()
workspace = Workspace("/data/my-workspace")

@app.get("/api/workspace")
def get_workspace():
    return workspace.snapshot()

@app.post("/api/proposals")
def create_proposal(body: dict):
    return workspace.propose(
        workflow=body["workflow"],
        markdown=body["markdown"],
        summary=body.get("summary", ""),
        source="web",
    )
```

For multi-tenant applications, construct one `Workspace` per authorized root;
never accept an arbitrary filesystem path directly from a request.
