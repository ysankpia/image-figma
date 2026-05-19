# Pre-M29 Archive Inventory

M30.2.1 freezes the pre-M29 runtime surface but does not move implementation code. This inventory is the handoff for a later physical archive phase.

## Runtime Status

Default runtime status:

```text
frozen_runtime_surface
```

Legacy runtime can be re-enabled with:

```text
LEGACY_PRE_M29_UPLOAD_ENABLED=true
```

## Candidate App Modules

| Path | Status |
| --- | --- |
| `backend/app/visual_primitives.py` | candidate_for_physical_archive_next |
| `backend/app/dsl_patch.py` | candidate_for_physical_archive_next |
| `backend/app/text_replacement.py` | candidate_for_physical_archive_next |
| `backend/app/text_binding.py` | candidate_for_physical_archive_next |
| `backend/app/component_structure.py` | candidate_for_physical_archive_next |
| `backend/app/component_annotation.py` | candidate_for_physical_archive_next |
| `backend/app/layer_separation.py` | candidate_for_physical_archive_next |
| `backend/app/asset_slice.py` | candidate_for_physical_archive_next |
| `backend/app/icon_candidate.py` | candidate_for_physical_archive_next |
| `backend/app/icon_coverage.py` | candidate_for_physical_archive_next |
| `backend/app/icon_gap_candidate.py` | candidate_for_physical_archive_next |
| `backend/app/icon_placement_plan.py` | candidate_for_physical_archive_next |
| `backend/app/icon_visible_fallback.py` | candidate_for_physical_archive_next |
| `backend/app/icon_business_candidate.py` | candidate_for_physical_archive_next |
| `backend/app/perception_benchmark.py` | candidate_for_physical_archive_next |
| `backend/app/sam_visual_candidate.py` | candidate_for_physical_archive_next |
| `backend/app/ui_visual_extraction.py` | candidate_for_physical_archive_next |

## Legacy Routes

| Surface | Status |
| --- | --- |
| `POST /api/upload` | frozen_runtime_surface |
| `GET /api/tasks/{taskId}/primitives` | frozen_runtime_surface |
| `GET /api/tasks/{taskId}/ocr` | frozen_runtime_surface |
| `GET /api/tasks/{taskId}/dsl-patch` | frozen_runtime_surface |
| `GET /api/tasks/{taskId}/text-replacements` | frozen_runtime_surface |
| `GET /api/tasks/{taskId}/text-bindings` | frozen_runtime_surface |
| `GET /api/tasks/{taskId}/component-structures` | frozen_runtime_surface |
| `GET /api/tasks/{taskId}/component-annotations` | frozen_runtime_surface |
| `GET /api/tasks/{taskId}/layer-separation-candidates` | frozen_runtime_surface |
| `GET /api/tasks/{taskId}/asset-slice-candidates` | frozen_runtime_surface |
| `GET /api/tasks/{taskId}/icon-candidates` | frozen_runtime_surface |
| `GET /api/tasks/{taskId}/icon-coverage-audit` | frozen_runtime_surface |
| `GET /api/tasks/{taskId}/icon-gap-candidates` | frozen_runtime_surface |
| `GET /api/tasks/{taskId}/icon-placement-plan` | frozen_runtime_surface |
| `GET /api/tasks/{taskId}/icon-visible-fallback` | frozen_runtime_surface |
| `GET /api/tasks/{taskId}/icon-business-candidates` | frozen_runtime_surface |
| `GET /api/tasks/{taskId}/perception-benchmark` | frozen_runtime_surface |
| `GET /api/tasks/{taskId}/sam-visual-candidates` | frozen_runtime_surface |

## Legacy Regression Tests

Current detected legacy-upload regression files:

```text
backend/tests/test_asset_slice.py
backend/tests/test_assets.py
backend/tests/test_baidu_ocr.py
backend/tests/test_component_annotation.py
backend/tests/test_component_structure.py
backend/tests/test_icon_business_candidate.py
backend/tests/test_icon_candidate.py
backend/tests/test_icon_coverage.py
backend/tests/test_icon_gap_candidate.py
backend/tests/test_icon_placement_plan.py
backend/tests/test_icon_visible_fallback.py
backend/tests/test_layer_separation.py
backend/tests/test_ocr_patch.py
backend/tests/test_perception_benchmark.py
backend/tests/test_sam_visual_candidate.py
backend/tests/test_text_binding.py
backend/tests/test_text_replacement.py
backend/tests/test_upload_flow.py
backend/tests/test_visual_primitives.py
```

Status:

```text
retained_for_legacy_reference
```

M30.2.2 should decide whether these stay as opt-in regression tests, move under a legacy test namespace, or are removed with the physical archive.

## Legacy Scripts

| Path | Status |
| --- | --- |
| `backend/scripts/run_m26_perception_smoke.py` | candidate_for_physical_archive_next |
| `backend/scripts/run_m27_sam_visual_smoke.py` | candidate_for_physical_archive_next |
| `backend/scripts/run_m28_single_visual_extraction.py` | candidate_for_physical_archive_next |

## Archived Plans

The M1-M28 plans were moved to:

```text
docs/plans/archive/pre_m29/
```

Detected count:

```text
28
```

Status:

```text
retained_for_legacy_reference
```

Old ADRs `0001` through `0031` remain under `docs/decisions/` as legacy decision history.

