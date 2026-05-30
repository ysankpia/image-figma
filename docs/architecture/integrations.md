# 外部集成

集成必须少而直接。当前 Codia Beta 路径依赖 Figma Plugin API、本地 Go `codiaserver`、可选 OCR provider、可选 OpenAI-compatible UI detector、本地文件存储和 DSL v0.2 Renderer。Python/FastAPI `/api/upload-preview` 是保留的 DSL v0.1 preview 路径，不是 Codia Beta 输出质量调试入口。

## Figma

Figma Plugin API 用于：

- 接收插件 UI 消息。
- 上传 PNG 到 Go Codia Beta 后端或保留的 Python preview 后端。
- 获取 task 状态和正式 DSL。
- 创建 root Frame。
- 创建文本、形状、图片和线条。
- 设置节点位置和样式。
- 将生成结果放到当前页面。

Renderer 只通过 Figma Plugin API 写图层，不调用后端。

## OCR

OCR is a source-evidence provider for M29:

```text
PNG -> text boxes -> M29 ownership evidence -> M29 plan-driven text nodes
```

Current providers:

```text
fake
baidu_ppocrv5
```

OCR output must include:

```text
text
bbox
confidence
lineId
blockId
```

When `OCR_PROVIDER=baidu_ppocrv5`, the token is supplied through `BAIDU_PADDLE_OCR_TOKEN`. Real tokens must never be committed.

In the M29 preview path, OCR failure fails the task. This preserves the evidence contract instead of falling back to a misleading completed DSL.

## Go Codia Beta

Go Codia Beta 是当前 `Generate Beta` 后端：

```text
services/backend-go/cmd/codiaserver
POST /api/codia-preview
GET /api/codia-preview/{taskId}/dsl
GET /api/codia-preview/{taskId}/assets/{assetId}.png
```

它负责 OCR、Go M29 physical evidence、可选 UI detector、assembly/control/tree/emitter、DSL v0.2 export 和 crop assets。调试 Codia Beta 输出质量时，先看：

```text
services/backend-go/storage/codia_server/codia_previews/{taskId}/compile/
```

## Python M29 Preview

Python M29 preview is a retained local app-layer module chain, not an external service.

It produces structured JSON evidence under:

```text
storage/upload_previews/{taskId}/
```

Python M29 plan-driven materializer emits DSL v0.1 for `/api/upload-preview`. It does not emit Codia Beta DSL v0.2 and should not be patched for Codia Beta assembly/tree defects.

## Storage

Development uses local filesystem storage.

Python M29 image assets are published under:

```text
storage/assets/{taskId}/m29/
/files/assets/{taskId}/m29/...
```

Go Codia Beta image assets are published under:

```text
services/backend-go/storage/codia_server/codia_previews/{taskId}/compile/assets/
/api/codia-preview/{taskId}/assets/{assetId}.png
```

Future object storage or signed URLs are out of scope for v0.1.

## Removed Integrations

The removed pre-M29 backend chain used old visual primitive, patch, text replacement, component, slice, icon, perception, and SAM harnesses. M29 Direct compare, legacy M30 product materializer, and M31-M39 downstream experiments are also no longer active upload integrations. Historical details remain in ADRs and `docs/reference/legacy/`.
