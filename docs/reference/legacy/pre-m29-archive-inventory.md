# Pre-M29 Archive Inventory

M30.2.2 removed the frozen pre-M29 backend chain from active runtime source.

This inventory records what was removed and what historical evidence remains.

## Runtime Status

Current status:

```text
removed_from_runtime_source
```

There is no active environment flag to re-enable the old chain.

## Removed Runtime Surface

| Surface | Status |
| --- | --- |
| `POST /api/upload` | removed_in_m30_2_2 |
| `GET /api/tasks/{taskId}/primitives` | removed_in_m30_2_2 |
| `GET /api/tasks/{taskId}/ocr` | removed_in_m30_2_2 |
| `GET /api/tasks/{taskId}/dsl-patch` | removed_in_m30_2_2 |
| `GET /api/tasks/{taskId}/text-replacements` | removed_in_m30_2_2 |
| `GET /api/tasks/{taskId}/text-bindings` | removed_in_m30_2_2 |
| `GET /api/tasks/{taskId}/component-structures` | removed_in_m30_2_2 |
| `GET /api/tasks/{taskId}/component-annotations` | removed_in_m30_2_2 |
| `GET /api/tasks/{taskId}/layer-separation-candidates` | removed_in_m30_2_2 |
| `GET /api/tasks/{taskId}/asset-slice-candidates` | removed_in_m30_2_2 |
| `GET /api/tasks/{taskId}/icon-candidates` | removed_in_m30_2_2 |
| `GET /api/tasks/{taskId}/icon-coverage-audit` | removed_in_m30_2_2 |
| `GET /api/tasks/{taskId}/icon-gap-candidates` | removed_in_m30_2_2 |
| `GET /api/tasks/{taskId}/icon-placement-plan` | removed_in_m30_2_2 |
| `GET /api/tasks/{taskId}/icon-visible-fallback` | removed_in_m30_2_2 |
| `GET /api/tasks/{taskId}/icon-business-candidates` | removed_in_m30_2_2 |
| `GET /api/tasks/{taskId}/perception-benchmark` | removed_in_m30_2_2 |
| `GET /api/tasks/{taskId}/sam-visual-candidates` | removed_in_m30_2_2 |

## Removed App Modules

| Path | Status |
| --- | --- |
| `backend/app/visual_primitives.py` | removed_in_m30_2_2 |
| `backend/app/dsl_patch.py` | removed_in_m30_2_2 |
| `backend/app/text_replacement.py` | removed_in_m30_2_2 |
| `backend/app/text_binding.py` | removed_in_m30_2_2 |
| `backend/app/component_structure.py` | removed_in_m30_2_2 |
| `backend/app/component_annotation.py` | removed_in_m30_2_2 |
| `backend/app/layer_separation.py` | removed_in_m30_2_2 |
| `backend/app/asset_slice.py` | removed_in_m30_2_2 |
| `backend/app/icon_candidate.py` | removed_in_m30_2_2 |
| `backend/app/icon_coverage.py` | removed_in_m30_2_2 |
| `backend/app/icon_gap_candidate.py` | removed_in_m30_2_2 |
| `backend/app/icon_placement_plan.py` | removed_in_m30_2_2 |
| `backend/app/icon_visible_fallback.py` | removed_in_m30_2_2 |
| `backend/app/icon_business_candidate.py` | removed_in_m30_2_2 |
| `backend/app/perception_benchmark.py` | removed_in_m30_2_2 |
| `backend/app/sam_visual_candidate.py` | removed_in_m30_2_2 |
| `backend/app/ui_visual_extraction.py` | removed_in_m30_2_2 |

## Removed Scripts

| Path | Status |
| --- | --- |
| `backend/scripts/run_m26_perception_smoke.py` | removed_in_m30_2_2 |
| `backend/scripts/run_m27_sam_visual_smoke.py` | removed_in_m30_2_2 |
| `backend/scripts/run_m28_single_visual_extraction.py` | removed_in_m30_2_2 |

## Removed Tests

The pure legacy module tests were deleted with the modules. Shared-current tests such as assets, OCR provider, config, upload flow, M29, and M30 tests remain active.

## Preserved Evidence

Historical evidence remains in:

```text
git history
docs/plans/archive/pre_m29/
docs/decisions/0001-0031*.md
docs/reference/legacy/*.original.md
```

Old local database tables and `backend/storage/**` files may still exist on a developer machine. M30.2.2 does not migrate or delete local historical data.
