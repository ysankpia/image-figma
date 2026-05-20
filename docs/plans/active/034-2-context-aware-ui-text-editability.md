# M34.2 Context-Aware UI Text Editability

- 状态：in_progress
- 创建日期：2026-05-20
- 负责人：Codex

## Goal

M34.1 把 OCR evidence 和 Figma text materialization decision 拆开，这是正确边界。但当前 M30 editability policy 仍把单个 OCR angle 和 visual overlap 当成强证据，导致普通 UI 文本被误判为 `graphic_text_preserve_in_fallback`。

M34.2 的目标是在不引入业务词和固定坐标的前提下，为 M30 text editability 增加通用几何反证：

```text
aligned_text_row
compact_overlay_badge
metadata_text_cluster
stable_local_background
```

## Scope

包含：

- 保留 M34.1 的 OCR/M29/M31 evidence preservation。
- 在 `classify_text_editability(...)` 内新增 text member 和 visual asset 几何上下文。
- 对 preserve signals 和 editable counter signals 分别记录到 report metrics。
- 允许上下文反证覆盖弱 preserve signal。
- 继续保护强图形字风险，不把艺术字普通 text 化。

不包含：

- 不做业务词特化。
- 不做固定坐标或固定分辨率阈值。
- 不做字体识别、手写体还原、VLM 分类或 inpainting。
- 不改 OCR、M29、M31、DSL schema、Renderer、Figma plugin UI。
- 不做 icon / pin 独立图层恢复。

## First Principles

OCR 的 `angle` 是测量结果，不是设计意图。截图中的子像素抗锯齿、背景纹理和 OCR polygon 抖动，会让水平 UI text 带上几度噪声。单个 box 的角度必须服从更强的组群几何共识。

同理，文字完全落在图片内只说明坐标包含关系，不说明它是照片里的不可编辑文字。UI 常把短文本叠在图片边缘形成 badge、时长、计数和元数据。正确判断应来自相对面积、边缘位置、局部稳定性和相邻结构，而不是图片 overlap 本身。

## Implementation

1. `backend/app/evidence_grounded_dsl_materialization.py`
   - 构建 `TextEditabilityContext`，包含全部 text member items、visual asset boxes、image area。
   - `build_text_editability_metrics(...)` 增加 `preserveSignals` 和 `editableCounterSignals`。
   - 新增通用几何 helpers：
     - `find_aligned_text_row_signal(...)`
     - `find_compact_overlay_badge_signal(...)`
     - `find_metadata_text_cluster_signal(...)`
     - `is_stable_local_background(...)`
   - 决策先收集 preserve signals，再用 counter signals 覆盖弱 preserve。

2. Report semantics
   - 最终 `reasons` 仍表示实际 decision 的原因。
   - `metrics.preserveSignals` 记录触发过的负证据。
   - `metrics.editableCounterSignals` 记录触发过的上下文反证。

3. Documentation
   - 更新 backend、architecture、observability、testing strategy、env vars 和 docs index。
   - 新增 ADR 0053。

## Acceptance

- 轻微 OCR angle noise 的 aligned text row 可成为 `editable_text`。
- 图片边缘小型 overlay badge text 可成为 `editable_text`。
- 紧凑 metadata cluster text 可成为 `editable_text`。
- 大型媒体区/复杂背景/高视觉风格损失文字继续 preserve。
- preserved graphic text 仍不生成 `m30_text_member`，也不参与 fallback erasure。
- report 可同时审计 preserve signals 和 editable counter signals。
- 禁止业务特化词出现在 schema、reason、测试或文档规则中。

## Validation

Focused:

```bash
cd backend
uv run pytest tests/test_evidence_grounded_dsl_materialization.py -q
```

Regression:

```bash
cd backend
uv run pytest \
  tests/test_baidu_ocr.py \
  tests/test_evidence_grounded_dsl_materialization.py \
  tests/test_m30_upload_pipeline.py \
  tests/test_config_env.py -q
```

Full:

```bash
cd backend && uv run pytest -q
pnpm run check
git diff --check
git status --short
```
