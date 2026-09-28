# Optional delegation pattern

Delegation is an agent-runtime optimization, not part of AdzeKit's core.

Use it only when a workflow contains many independent items and measurement
shows that parallel workers help. A runtime without sub-agents must still be
able to run the workflow in one context.

## Contract

```text
orchestrator -> independent read-only workers -> structured results -> proposal
```

- The orchestrator chooses work slices and owns side effects.
- Workers receive only the context required for their slice.
- Workers return structured data and do not write workspace files.
- The orchestrator merges results and submits one or more proposals.
- Worker failure is data; it does not erase successful sibling results.

Five concurrent workers and one level of delegation are conservative defaults,
not format requirements. Adapters should tune them with evidence.

## Safety boundary

The important boundary is not “sub-agent” versus “main agent.” It is read versus
write. Generated work enters the proposal queue through the orchestrator. A
worker should not modify human-owned files or external systems.

## Runtime mappings

Claude Code can map workers to its agent tool. Other runtimes may use tasks,
threads, processes, batch inference, or no delegation at all. Those details
belong in the runtime adapter, not in a workflow definition.

## Verification

For an adapter that delegates, verify:

1. workers cannot mutate the workspace;
2. inputs are smaller than the orchestrator's full context;
3. outputs validate against the declared structure;
4. one failed worker does not discard other results;
5. the final mutation is a reviewable proposal.
