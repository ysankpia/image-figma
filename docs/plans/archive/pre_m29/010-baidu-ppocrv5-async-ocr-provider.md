# M10 Baidu PP-OCRv5 Async OCR Provider

- 状态：active
- 创建日期：2026-05-16
- 负责人：Codex

## Goal

把 M9 fake OCR 合同层升级为可选真实 OCR provider。M10 使用百度 AI Studio `PP-OCRv5` 异步 OCR API，把远端返回的 `rec_texts`、`rec_scores`、`rec_boxes` 和 `rec_polys` 标准化为 `OCRDocument v0.1`，再复用现有 DSL patch builder 生成 hidden `candidate_text`。

## Scope

包含：

- `OCR_PROVIDER=baidu_ppocrv5`。
- 百度异步 jobs API 提交、轮询和 JSONL 下载。
- PP-OCRv5 OCR 结果转内部 `[x, y, width, height]` bbox。
- 低置信度 OCR 过滤。
- OCR 失败降级，不影响 fallback DSL。
- 单元测试和文档同步。

不包含：

- 同步 OCR API。
- 本地 PaddleOCR/RapidOCR provider。
- PaddleOCR-VL 或 PP-StructureV3。
- 可见文字替换。
- 背景擦除、Auto Layout、组件化。

## Implementation

新增百度 OCR provider 后，上传链路保持：

```text
PNG
-> deterministic region fallback DSL
-> visual primitives
-> OCRDocument
-> DSL patch
-> enhanced DSL
```

默认仍是 `OCR_PROVIDER=fake`。只有显式设置 `OCR_PROVIDER=baidu_ppocrv5` 和 `BAIDU_PADDLE_OCR_TOKEN` 时才调用远端。

M10 只保存标准化 OCR JSON，不默认保存百度原始 JSONL。

## Acceptance

- fake OCR 默认路径不变。
- 百度 provider 成功时 `/api/tasks/{taskId}/ocr` 返回 `provider: "baidu_ppocrv5"` 和 `model: "PP-OCRv5"`。
- `/dsl` 中生成 hidden `candidate_text`，fallback region 和 `original_ref` 保留。
- 百度失败、缺 token、远端 failed、超时或 JSONL 异常时，上传仍 completed，`/dsl` 回退 fallback DSL。
- 真实 token 不写入仓库。

## Validation

自动验证：

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
```

手动 smoke：

```bash
cd backend
OCR_PROVIDER=baidu_ppocrv5 \
BAIDU_PADDLE_OCR_TOKEN=... \
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

上传主样例后确认：

- UI 显示 Rendered。
- Figma 可见画面仍是 fallback region。
- Layers 中出现 hidden OCR text candidates。
- `/api/tasks/{taskId}/ocr` 返回真实中文 OCR blocks。
