# AdzeKit

AdzeKit is a portable Markdown workspace for people and agents.

Your context stays in ordinary files. Software reads those files and puts
suggested changes in a proposal inbox. You decide what becomes permanent.

```text
files -> workflow -> proposal -> human decision
```

That is the product. It does not require an LLM, a particular agent, a web
framework, or a database.

## Start

```bash
git clone https://github.com/AdzeKit/AdzeKit.git
cd AdzeKit
uv pip install -e .

adzekit init ~/my-workspace
adzekit --workspace ~/my-workspace status
```

Initialization creates an empty workspace. It does not invent example projects,
notes, reviews, or graph data.

For compatibility, `--shed` and `ADZEKIT_SHED` still work. New integrations
should use `--workspace`, `ADZEKIT_WORKSPACE`, or an explicit Python path.

## Python API

```python
from adzekit import Workspace

workspace = Workspace("/data/my-workspace")

# JSON-safe: return this directly from a web route or tool handler.
state = workspace.snapshot()

# Generated work always enters the review queue.
proposal = workspace.propose(
    workflow="weekly-review",
    markdown="# Proposed review\n",
    summary="Weekly review ready",
    source="my-agent",
)
```

`Workspace` uses the path you give it. It does not consult global configuration,
which makes it suitable for FastAPI, Flask, Django, serverless functions, MCP
servers, background jobs, and tests. See [the agent contract](docs/agent-contract.md).

## Workspace format

The required format is intentionally small:

```text
my-workspace/
├── .adzekit       format marker
└── drafts/        generated proposals waiting for review
```

Bundled workflows also understand optional folders for daily notes, loops,
projects, knowledge, reviews, and a derived graph. They are conventions, not the
definition of AdzeKit. See [the workspace format](backbone-spec/schema.md).

## CLI essentials

```bash
adzekit today                       # create/show today's note
adzekit add-loop "Send estimate"    # record a commitment
adzekit project new-client          # create a project in backlog
adzekit status                      # summarize the workspace

adzekit drafts list                 # list proposals
adzekit drafts show 1               # inspect proposal and provenance
adzekit drafts accept 1             # promote it to human-owned files
adzekit drafts dismiss 2            # archive it
adzekit drafts rollback             # undo the latest acceptance
```

The CLI contains additional workflow and integration commands. They are kept for
existing users but are not part of the minimal product model.

## Agents

Any agent can use AdzeKit if it can:

1. open an explicit workspace;
2. read Markdown or `Workspace.snapshot()`;
3. submit generated work through `Workspace.propose()`;
4. leave acceptance or dismissal to the person.

MCP support is optional:

```bash
uv pip install -e ".[mcp]"
adzekit-mcp
```

The Claude Code adapter remains available under `adapters/claude-code/`, but it
is one integration rather than AdzeKit's runtime.

## Extensions

Install only what an application needs:

```bash
uv pip install -e ".[mcp]"       # MCP transport
uv pip install -e ".[export]"    # DOCX export
uv pip install -e ".[telegram]"  # Telegram gateway
uv pip install -e ".[sdk]"       # legacy Claude SDK runner
uv pip install -e ".[dev,all]"   # contributor environment
```

Gmail, Calendar, Telegram, document export, launchd cadence, graph building, and
runtime adapters are extensions. The core remains useful without them.

## Design

AdzeKit follows three principles:

1. Keep the source ordinary.
2. Separate proposals from decisions.
3. Keep the core smaller than its integrations.

Read the short [philosophy](docs/philosophy.md) and the detailed
[simplification review](docs/simplification-review.md).

## Development

```bash
uv pip install -e ".[dev,all]"
pytest -q
ruff check src tests
```

The storage format remains at version 2, so existing workspaces need no
migration. Legacy vocabulary such as “shed,” “backbone,” and “workbench” remains
in compatibility APIs while new public interfaces use “workspace,” “files,” and
“proposals.”
