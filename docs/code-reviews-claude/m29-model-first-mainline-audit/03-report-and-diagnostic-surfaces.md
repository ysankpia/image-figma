# 03 Report and Diagnostic Surfaces Audit

## Fact: Report-Only/Permission-Only Validation
All post-replay reports generated in the upload-preview pipeline are strictly report-only or permission-only. They do not mutate the `design.dsl.json` or write assets to storage.

We audited the validation modules for each stage:
1. **Ownership Conservation**: [ownership_conservation/validation.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/ownership_conservation/validation.py) enforces:
   - `dslChanged = False`
   - `assetChanged = False`
   - `createdVisibleNodeCount = 0`
   - `reportOnly = True`
2. **Hierarchy Candidates**: [hierarchy_candidate_report/validation.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/hierarchy_candidate_report/validation.py) enforces:
   - `dslChanged = False`
   - `assetChanged = False`
   - `createdVisibleNodeCount = 0`
3. **Sibling Groups**: [sibling_group_candidate_report/validation.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/sibling_group_candidate_report/validation.py) enforces:
   - `dslChanged = False`
   - `assetChanged = False`
   - `createdVisibleNodeCount = 0`
   - `groupMaterializationPermission = False`
4. **Layout Energy**: [layout_energy_report/validation.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/layout_energy_report/validation.py) enforces:
   - `dslChanged = False`
   - `assetChanged = False`
   - `createdVisibleNodeCount = 0`
   - `autoLayoutPermission = False`
5. **Auto Layout Permission**: [auto_layout_permission_report/validation.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/auto_layout_permission_report/validation.py) enforces:
   - `dslChanged = False`
   - `assetChanged = False`
   - `createdVisibleNodeCount = 0`
   - `autoLayoutCreated = False`
   - `permissionOnly = True`

## Fact: Diagnostic Fate Trace Isolation
The stage `run_m29_perception_fate_trace_stage` compiles [perception_fate_trace_report.json](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/m29_perception_fate_trace/pipeline.py).
As verified, this report is written *after* materialization is complete. It maps candidate fates for developer debugging but is **not imported or consumed** by upstream compilers, replay planning, or the materializer.

## Inference: Zero Back-Pollution of Source Truth
Because all of these 5 reports and the diagnostic fate trace run *after* replay decisions are finalized (or as diagnostic sub-stages), and because their schemas enforce zero side-effects, there is **no risk of back-pollution**. They act as a clean, unidirectional evidence pipeline that does not corrupt the source truth.

## Risk
None. The architecture here is extremely clean and compliant.

## Recommendation
Maintain this unidirectional flow. If future features introduce auto-layout grouping, the materializer should consume the `auto_layout_permission_report` to generate frame nodes, but the reports themselves must never write directly to the DSL.
