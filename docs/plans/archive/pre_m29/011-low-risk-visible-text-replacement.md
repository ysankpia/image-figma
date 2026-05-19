# M11 Low-risk Visible Text Replacement

- 状态：active
- 创建日期：2026-05-16
- 负责人：Codex

## Summary

M11 在 M10 真实 OCR 合同后增加低风险可见文字替换 harness。默认 `TEXT_REPLACEMENT_MODE=debug` 只生成 accepted/rejected decisions，不改变 Figma 可见输出。显式设置 `TEXT_REPLACEMENT_MODE=apply` 时，只把浅色纯色背景上的高置信 OCR block 合并为 cover shape + visible text。

M11 不做完整可编辑还原，不删除 fallback region，不改 Figma 插件 UI/Main，不接新 OCR/AI provider。

## Key Changes

- 新增 `TextReplacementDocument v0.1`，保存到 `backend/storage/text_replacements/{taskId}.json`。
- 新增 SQLite `text_replacement_results`，记录 mode、status、accepted/rejected count 和文件路径。
- 新增 `GET /api/tasks/{taskId}/text-replacements` 调试接口。
- 新增 PNG pixel decoder/background sampler，复用标准库 PNG unfilter 逻辑。
- 新增 `TEXT_REPLACEMENT_MODE=off|debug|apply` 和低风险筛选阈值环境变量。
- `apply` 模式追加 `text_replacement_cover` shape 和 `visible_text_replacement` text，仍保留 original ref、fallback regions 和 hidden candidate text。

## Test Plan

必须通过：

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
```

覆盖点：

- debug 模式生成 replacement document，但 `/dsl` 不含 visible replacement。
- apply 模式保留 fallback/original/candidate text，同时新增 cover/text replacement。
- low confidence、status bar、小 bbox、大 bbox、复杂背景、深色背景、超过 max blocks 都被拒绝并给出稳定 reason。
- unsupported PNG sampling 和 validation failed 不影响 upload completed。
- text replacement endpoint 的成功、TASK_NOT_FOUND、TEXT_REPLACEMENT_NOT_FOUND。

## Assumptions

- 默认 `TEXT_REPLACEMENT_MODE=debug`。
- 只接受浅色纯色背景，深色按钮和复杂背景留到后续阶段。
- 不新增 Pillow/OpenCV/PaddleOCR/RapidOCR。
- 不改插件协议和 Renderer。
