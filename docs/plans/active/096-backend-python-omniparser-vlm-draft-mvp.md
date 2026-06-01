# 096 Backend Python OmniParser + OCR + VLM Draft MVP

- 状态：active
- 创建日期：2026-06-01
- 分支：`feat/omniparser-vlm-pipeline`
- 负责人：Codex

## Goal

把 `services/backend-python` 重构为一条小而硬的 Draft MVP 链路：

```text
PNG
-> OCR text authority
-> OmniParser objectness candidates
-> VLM candidate classifier
-> deterministic promotion planner
-> Draft Runtime DSL + image assets
```

目标是生成可快速编辑、可辅助开发的 Figma Draft，不复刻 Codia，不追 Auto Layout，不使用 M29。

## First Principles

源图只有像素，没有原始 Figma tree。MVP 的正确目标不是恢复原始设计稿，而是降低编辑成本：

- OCR 是文字内容和文本 bbox 权威。
- OmniParser 只负责候选 bbox，不负责类别和最终 layer。
- VLM 只给候选分类建议，不生成 bbox、不生成文字、不生成 DSL。
- Deterministic planner 才能把候选晋升为 `text`、`image`、`shape`。

## Scope

包含：

- 保留现有 `/api/draft-preview` HTTP API。
- 重写 Python pipeline 的 merge/classification/promotion/asset 逻辑。
- 为 OCR、OmniParser、VLM、promotion、summary 写入 artifacts。
- 只为最终 image layer 裁 asset；shape 采样颜色，不裁图。
- 增加单元测试和 fake pipeline 测试。

不包含：

- 不接 M29。
- 不恢复 Codia generation route。
- 不读取 Codia golden 作为 runtime hint。
- 不按样本名、文案、固定坐标、固定 bbox、固定屏幕尺寸写规则。
- 不做 Auto Layout、组件、设计系统、原始 Figma tree 还原。

## Acceptance

- `cd services/backend-python && uv run pytest -q` 通过。
- `python -m py_compile app/*.py` 通过。
- Draft Runtime DSL 中 image asset ref 全部可解析。
- OCR text 不被 VLM 改写。
- Shape 不写 asset。
- VLM/provider/OCR/OmniParser 失败有 artifact，pipeline 不因可降级 provider 失败崩溃。
- 四图 smoke 产出 summary，能看到 text/image/shape/suppress 计数和 provider 错误计数。
