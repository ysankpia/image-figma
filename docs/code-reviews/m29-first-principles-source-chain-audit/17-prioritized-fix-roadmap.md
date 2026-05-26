# 17 Prioritized Fix Roadmap

## First-Principles Conclusion

Current M29 is not failing because the final Figma Renderer cannot draw nodes. It is failing because several real UI objects never become final M29.2 source objects and therefore never enter final M29.5 replay.

The target is not:

```text
more confidence
more output nodes
downstream patches
single-sample special cases
```

The target is:

```text
evidence-supported source objects
safe visible replay
safe cleanup authorization
selectable/editable controls with bounded repair risk
```

## Priority 1: Bridge Rejection Diagnostics

Goal:

```text
Make every internal candidate's final fate explainable from one trace.
```

Implement later:

```text
candidate detected
transparent preflight decision
evidence decision
promotion decision
final M29.5 action
materializer replay/skipped result
```

Why first:

```text
Current failures require opening 4-5 reports manually.
Without trace aggregation, future fixes will look like threshold guessing.
```

Acceptance:

```text
For a given candidateId, report shows exact first blocking gate and reason.
No runtime behavior change required for this stage.
```

## Priority 2: General Internal Candidate Execution Support

Goal:

```text
Allow medium-confidence but strongly anchored internal candidates to run transparent alpha analysis when independent evidence is strong.
```

Do not do:

```text
do not whitelist text content, brand, filename, task id, fixed bbox, fixed coordinates, or theme color
do not allow cleanup before visible replacement exists
```

Candidate evidence should include:

```text
candidateDecision = accepted_report_candidate
role = internal_icon_candidate
textAnchorScore >= threshold
textOverlap = low
heroPenalty = low
mediaContainment high
anchor relation clear
local foreground component compact
not text mask
```

Acceptance:

```text
Previously blocked anchored candidates reach alpha analysis.
Weak texture fragments still reject.
At least one real sample plus targeted synthetic tests prove no broad false-positive jump.
```

## Priority 3: Transparent Asset Gate Split

Goal:

```text
Separate "may attempt alpha analysis" from "may visible replay" from "may cleanup copied media".
```

Current issue:

```text
internal_candidate_not_execution_supported blocks alpha analysis,
then missing assetPath blocks evidence/promotion.
```

Recommended contract:

```text
analysis_allowed
asset_generated
visible_replay_allowed
cleanup_allowed
```

Acceptance:

```text
Candidates can generate diagnostic alpha assets without automatically becoming visible nodes.
Evidence contract still controls visible replay.
M29.5 still controls cleanup.
```

## Priority 4: Internal Control / Button Background Contract

Goal:

```text
Promote media-contained control backgrounds as shape_geometry when evidence is strong.
```

Source evidence should be generic:

```text
finite bbox
stable fill or stable gradient class
contains OCR text or icon/text pair
low texture
reasonable rounded-rect geometry
inside media
not page-sized
cleanup risk bounded
```

Do not do:

```text
do not make materializer infer button backgrounds
do not use visible text values such as login/Google/充值 as rule keys
```

Acceptance:

```text
media-contained button can produce shape_replay + text/icon members.
Copied media cleanup is only created by M29.5.
Controlled structure may group members only after visible nodes exist.
```

## Priority 5: Selected Marker / Table Marker Role Path

Goal:

```text
Represent state markers and small table/list markers without misclassifying them as icons.
```

New source roles may be needed:

```text
selected_marker
table_marker
status_dot
indicator_shape
```

These should normally replay as shape geometry, not raster icons.

Acceptance:

```text
bottom tab selected marker becomes selectable as state/indicator shape.
table marker / small dot becomes selectable when geometry and repetition evidence support it.
Icon replay remains reserved for icon-like foreground objects.
```

## Priority 6: Render-Back / Cleanup Risk Gate

Goal:

```text
Prevent cleanup scars and double-image artifacts using local visual validation.
```

Use after source contracts improve:

```text
local before/after patch comparison
alpha-mask coverage sanity
unexplained erased area check
double-owned area check
```

Acceptance:

```text
cleanup is rejected or downgraded when it increases local visual error beyond threshold.
Visible replay can still happen without copied-media cleanup if cleanup risk is high.
```

## Priority 7: Legacy Cleanup

Goal:

```text
Reduce wrong-layer reasoning from historical packages and stale env/docs.
```

Do after behavior-facing fixes:

```text
label compatibility-only packages
remove stale env vars if not current settings
archive formulas that are not used
delete dead packages only with explicit plan and tests
```

Acceptance:

```text
current-mainline docs and imports make active runtime obvious.
No historical package is mistaken for active source truth.
```

## Non-Goals

Do not implement these as shortcuts:

```text
Renderer/plugin special handling for missing icons
materializer bbox/color/text heuristics to create missing nodes
fixed-coordinate rules for current screenshots
brand/text-specific button rules
global confidence loosening
automatic cleanup without M29.5 target
external AI background removal as default path
```

## Suggested Stage Order

```text
063 bridge fate trace report
064 internal candidate execution support
065 transparent asset gate split
066 internal control background promotion
067 marker/state role promotion
068 cleanup render-back gate
069 legacy/dead-path cleanup
```

Each stage should follow:

```text
targeted tests
representative real-sample run
artifact inspection
bug/plan update
stage-scoped commit
```

## Final Judgment

The evidence contract direction is correct. The problem is that the current executable bridge is too narrow:

```text
M29.6 / transparent / evidence can see many things,
but only internal raster icons with transparent assetPath can cross back into M29.2.
```

To approach Codia-like output, the next work must widen the bridge with explicit source roles and gated promotion paths, not add downstream patches.
