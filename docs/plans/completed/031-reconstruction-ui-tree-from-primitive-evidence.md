# M31 Reconstruction UI Tree From Primitive Evidence

- 状态：completed
- 创建日期：2026-05-20
- 负责人：Antigravity

## Goal

M31 从第一性原理修正 M29 之后的抽象层：PNG 是被压扁后的渲染结果，M29 只负责把像素拆成可审计 primitive evidence。M31 负责把碎 evidence 组织成可回放、可回退、可验证的 reconstruction units。

目标链路：

```text
source PNG + OCR text boxes + M29 primitive nodes
-> M31 reconstruction UI tree
-> reconstruction units with fallback crops
-> ownership/report/overlay
```

## Scope

包含：

- 新增 script-only M31 reconstruction tree 模块。
- 输入只读消费 source PNG、OCR JSON、M29 `nodes.json`。
- 输出 `m31_reconstruction_tree.json`、`m31_reconstruction_tree_report.json`、unit fallback crops，以及 development overlay。
- 每个 M29 primitive ref 必须归属到一个 reconstruction unit 或 review bucket。
- 每个 reconstruction unit 必须有 fallback crop。
- 新增 focused tests 和文档/ADR。

不包含：

- 不接 `/api/upload-m30-preview`。
- 不替换 M30 DSL。
- 不删除 M29.0.2-M29.0.5。
- 不把 M29.0.2/M29.0.3/M29.0.4/M29.0.5/M30 DSL 作为 M31 主输入。
- 不做 DSL materialization、Figma output、Auto Layout、Component/Instance、SVG/vectorization、fallback masking、text cover、icon recovery、semantic business classification、alpha matting。

## Steps

1. 新增 ADR `0049-build-reconstruction-ui-tree-from-m29-primitive-evidence.md`，固定 M31 是 M29 后的组织层。
2. 新增 `backend/app/reconstruction_ui_tree.py`，实现 OCR/M29 parsing、primitive refs、unit grouping、fallback crop、report 和 overlay。
3. 新增 `backend/scripts/run_m31_reconstruction_ui_tree.py`，支持 single 和 batch smoke。
4. 新增 `backend/tests/test_reconstruction_ui_tree.py`，覆盖 ownership、fallback、review bucket、repeated group、禁词和 profile 行为。
5. 更新 backend、architecture、DSL、testing strategy、glossary 和 docs index，明确 M31 不改变当前 M30 plugin runtime。

## Acceptance

- `m31_reconstruction_tree.json` 顶层 schema 为 `M31ReconstructionUiTree`。
- `m31_reconstruction_tree_report.json` 顶层 schema 为 `M31ReconstructionUiTreeReport`。
- 每个 M29 node 都生成 primitive ref。
- 每个 primitive ref 被 exactly one reconstruction unit 拥有，或进入 exactly one review bucket。
- root 下不直接挂 primitive leaf。
- 每个 reconstruction unit 都有 fallback crop。
- `createdDetectionBBoxCount = 0`。
- `permissionViolationCount = 0`。
- `rootLeafPrimitiveCount = 0`。
- `unitFallbackCoverage = 1.0`。
- `forbiddenHitCount = 0`。
- source M29 JSON 不被改写。
- M30 plugin upload path 不受影响。

## Validation

Focused:

```bash
cd backend
uv run pytest tests/test_reconstruction_ui_tree.py -q
```

Regression:

```bash
cd backend
uv run pytest \
  tests/test_reconstruction_ui_tree.py \
  tests/test_visual_primitive_graph.py \
  tests/test_m30_upload_pipeline.py \
  tests/test_evidence_grounded_dsl_materialization.py \
  tests/test_upload_flow.py -q
```

Full:

```bash
cd backend && uv run pytest -q
pnpm run check
git diff --check
git status --short
```

Manual smoke:

```bash
cd backend
uv run python scripts/run_m31_reconstruction_ui_tree.py \
  --source-image storage/uploads/{taskId}/original.png \
  --ocr-json storage/m30_1_uploads/{taskId}/ocr/ocr.json \
  --m29-nodes-json storage/m30_1_uploads/{taskId}/m29/nodes.json \
  --out storage/m31_runs/{taskId} \
  --profile development
```

## Notes

M31 借鉴 `uic` 的 source refs、evidence refs、parent/children tree 和 reconstruction core 思路，但不复制 semantic role enrichment、Codia adapter、preset-heavy 语义层，也不扩大 artifact surface。

后续路线：

```text
M31.1 attach M31 diagnostics to upload pipeline
M32 layer recovery plan
M33 unit-level recomposition validator
M34 DSL materializer from validated units
M35 remove obsolete M29.0.2-M29.0.5 object-refinement chain if M34 replaces them
```
