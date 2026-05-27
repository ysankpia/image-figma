# 04 Legacy Path and Stale Doc Inventory Audit

## Fact: Legacy Discovery Loop Code
The following legacy discovery loop directories remain in the repository:
1. `backend/app/media_internal_decomposition/` (M29.6 decomposed media candidates)
2. `backend/app/transparent_asset_report/` (M29 transparent alpha/mask analysis)
3. `backend/app/m29_evidence_contract/` (Legacy icon/shape replay authorization scoring)
4. `backend/app/internal_source_promotion/` (Legacy promotion loop bridge)
5. `backend/app/m29_bridge_fate_trace/` (Legacy bridge diagnostic fate trace)

### Inference
These directories are retained solely for backward compatibility, diagnostic testing, and archival comparison. They are not invoked during normal execution of `/api/upload-preview`.

---

## Fact: Stale Completed Plans in Active Folder (P3)
The directory [docs/plans/active/](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/plans/active/) contains the following 8 plan documents:
* `056-m29-525-real-sample-batch-hardening.md`
* `057-m29-525-editable-control-quality-hardening.md`
* `058-m29-evidence-contract-for-internal-ui-icons.md`
* `060-gemini-review-first-principles-audit.md`
* `062-m29-first-principles-source-chain-code-audit.md`
* `065-m29-composite-media-residual-ownership-rewrite.md`
* `066-m29-model-first-perception-pivot.md`
* `067-m29-model-first-perception-implementation.md`

All of these plans are actually finished, superseded, or completed by the finalized plan [068-m29-model-first-mainline-destructive-refactor.md](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/docs/plans/completed/068-m29-model-first-mainline-destructive-refactor.md).

### Inference & Risk
Leaving these files in `active/` directly violates the `AGENTS.md` directive:
> "Plan status must match its directory: unfinished work belongs in active/, completed work in completed/, and superseded or deferred work in the matching archive/ subdirectory."

This documentation drift can mislead future development agents into treating stale ideas as active goals.

---

## Fact: Stale Test Files
The test folder contains several files specifically targeting legacy loop logic:
- `test_internal_source_promotion.py`
- `test_m29_bridge_fate_trace.py`
- `test_m29_evidence_contract.py`
- `test_media_internal_decomposition.py`
- `test_symbol_fragment_grouping.py`
- `test_text_aware_visual_object_refinement.py`
- `test_text_masked_media_audit.py`
- `test_text_visual_ownership_gate.py`
- `test_transparent_asset_report.py`
- `test_visual_evidence_normalization.py`
- `test_visual_object_candidate_audit.py`

### Inference & Risk
Running `pytest` by default scans and executes all these legacy tests, which still pass today, but increases execution time and creates maintenance overhead.

## Recommendation
Move the 8 stale plans in `docs/plans/active/` to `docs/plans/completed/` or `docs/plans/archive/`. Legacy python modules and their corresponding tests should remain untouched for compatibility reference until explicitly requested to be deleted in a future cleanup ticket.
