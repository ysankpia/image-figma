# ADR: Use Replay Plan As M29 Direct Quality Gate

- 状态：accepted
- 日期：2026-05-23

## Context

M29.2 can decide source pixel ownership. M29.3.1 can describe pairwise region relations. M29.4 can identify stable local design clusters.

If `m29_direct_replay` consumes only raw source objects, these evidence layers remain diagnostic and cannot directly reduce visible replay errors.

The failure mode is:

```text
good evidence exists
-> replay ignores part of it
-> left-side Figma output still has ghosts, wrong replay, missed replay, or too many layers
```

## Decision

Add M29.5 as a replay quality plan stage before M29 direct replay:

```text
M29.2 source objects
-> M29.3.1 relation graph
-> M29.4 stable clusters
-> M29.5 replay plan
-> M29 direct replay DSL
```

M29.5 writes `m29_5/replay_plan.json` with final replay actions, cleanup targets, suppressed duplicates, relation edge ids, cluster ids, reasons, and risks.

`m29_direct_replay` must prefer this plan when it exists. Without the plan, it falls back to the current M29.2 direct replay behavior.

## Consequences

- Replay quality decisions are inspectable before DSL materialization.
- Node budget and duplicate suppression happen before visible nodes are created.
- Cleanup targets are explicit, so copied image asset text erasure is not hidden inside replay heuristics.
- M29.4 cluster evidence can support confidence and suppression without becoming Component/Instance or UI semantic truth.

## Boundaries

- M29.5 does not create DSL nodes.
- M29.5 does not write or modify assets.
- M29.5 does not change `/api/tasks/{taskId}/dsl`.
- M29.5 does not add routes or plugin UI.
- M29.5 does not infer SearchBar, Card, TabBar, ProductCard, or other UI truth names.
- M29.5 is a compare-left experiment quality gate, not a default path switch.
