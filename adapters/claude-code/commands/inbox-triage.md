---
description: Classify, archive, and draft replies for inbox emails (Gmail by default)
argument-hint: Optional batch size override (default: 200 per pass)
---

Execute the AdzeKit `inbox-triage` skill (canonical:
`src/adzekit/skills/inbox-triage.md`).

This is a fan-out skill. Use the `email-triage-worker` plugin agent (in
this plugin's `agents/` directory) to classify message chunks in parallel.
Recommended sharding: 25 emails per worker, concurrency cap 5.

Orchestration:
1. Authenticate Gmail (`gcloud auth application-default print-access-token`).
2. Fetch all metadata in one Bash pass (no LLM in the loop).
3. Build the context block from `knowledge/soul.md`, optional workspace
   `knowledge/contacts.md` or `knowledge/role-context.md`, open loops.
4. Spawn workers in parallel via the `Agent` tool with
   `subagent_type: "email-triage-worker"`. Each worker gets its chunk +
   the context block.
5. Collect JSON results, apply Gmail side-effects in one batch
   (`batchModify`, `drafts.create`).
6. Write a single review report via `adzekit drafts accept` — actually,
   the orchestrator writes the report draft and surfaces it in INBOX.

Workers have `Bash, Read` only. They do NOT have Write or Edit tools and
they do NOT call any Gmail mutation endpoint. Files-first invariant is
preserved by tool absence; see `docs/delegation-pattern.md`.

ARGUMENTS: $ARGUMENTS
