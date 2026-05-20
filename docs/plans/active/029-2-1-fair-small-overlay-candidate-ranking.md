# M29.2.1 Fair Small Overlay Candidate Ranking

- 状态：completed
- 日期：2026-05-20

## Goal

M29.2.1 fixes two proposal-layer bugs in M29.2:

```text
global candidate starvation
strict baseline rejection for tiny overlay labels
```

The stage remains audit-only. It does not recognize text, patch OCR, feed M30, or change Figma output.

## Plan

- Generate proposals for every M29.0.2 accepted image before applying the global candidate cap.
- Keep a local per-image budget, then merge candidates with round-robin fair selection.
- Rank each image's candidates by decision class, corner proximity, edge proximity, tiny-label-sized area, and stable y/x order.
- Keep texture, size, OCR coverage, and line-like rejection as hard gates.
- For tiny overlay candidates, treat large `baselineSpread` as a report penalty rather than a hard rejection.
- Record `cornerDistance`, `imageLocalRank`, `selectionRound`, and `baselinePenaltyApplied` in candidate metrics.

## Non-Goals

- No slash, fraction, `1/6`, `1/9`, app, page, or coordinate-specific rules.
- No local OCR re-probe behavior change.
- No M30 supplemental materialization.
- No OCR, M29, M31, M37, fallback erasure, Renderer, or plugin contract change.

## Acceptance

- Later accepted images cannot be starved by earlier noisy images.
- Tiny overlay labels with vertical component spread can remain `proposal_only` with `baseline_spread_penalty`.
- The report still keeps `materializedTextCount=0`, `createdNewBBoxCount=0`, and `dslChanged=false`.
- Current sample's `m29_image_003` appears in the default M29.2 report candidates.

## Verification

```bash
cd backend
uv run pytest tests/test_png_tools.py tests/test_small_overlay_text_proposal.py tests/test_m30_upload_pipeline.py tests/test_config_env.py -q
```

Completed verification:

```text
52 passed in 32.45s
233 passed in 42.49s
pnpm run check passed
git diff --check passed
```

Manual sample check against `task_3cb2036ec6c3`:

```text
m29_image_003 appears in the default 12-candidate M29.2 report.
Top m29_image_003 candidate is proposal_only with baseline_spread_penalty.
materializedTextCount=0, createdNewBBoxCount=0, dslChanged=false.
```
