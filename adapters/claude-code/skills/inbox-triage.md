# Inbox Triage

## Goal

Process the user's email inbox in batches: classify each message into a small fixed taxonomy,
take the safe per-category actions (archive obvious noise, star or label messages requiring
human eyes), and draft reply candidates where a reply is clearly warranted. Emit a single
review report to `drafts/` summarizing what happened so the human can audit in one place.

Generic skill. Domain context (priority contacts, sender-elevation rules, customer table,
project slugs) is loaded from the workspace via `knowledge/soul.md` and optional context
files referenced by the adapter — it is not baked into the skill.

## Inputs

- Authenticated mail provider access (Gmail by default; adapter resolves how — e.g., `gcloud
  auth application-default print-access-token` for Gmail, or an OAuth flow for IMAP)
- `{SHED}/knowledge/soul.md` — voice, values, deep-work hours
- Optional `{SHED}/knowledge/contacts.md` or workspace-specific context file declaring
  priority contacts and sender-elevation rules
- Optional `{SHED}/loops/open.md` (or `loops/active.md` — adapter resolves) — hot accounts
  where incoming mail is more likely to warrant action
- Optional `{SHED}/projects/*.md` — to recognize project-relevant senders

## Process

1. **Load context.** Read soul.md, any contacts/customer context file, open loops, and
   project files. Parallelism: all reads independent.
2. **Fetch inbox.** Page through the inbox (default cap: 200 messages per pass; adapter
   may raise or lower). Pull metadata only (From, Subject, Date, To, Cc) — full bodies are
   fetched on demand for the small subset that needs drafting.
3. **Classify** each message into exactly one bucket:
   - `URGENT` — time-bound, requires action in next 24h
   - `DIRECT` — addressed personally, expects a response but not urgent
   - `REVIEW` — needs human eyes but not action (FYI, status update, summary)
   - `CHATTER` — group threads, peer discussions, social — read if time, skip if not
   - `NOTIFICATION` — system messages, calendar invites already accepted, build alerts
   - `JUNK` — promotional, marketing, automated noise
   Classification rules come from soul.md and the context files. Where rules are absent,
   use conservative defaults (lean toward REVIEW, not JUNK).
4. **Apply safe per-category actions:**
   - JUNK and NOTIFICATION → archive in batch
   - REVIEW → label or star (adapter chooses based on mail provider capability) and leave in inbox
   - URGENT, DIRECT → leave in inbox; mark as candidates for reply drafting
   - CHATTER → archive
5. **Draft replies** for URGENT and DIRECT messages where a reply is clearly warranted.
   Voice and tone come from soul.md. Draft creation does not send — it lands in the mail
   provider's drafts folder, linked to the original thread.
6. **Emit the review report** to `{SHED}/drafts/inbox-triage-YYYY-MM-DD-HHMM.md` containing:
   - Classification distribution (count per bucket)
   - The URGENT and DIRECT items with one-line summaries
   - The REVIEW items with one-line summaries (no draft)
   - List of proposed loops (one line per DIRECT message that warrants tracking): the
     adapter does not append these to `loops/open.md` — they go in the draft for the human
     to promote
   - Sender signals worth noting (new high-priority contacts, escalation patterns)
7. **Print terminal summary** with one-line counts per bucket and the path to the draft.

## Outputs

- `{SHED}/drafts/inbox-triage-YYYY-MM-DD-HHMM.md` (with `<!-- adzekit-draft ... -->`
  provenance header once Phase 2 lands)
- Mail provider state: noise archived, REVIEW items labeled, URGENT/DIRECT drafts created
- Terminal summary

## Parallelism notes

This skill benefits enormously from sub-agent fan-out. Classification is per-message and
embarrassingly parallel. Recommended adapter pattern:
- Orchestrator fetches all metadata, builds the context block, shards messages into chunks
  of ~25, fans out classification workers with concurrency cap 5.
- Workers return JSON (one record per message: id, threadId, category, signals, draft body
  if applicable). Workers have read-only tools — they do not write to the shed and do not
  modify mail provider state.
- Orchestrator collects all JSON, applies mail provider state changes in batched calls
  (e.g., Gmail batchModify), writes drafts via the mail provider API, and emits the single
  review report.

Speed budget: 200 emails should classify in under 90 seconds when the adapter parallelizes
correctly. Single-context monolithic execution is the failure mode this skill is structured
to avoid.

## Safety Rules

- Never archive URGENT, DIRECT, or REVIEW items. Only JUNK, NOTIFICATION, and CHATTER are
  archive-eligible.
- Never send a reply. Drafts only. Human approves and sends.
- Never delete email. Archive is the maximum destructive action.
- Never write to `loops/`, `projects/`, `daily/`, `knowledge/`, or `reviews/`. Loop proposals
  go in the report for human promotion.
- If classification confidence is low for a message, default to REVIEW and leave it in the
  inbox. False positives in JUNK are worse than false negatives.
- Respect deep-work hours from soul.md: if invoked during a declared deep-work window, the
  skill still runs but the adapter suppresses any notification of completion until the
  window closes.

## Notes for adapters

- Mail provider abstraction: the skill spec assumes Gmail but does not require it. An IMAP
  adapter would resolve `archive` to "move to All Mail" or similar.
- Domain personalization: do not hardcode customer lists, sender domains, or project slugs
  in the skill itself. The workspace's `knowledge/soul.md` and optional context files own
  this. A user with no domain context still gets correct generic classification.
- Confidence field: once draft frontmatter lands (Phase 2), the report should declare a
  `confidence:` value (0.0–1.0) per category-action pair. `JUNK → archive` is high
  confidence and `drafts accept --auto` should promote it; `DIRECT → draft reply` is lower
  and requires human review.
