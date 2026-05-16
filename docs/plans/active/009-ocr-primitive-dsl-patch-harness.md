# M9 OCR + Visual Primitive -> DSL Patch Harness

- 状态：completed
- 创建日期：2026-05-16
- 负责人：Codex

## Goal

在 M8 visual primitive contract 后面补上 DSL patch 合同层。OCR boxes 和 visual primitives 只能生成可验证 patch，不能直接成为最终 DSL 权威。

M9 默认 `debug` 模式会把 hidden OCR text candidates 合并进 `/api/tasks/{taskId}/dsl`，但不改变插件协议、不改变 Renderer、不做可见文字替换。

## Scope

包含：

- `OCRDocument v0.1` 合同。
- 默认 fake OCR provider。
- `DSLPatchDocument v0.1` 合同。
- `DSL_PATCH_MODE=off|debug|apply`，默认 `debug`。
- OCR 和 patch JSON 持久化。
- SQLite `ocr_results` 和 `dsl_patch_results`。
- `GET /api/tasks/{taskId}/ocr`。
- `GET /api/tasks/{taskId}/dsl-patch`。
- hidden `candidate_text` 合并进 enhanced DSL。
- Python enhanced DSL 结构断言和失败回退。

不包含：

- 真实 OCR provider。
- AI 直接生成 DSL 或 patch。
- 可见文字替换。
- 背景擦除。
- Auto Layout。
- 组件化。
- 插件 UI/Main 改动。
- Renderer 改动。

## Behavior

上传链路：

```text
POST /api/upload
-> M7 deterministic region fallback DSL
-> M8 visual primitive candidates
-> M9 fake OCR boxes
-> M9 DSL patch builder
-> enhanced DSL with hidden text candidates
-> task completed
```

默认 `/api/tasks/{taskId}/dsl` 返回 enhanced DSL：

- 保留 `original_ref`。
- 保留 `fallback_region_header/content/bottom` 或 `fallback_full_image`。
- 增加 hidden `candidate_text` 元素。
- `style.visible` 固定为 `false`，避免双层文字。
- `meta.qualityFlags` 追加 `m9_hidden_text_candidates`。

如果 `DSL_PATCH_MODE=off`，`/dsl` 返回 M7 base DSL，不合并 patch。

如果 patch build 或 validation 失败，`/dsl` 回退 base DSL，失败写入 `error_logs` 和 `dsl_patch_results`。

## Validation

自动验证：

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
```

当前自动测试覆盖：

- 默认 fake OCR 上传成功。
- OCR JSON 和 patch JSON 落盘。
- OCR 和 patch 查询接口。
- `DSL_PATCH_MODE=off` 回退 base DSL。
- `DSL_PATCH_MODE=debug` 返回 hidden text candidates。
- fallback region 不被删除。
- OCR 空文本、越界 bbox、重复 id 被处理。
- patch 后 element id 唯一。
- enhanced DSL 结构断言。
- M8 primitives 继续可查询。

## Evidence

已验证：

```text
cd backend && uv run pytest
34 passed
```

