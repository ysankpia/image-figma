# M34.1 Preserve Graphic Text Evidence And Editability Decision

- 状态：completed
- 创建日期：2026-05-20
- 完成日期：2026-05-20
- 负责人：Codex

## Goal

修正 M34 的错误抽象：OCR text block 是证据，不是已经批准的 Figma text layer。M34.1 保留全部 OCR/M29/M31 可审计证据，把“是否生成普通可编辑文字层”的判断后移到 M30 materialization。

正确链路是：

```text
OCR text evidence
-> M29/M31 evidence trace
-> M30 text editability decision
-> editable_text 生成 text layer
-> graphic_text_preserve_in_fallback 不生成 text layer、不擦 fallback
```

## Scope

包含：

- 保留 `OCRBlock.meta.angle` 和 `OCRBlock.meta.polygon`。
- 保留 `M29TextBox.meta`，并在 M29.0.2 `textBoxes` 中输出。
- 移除 upload pipeline 中 M29 前的 artistic text drop 行为。
- 在 M30 materialization 前新增 text editability decision。
- M30 report 输出 `textEditabilityDecisions`、`preservedGraphicTextItems`、`reviewTextItems` 和 summary 计数。
- `GET /api/tasks/{taskId}/m30-materialization` 返回这些只读诊断字段。
- 默认保守：图形化/媒体区/旋转/复杂背景文字保留在 fallback，不转普通 text layer。

不包含：

- 不做字体识别。
- 不做艺术字体重建。
- 不做 VLM 分类。
- 不做 inpainting。
- 不改 DSL schema。
- 不改 Renderer 或 Figma plugin UI。
- 不做 M32/M33/M34 主线重写。

## First Principles

PNG 是压扁后的最终渲染结果。OCR 的输出只说明“这里有文字证据”，不能说明“这里应该被擦掉并用系统字体重画”。

证据层的目标是保留事实；物化层的目标是选择可回放的 Figma layer。把图形化文字在 OCR 后直接删除，会导致两种信息损失：

- M29/M31 不再能审计原始文字位置和角度。
- 下游无法解释为什么某段文字没有进入 Figma text layer。

因此 M34.1 的边界是：不删除证据，只阻止高风险文字成为 editable text。

## Implementation

1. `backend/app/config.py`
   - 新增 `OCR_TEXT_EDITABILITY_ENABLED=true`。
   - 新增 `OCR_GRAPHIC_TEXT_PRESERVE_ENABLED=true`。
   - 旧 `OCR_ARTISTIC_TEXT_FILTER_ENABLED` 暂时作为 preserve alias 保留，但不再表示 drop OCR boxes。

2. `backend/app/m30_upload_pipeline.py`
   - 移除 `filter_artistic_text()` 的预过滤调用。
   - 全量 OCR text boxes 进入 M29、M31、M29.0.2。
   - 调用 M30 materialization 时传入 M29.0.2 text box metadata。

3. `backend/app/text_masked_media_audit.py`
   - `text_box_to_dict()` 输出 `meta`，让 OCR angle/polygon 可继续追踪。

4. `backend/app/evidence_grounded_dsl_materialization.py`
   - 新增 `M30TextEditabilityDecision`。
   - 新增 `classify_text_editability(...)`。
   - `append_text_nodes(...)` 只物化 `editable_text`。
   - `graphic_text_preserve_in_fallback` 和 `review_text` 进入 report/skipped，不生成 text node，也不会参与 fallback erasure。

5. `backend/app/routes/tasks.py`
   - M30 report endpoint 返回 text editability 诊断。

## Acceptance

- OCR polygon angle/meta 继续保留。
- 上传链路不再在 M29 前删除 OCR text boxes。
- 旋转 OCR text 仍可在 OCR/M29.0.2/M31 证据链中追踪。
- `graphic_text_preserve_in_fallback` 不生成 `m30_text_member`。
- `graphic_text_preserve_in_fallback` 不进入 fallback pixel erasure。
- 普通水平 UI text 仍生成 `m30_text_member`。
- M30 report 包含 editable/preserved/review 统计和原因计数。
- `createdNewBBoxCount` 仍为 `0`。
- M30 upload pipeline、M31 diagnostics、DSL endpoint 不受破坏。

## Validation

Focused validation:

```bash
cd backend
uv run pytest tests/test_baidu_ocr.py tests/test_evidence_grounded_dsl_materialization.py tests/test_m30_upload_pipeline.py tests/test_config_env.py -q
```

结果：

```text
45 passed
```

后续还需在阶段提交前跑：

```bash
cd backend && uv run pytest -q
pnpm run check
git diff --check
git status --short
```

## Notes

针对用户样本中的红色手写体和媒体区大字，MVP 默认策略是 preserve，不尝试普通字体重画。后续如果要恢复更高可编辑性，应进入单独阶段做 layer recovery / recomposition validation，而不是回到 OCR 前过滤。
