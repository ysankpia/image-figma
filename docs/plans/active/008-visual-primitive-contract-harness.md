# M8 Visual Primitive Contract Harness

- 状态：completed
- 创建日期：2026-05-16
- 负责人：Codex

## Goal

把《Thinking with Visual Primitives》这类视觉基元范式落成工程合同：AI/OCR 只能提出可验证的候选 visual primitives，不能直接成为 DSL 权威。

M8 不改变插件和 Figma 输出。上传链路仍返回 M7 deterministic region fallback DSL，新增的是 primitive JSON 持久化和只读查询接口，为 M9 做 OCR boxes + visual primitives 合并打地基。

## Scope

包含：

- `VisualPrimitiveDocument v0.1` 合同。
- 默认 `fake` provider。
- 可选 `openai` provider。
- primitive JSON 文件持久化。
- SQLite `primitive_results` 索引表。
- `GET /api/tasks/{taskId}/primitives` 查询接口。
- primitive bbox validator。
- OpenAI structured JSON output 的最小 provider 边界。
- 后端测试覆盖 fake、OpenAI 错误降级、bbox 转换和 API。

不包含：

- OCR。
- 可编辑文字生成。
- Auto Layout。
- 组件化。
- primitives 合并进 DSL。
- 插件 UI/Main 改动。
- Figma 输出变化。

## Contract

primitive document 固定为：

```json
{
  "version": "0.1",
  "taskId": "task_xxx",
  "provider": "fake",
  "model": null,
  "imageSize": { "width": 941, "height": 1672 },
  "coordinateSpace": "pixel",
  "primitives": [],
  "relations": [],
  "warnings": [],
  "meta": {
    "notes": "visual_primitive_contract_harness"
  },
  "status": "completed"
}
```

坐标规则：

- `bbox` 一律是整图像素坐标 `[x, y, width, height]`。
- OpenAI provider 的 region-local normalized box `[x1, y1, x2, y2]` 必须先转换成整图像素 bbox。
- bbox 轻微越界会 clamp 并记录 warning。
- 严重非法 bbox 会被丢弃。
- 重复 primitive id 会被丢弃。
- relation 引用不存在 primitive 会被丢弃。

v0.1 允许的 `kind`：

```text
region
card
button_background
image
icon
shape
divider
text_block
unknown
```

## Pipeline

上传链路现在是：

```text
POST /api/upload
-> PNG metadata
-> M7 region slicer
-> M7 deterministic DSL
-> M8 primitive extraction
-> save DSL JSON
-> save primitive JSON
-> task completed
```

primitive extraction 失败不影响 DSL：

- 上传仍可 `completed`。
- `/api/tasks/{taskId}/dsl` 仍返回 M7 DSL。
- `/api/tasks/{taskId}/primitives` 返回 `status: failed` 和错误摘要。
- 失败写入 `error_logs`，错误码为 `PRIMITIVE_EXTRACTION_FAILED`。

## Providers

默认：

```text
VISUAL_PRIMITIVE_PROVIDER=fake
```

Fake provider 根据 M7 region 生成：

```text
vp_region_header
vp_region_content
vp_region_bottom
```

如果 M7 退回整图 fallback，则生成：

```text
vp_region_full_image
```

OpenAI provider 仅在显式配置时启用：

```bash
VISUAL_PRIMITIVE_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_VISION_MODEL=gpt-5.5
```

OpenAI provider 只分析 region PNG，最多 3 个 region。模型被要求输出结构化 JSON，不输出 DSL，不抄写完整文字。

## Acceptance

- 默认无 `OPENAI_API_KEY` 时上传仍 completed。
- 上传后生成 `backend/storage/primitives/{taskId}.json`。
- `primitive_results` 写入 provider、status、primitive count、primitive path。
- `GET /api/tasks/{taskId}/primitives` 返回 fake primitives。
- M7 DSL 不包含 `vp_*` 节点。
- OpenAI provider 缺 key、异常、空结果不影响上传和 DSL 查询。
- normalized `0..999` bbox 能转换为整图像素 bbox。
- bbox 越界 clamp 并记录 warning。
- 严重非法 bbox、重复 id、无效 relation 不进入结果。

## Validation

自动验证：

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
```

可选 OpenAI smoke：

```bash
cd backend
VISUAL_PRIMITIVE_PROVIDER=openai \
OPENAI_API_KEY=... \
OPENAI_VISION_MODEL=gpt-5.5 \
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

然后上传主样例，并查询：

```bash
curl http://localhost:8000/api/tasks/{taskId}/primitives
```

## Evidence

当前自动测试覆盖：

- fake provider 默认启用。
- primitive JSON 文件落盘。
- primitives endpoint 成功返回。
- task 缺失和 primitive result 缺失错误。
- M7 DSL 不被 primitives 污染。
- normalized box 转 pixel bbox。
- primitive bbox clamp 和 out-of-bounds 丢弃。
- duplicate primitive id 和 invalid relation 丢弃。
- OpenAI 缺 key、region 异常、结构化 payload normalize。

已验证命令：

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
```

验证结果：

- 后端 pytest：`26 passed`。
- 根检查：DSL Schema、Renderer、Figma 插件 typecheck/build/test 全部通过。
- Figma 插件 bundle compatibility scan 通过。
