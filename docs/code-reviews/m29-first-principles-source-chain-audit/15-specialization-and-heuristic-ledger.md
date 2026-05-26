# 15 Specialization And Heuristic Ledger

## Purpose

This ledger separates normal mathematical heuristics from specialization risk.

Valid heuristic:

```text
depends on geometry, area, contrast, overlap, containment, texture, alpha, source confidence, or repair risk
```

Specialization risk:

```text
depends on text content, brand, filename, task id, fixed path, fixed absolute coordinates, theme color, industry, account, or one screenshot structure
```

## Ledger

| Layer | Heuristic | Current status | Risk |
| --- | --- | --- | --- |
| M29.2 text | `min_text_confidence = 0.60` | Generic OCR quality gate | Low |
| M29.2 text/media | `editable_text_max_media_overlap = 0.82` | Generic containment/display-text separation | Medium |
| M29.2 media | color/texture/area thresholds for media regions | Generic pixel complexity gate | Medium |
| M29.2 controls | finite control width/height/aspect/text containment/texture gates | Generic control-background gate | Medium |
| M29.2 icons | skip media-contained symbols from direct replay | Safe ownership boundary | Medium product gap |
| M29.2 unknowns | selected tab indicator is not icon replay | Semantically reasonable but under-modeled | Medium |
| M29.3 relation | bbox primary/secondary geometry thresholds | Generic geometry math | Low |
| M29.4 cluster | weak row/column/repetition/background-anchor scoring | Generic weak structure evidence | Low |
| M29.5 cleanup | text/media containment overlap thresholds | Generic cleanup permission | Medium |
| M29.5 promoted icon overlap | `MAX_PROMOTED_INTERNAL_ICON_TEXT_OVERLAP_RATIO = 0.14` | Generic anti-text-leak guard | Medium |
| M29.6 pixel components | min/max area, short edge, aspect, foreground distance, luma, saturation | Generic connected-component filtering | Medium |
| M29.6 anchors | above/below/left/right/near OCR anchors | Generic relation evidence | Low |
| Transparent asset | max area, max text overlap, hero penalty, edge alpha, background stability | Generic alpha extraction guard | Medium |
| Evidence contract | allow/report thresholds and evidence/risk weights | Generic evidence consistency gate | Medium |
| Promotion | requires transparent assetPath + evidence allow | Safe bridge gate | High product bottleneck |
| Materializer | max visible nodes, controlled group score/member/area thresholds | Generic execution safety | Low |

## Code Evidence

M29.2 options:

```text
backend/app/source_ui_physical_graph/types.py:37-66
```

M29.6 pixel component constants:

```text
backend/app/media_internal_decomposition/candidates.py:14-23
```

Transparent asset constants:

```text
backend/app/transparent_asset_report/candidates.py:9-16
backend/app/transparent_asset_report/alpha.py:10-17
```

Evidence contract constants:

```text
backend/app/m29_evidence_contract/scoring.py:8-14
```

M29.5 promoted icon overlap:

```text
backend/app/m29_replay_plan/overlap.py:42
```

Materializer options:

```text
backend/app/plan_materializer/types.py:7-21
```

## What Is Not Specialization

These are not specialization by themselves:

```text
OCR anchor directions
area bounds
aspect-ratio bounds
text-overlap bounds
media containment bounds
hero/texture penalties
local background stability
alpha edge metrics
node budget
```

They are legitimate if they stay tied to source evidence and are validated on multiple samples.

## Actual Specialization Risks Found

### Risk 1: Semantic role without representation path

`selected_tab_indicator_not_icon` avoids falsely making a selected tab marker into an icon. That is correct. But current chain lacks a positive representation for selected marker / tab state.

Result:

```text
not wrong as icon
but also not replayed as marker/control state
```

This is not text/brand specialization. It is a missing role contract.

### Risk 2: "Execution support" behaves like a hidden single bottleneck

Transparent asset report requires internal candidates to be high confidence or group-supported before alpha analysis. This is generic, not special-cased. But in real artifacts it can block well-anchored medium candidates.

Result:

```text
M29.6 sees candidate
transparent refuses alpha analysis
evidence has no asset
promotion impossible
```

This is a product-quality bottleneck.

### Risk 3: Promotion only supports internal icons

Promotion only appends `raster_icon` source objects. It has no equivalent path for:

```text
internal control background
selected marker
table marker
small state dot
single-control structure
```

This is a missing abstraction, not a threshold tuning issue.

### Risk 4: Media containment is both safety and information-loss source

Skipping media-contained symbols in M29.2 prevents double-ownership. But it makes M29.6/transparent/evidence/promotion the only recovery path.

If that bridge is too strict, internal UI remains raster-only.

## Formula Issues

### Issue 1: Transparent asset as hard prerequisite

Evidence contract includes many independent evidence terms, but visible replay still requires `transparentAllowed`.

This makes alpha extraction a hard bridge requirement even when:

```text
candidate score is medium/high
text anchor is strong
hero penalty is low
text overlap is zero
candidate is inside media
```

This is safe but conservative. It is the clearest current blocker for Codia-like icon selectability.

### Issue 2: Control/background evidence does not share the same bridge

M29.2 can recognize some finite control backgrounds outside major media. But media-contained button backgrounds need an internal control/background candidate contract analogous to internal icons.

Current M29.6 candidates are icon-centered.

### Issue 3: Report-only surfaces need promotion-class contracts

M29.6, transparent, and evidence are correctly report-only. But Codia-like output requires specific bridges from report evidence back into M29.2.

The existing bridge is too narrow:

```text
internal icon only
requires transparent asset path
```

## Current Anti-Specialization Guard

M29.6, evidence contract, and promotion reports declare:

```text
noSpecializedTextFilenameThemeOrFixedBboxRules = true
```

Validation enforces this for M29.6 and evidence contract.

Code evidence:

```text
backend/app/media_internal_decomposition/validation.py:26-27
backend/app/m29_evidence_contract/validation.py:26-27
backend/app/internal_source_promotion/types.py:14
```

This is good, but it is a declaration, not proof. The ledger above is the proof surface.

## Recommended Next Action

Do not remove mathematical thresholds blindly. Instead:

```text
1. Keep thresholds tied to source evidence and regression samples.
2. Add explicit role contracts where missing: selected_marker, table_marker, internal_control_background.
3. Replace hard transparent asset gating for some candidates with a staged allow path that still preserves cleanup safety.
4. Record per-gate rejection reasons in aggregate reports so one bottleneck cannot hide behind confidence.
```
