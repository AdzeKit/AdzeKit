# Delegation Pattern — Adapter Contract

The shared contract that every AdzeKit adapter implements for skills that benefit from
sub-agent fan-out (`inbox-triage`, `slack-capture`, `loop-momentum`, `graph-update`'s
orphan-enrichment step). The point is: skills express the *structure* of the work; each
adapter expresses *how to execute* it.

## The shape

```
                    ┌───────────────────┐
                    │   Orchestrator    │  (the skill itself, single LLM context)
                    │  - loads context  │
                    │  - shards work    │
                    │  - fans out       │
                    │  - merges results │
                    │  - writes drafts  │
                    └────────┬──────────┘
                             │ structured input per worker
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ Worker 1 │  │ Worker 2 │  │ Worker N │  (each isolated, no shed write tools)
        │ chunk 1  │  │ chunk 2  │  │ chunk N  │
        │ returns  │  │ returns  │  │ returns  │
        │   JSON   │  │   JSON   │  │   JSON   │
        └──────────┘  └──────────┘  └──────────┘
```

## Invariants

1. **Files-first is enforced by tool absence.** Workers do not have file-writing tools.
   Not "should not" — *do not have*. Whatever tool surface the adapter exposes for
   workers, it never includes the host runtime's `Write` / `Edit` / `Save` tool.

2. **Workers return JSON.** Not free text. Not partial writes. Structured records that
   the orchestrator can merge deterministically.

3. **Orchestrator owns all side effects.** Every mutation to the shed, every API call
   that changes external state (Gmail batch-modify, Slack message-mark-read, draft
   creation), every file write — happens in the orchestrator after all workers return.
   This is the single chokepoint that preserves the "AI proposes to drafts/" invariant.

4. **Selective context inheritance.** Workers receive only the slice they need. A
   triage worker handling 25 emails does not receive the open loops, the project files,
   the daily notes, or the other 175 emails. The orchestrator extracts the smallest
   correct slice and passes it.

5. **Concurrency cap.** Default `max_concurrent_children = 5`. Adapters may lower for
   cost reasons; should not raise without measurement. The cap exists because (a)
   model providers throttle, (b) most fan-out wins come from the first 5 workers, (c)
   debugging 20 parallel children is awful.

6. **Worker depth = 1.** Workers do not spawn sub-workers. If a problem decomposes into
   nested fan-out, that's a sign the skill needs restructuring — not a sign to allow
   deeper recursion.

## Per-adapter mapping

### Claude Code adapter

- **Orchestrator**: the skill markdown is executed as a slash command in the main
  conversation. Claude Code's main agent IS the orchestrator.
- **Worker spawn**: the orchestrator emits multiple `Agent` tool calls in a single
  message. Multiple Agent calls in one message run in parallel.
- **Worker type**: a plugin agent defined under `adapters/claude-code/agents/` with
  frontmatter declaring `Bash, Read` (and any read-only MCPs the worker needs). No
  `Write`, no `Edit`.
- **JSON return**: the worker's final text output is the JSON payload. Orchestrator
  parses it.
- **Concurrency**: Claude Code does not currently expose a hard concurrency knob.
  Orchestrator achieves the cap by batching Agent calls (max 5 per message, then
  another batch).
- **Streaming/progress**: orchestrator prints a one-line announcement before each
  batch (`spawning 5 email-triage workers (200 emails, 40 per worker)`) and a one-line
  summary after.

### Future adapters

Any runtime that supports (a) isolated sub-agent execution with (b) selectable tool
sets and (c) a way to return structured output qualifies for the orchestrator+worker
pattern documented here. Runtimes that lack one of these can still implement the
skill spec as a monolithic single-context fallback — the skill works, it's just slower.

## The worker contract

Every worker, regardless of adapter, follows this shape:

**Input** (passed by orchestrator in the spawn call):
- A small bundled context (specific to the skill — e.g., classification rules, the
  customer table, the entity registry slice)
- A work slice (the specific chunk this worker handles)
- A structured-output schema declaration

**Tools available**: `Bash` and `Read` only by default. Plus any read-only MCPs the
specific worker needs (Slack MCP for slack-capture-worker, etc.). Never `Write`,
`Edit`, `NotebookEdit`, or any mutation tool.

**Output**: A JSON array (or object) matching the declared schema. Pretty-printed
or compact — the orchestrator parses with a permissive parser.

**Failure mode**: If a worker can't complete its slice, it returns a JSON object with
`{"error": "...", "partial": [...]}` rather than throwing. The orchestrator decides
whether to retry, skip, or surface to the human.

## Anti-patterns to refuse

- **Worker writes a draft** → no, only orchestrator writes drafts
- **Worker calls Gmail batchModify** → no, only orchestrator does state-changing API calls
- **Worker spawns a sub-worker** → no, depth = 1
- **Worker receives full backbone** → no, only its slice
- **Orchestrator returns from workers serially via `await`** → no, parallel spawn
- **Concurrency = 20 because "more is faster"** → no, default 5; raise only with evidence

## Verification (per adapter)

When implementing a new adapter, verify:

1. **Tool absence**: grep the worker definition for `Write` / `Edit` / equivalent.
   Should return zero matches.
2. **Failure containment**: simulate a worker crash mid-batch; orchestrator must
   complete remaining workers and surface the failure in the final draft.
3. **Selective context**: log the bytes passed to each worker. The triage-worker
   prompt should be ~5–10x smaller than the orchestrator's full context.
4. **Parallel execution**: measure wall-clock for a 5-worker batch. Should be ~max
   of individual worker times, not their sum.
5. **JSON parse robustness**: feed the orchestrator a worker output with trailing
   commentary text after the JSON. Should still parse.
