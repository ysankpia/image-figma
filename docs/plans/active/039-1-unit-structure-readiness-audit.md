# M39.1 Unit Structure Readiness Audit

- 状态：completed
- 日期：2026-05-22

## Goal

M39.1 is a read-only unit/component readiness audit stage. It explains why the current pipeline has materialized bricks but only a small number of safe rooms.

First-principles boundary:

```text
M39.1 observes existing evidence and writes a report.
M39.1 does not create visible nodes, move DSL nodes, edit assets, or promote units.
```

## Scope

包含：

- Run `m39_1_unit_structure_readiness_audit` after M38 when M31 artifacts exist.
- Read M30 DSL, M31 tree/report, M37 readiness report, optional M38 report, and optional M39 report.
- Normalize M37 unit reports into `candidateUnits`.
- Derive diagnostic product-card, banner, chrome-shell, content-section, and ONNX box candidates.
- Record blocker taxonomy and promotion hints for future M39.2/M31.2 work.
- Add `GET /api/tasks/{taskId}/m39-1-unit-structure-readiness`.

不包含：

- No M40 nested hierarchy.
- No visual fix for a specific black bar, search box, or carousel.
- No Codia schema adapter.
- No model output as truth.

## Runtime Switches

```text
M39_1_UNIT_STRUCTURE_READINESS_ENABLED=true
M39_1_ONNX_UNIT_PROPOSER_ENABLED=true
M39_1_ONNX_MODEL_PATH=/Volumes/WorkDrive/Models/model_fp16.onnx
```

Missing optional ONNX dependencies, missing model, bad output shape, and inference failure only record `modelSkippedReason`/warnings and fall back to rule-only audit.

## Report

M39.1 writes:

```text
storage/m30_1_uploads/{taskId}/m39_1/unit_structure_readiness_report.json
```

The report includes summary counts, `candidateUnits[]`, `blockerSummary`, `promotionHints`, warnings, and model status.

## Acceptance

- Report exists after normal uploads with M31 artifacts.
- Summary guard fields remain:
  ```text
  dslChanged=false
  createdVisibleNodeCount=0
  assetChanged=false
  ```
- Candidate units explain existing M37 safe units, blocked/micro units, product-card/banner/chrome/content candidates, and model-only diagnostic candidates.
- Main M30/M37/M38 behavior remains stable.

## Verification

```bash
cd backend
uv run pytest tests/test_unit_structure_readiness.py tests/test_m30_upload_pipeline.py tests/test_content_chrome_classification.py tests/test_m37_hierarchy_readiness.py tests/test_hierarchy_materialization.py tests/test_config_env.py -q
```
