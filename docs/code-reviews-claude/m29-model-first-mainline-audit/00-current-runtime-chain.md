# 00 Current Runtime Chain Audit

## Fact: Pipeline Orchestration & Interactive Mainline
The active mainline pipeline for upload-preview is located in [pipeline.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/upload_preview/pipeline.py#L37-L335).

It executes the following stages sequentially:
1. **OCR**: `run_ocr` to extract raw bounding boxes.
2. **Model Candidate Detection**: `run_m29_perception_model_stage` (if `m29_perception_model_enabled` is `True`).
3. **M29 Raw Physical Graph**: `run_m29_visual_primitive_stage` to detect shapes/images using standard rules.
4. **M29.2 Source Physical Graph**: `run_m292_source_ui_physical_stage` to extract pixel owners.
5. **M29 Perception Compiler**: `run_m29_perception_source_compiler_stage` to compile model candidates and integrate them back into the enhanced M29.2 graph.
6. **M29.3 Relation Graph**: `run_m2931_relation_stage` to establish containment/overlaps.
7. **M29.4 Design Cluster**: `run_m294_cluster_stage` to produce weak grouping evidence.
8. **M29.5 Replay Plan**: `run_m295_replay_plan_stage` to establish visible actions, deduplication, and cleanup permissions.
9. **Ownership Conservation**: `run_m29_ownership_conservation_stage`.
10. **Hierarchy Candidates**: `run_m29_hierarchy_candidate_stage`.
11. **Sibling Groups**: `run_m29_sibling_group_candidate_stage`.
12. **Layout Energy**: `run_m29_layout_energy_stage`.
13. **Auto Layout Permission**: `run_m29_auto_layout_permission_stage`.
14. **Materialization**: `run_materialization_stage` to generate `design.dsl.json`.
15. **Perception Fate Trace**: `run_m29_perception_fate_trace_stage` (diagnostic tracing of model candidates).
16. **Diagnostic Surfaces**: If runtime mode is `diagnostic` or `full`:
    - `run_m29_design_token_stage`
    - `run_m29_b_stage_quality_stage`
    - `run_m29_dsl_visual_comparison_stage`
17. **Asset Publishing**: `publish_m29_assets` to export replayed assets.

### Legacy Loop Exclusion
The legacy discovery loop stages (`media_internal_decomposition`, `transparent_asset_report`, `m29_evidence_contract`, `internal_source_promotion`, `m29_bridge_fate_trace`) are **completely absent** from the mainline pipeline in `pipeline.py`. They are not wired back into the active runtime paths.

## Inference: Option Settings Separation
The option fields mapped from settings have a clear separation of concerns in [config.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/config.py#L27-L30) and [pipeline.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/upload_preview/pipeline.py#L337-L348):
* `upload_preview_profile`: Determines the artifact generation depth (`production` disables debug/preview PNGs to save space; `development` enables them).
* `upload_preview_runtime_mode`: Controls post-materialization evaluation stages (`interactive` is the lightweight client default; `diagnostic`/`full` enable token extraction, quality reports, and visual pixel differences).
* `m29_perception_model_enabled`: A toggle flag that enables/disables the model proposal and compiler stages without affecting the rest of the physical rules.

## Inference: Perception Model Proposal Isolation
The stage `run_m29_perception_model_stage` is strictly report-only. As verified in [pipeline.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/perception_model_report/pipeline.py#L52-L72), it outputs a report validated against `M29PerceptionModelReport` schema where:
* `reportOnly = True`
* `dslChanged = False`
* `assetChanged = False`
* `createdVisibleNodeCount = 0`

It does not create visible elements or assets, nor does it grant cleanup authorizations. It only proposes candidates.

## Risk
The runtime separation is healthy. The only risk is that legacy packages remain in the repository and are still compiled or imported by test suites (see `04-legacy-path-and-stale-doc-inventory.md`).

## Recommendation
Keep the runtime chain clean. Ensure that any future structure optimizations (like Codia grouping or Auto Layout generation) are built on top of the M29.5 plan-driven materializer outputs, rather than restoring older B-stage loops.
