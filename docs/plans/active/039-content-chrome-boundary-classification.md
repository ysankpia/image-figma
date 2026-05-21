# M39 Content-Chrome Boundary Classification

- 状态：completed
- 创建日期：2026-05-21
- 负责人：未指定

## Goal

M39 introduces a generic classification stage between M30 materialization and M37 hierarchy readiness. It categorizes M30 DSL nodes into `content` (scrollable cards, rows, text) and `chrome` (fixed headers, tab bars, floating action items, status bars) using:
1. Generic geometry-based rules (resolution-independent relative bounds).
2. An optional, non-blocking ONNX model proposer (`model_fp16.onnx`) that proposes candidate chrome/content regions.

First-principles boundary:
```text
Classification labels exist in node metadata.
M39 does not create new visible elements or alter page layouts.
M37/M38 use M39 classification to prevent grouping content and chrome nodes together.
```

## Scope

包含：
- A new pipeline stage `m39_boundary_classification` that runs after M30 materialization and before M37 hierarchy readiness.
- A generic geometry-based classification module in `backend/app/content_chrome_classification.py`.
- An optional, non-blocking ONNX model adapter that loads `/Volumes/WorkDrive/Models/model_fp16.onnx` if `onnxruntime` is present, running YOLOv8 detection to propose candidate chrome zones.
- Snap-to-element overlap resolution: M30 nodes are classified based on rule parameters and model proposed bounding boxes.
- Validation checks in M37 (hierarchy readiness) and M38 (hierarchy materialization) to reject groupings that cross the content-chrome boundary.

不包含：
- Hardcoded hacks for specific text, buttons, or page URLs.
- Moving elements or visual changes in the final layout.
- Auto Layout, Figma Component/Instance, or batch upload changes.

## Steps

1. **Design & Plan**: Write M39 plan and ADR.
2. **Classification Logic (`backend/app/content_chrome_classification.py`)**:
   - Define a rule-based classifier using relative geometry (e.g. top 12% height, bottom 12% height, full-width header/footer spans, right-edge float zones).
   - Implement the optional ONNX model runner:
     - Resize input PNG to 640x640 (preserving aspect ratio with letterboxing or simple scaling).
     - Run inference on `/Volumes/WorkDrive/Models/model_fp16.onnx`.
     - Filter bounding boxes with score >= threshold, scale them back to original page coordinates.
     - Apply Non-Maximum Suppression (NMS) to obtain clean candidate chrome boxes.
   - Combine rule checks and model candidates: any node overlapping significantly (e.g., overlap ratio > 0.8) with a proposed model box gets classified as `chrome`, provided it doesn't violate core geometric safety bounds (e.g., a card in the page center should never be chrome).
   - Update node meta in M30 DSL with `boundaryClassification` equal to `"chrome"` or `"content"`.
3. **Pipeline Integration (`backend/app/m30_upload_pipeline.py`)**:
   - Register and run the M39 stage.
   - Save intermediate report `m39_boundary_classification_report.json` in the task directory.
4. **M37/M38 Boundary Enforcement**:
   - Modify M37 (`hierarchy_readiness.py`) to mark a reconstruction unit unsafe (`unsafeReasons` includes `boundary_classification_conflict`) if it contains both `chrome` and `content` nodes.
   - Modify M38 (`hierarchy_materialization.py`) to skip grouping any units that have classification conflicts.
5. **Tests & Validation**:
   - Write comprehensive unit tests in `backend/tests/test_content_chrome_classification.py`.
   - Update backend tests to verify that the M39 stage runs successfully and doesn't break existing M30/M37/M38 tests.
   - Update docs index and reference files.

## Acceptance

- Intermediate report `m39_boundary_classification_report.json` exists in `storage/m30_1_uploads/{taskId}/m39/`.
- M30 DSL nodes in `m30_materialized_dsl.json` contain `boundaryClassification` (either `"chrome"` or `"content"`) in their `meta`.
- Reconstruction units mapping to both chrome and content nodes are marked unsafe in M37 and skipped in M38.
- Main upload pipeline is robust and succeeds even if `onnxruntime` is missing (falls back gracefully to rule-only classification).
- Standard backend tests pass without regression.

## Validation

```bash
cd backend
# Run focused classification and pipeline tests
uv run pytest tests/test_content_chrome_classification.py tests/test_hierarchy_materialization.py tests/test_m37_hierarchy_readiness.py tests/test_m30_upload_pipeline.py -q
# Run all tests
uv run pytest -q
```

## Notes

- The ONNX model `model_fp16.onnx` is located at `/Volumes/WorkDrive/Models/model_fp16.onnx` and is a YOLOv8-based model with 1 class.
- To prevent extra runtime dependencies, `onnxruntime` must not be added to the core project dependencies, but dynamically loaded. Developers can test it locally by installing it in their environment if they wish, while the pipeline handles its absence gracefully.
