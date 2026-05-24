# 外部集成

v0.1 集成必须少而直接。当前产品路径只依赖 Figma Plugin API、本地 FastAPI、可选 OCR provider、本地文件存储和 DSL Renderer。

## Figma

Figma Plugin API 用于：

- 接收插件 UI 消息。
- 上传 PNG 到后端。
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

## M29

M29 is a local app-layer module chain, not an external service.

It produces structured JSON evidence under:

```text
storage/m30_1_uploads/{taskId}/
```

M29 plan-driven materializer is the only current layer that emits the DSL consumed by the plugin renderer.

## Storage

Development uses local filesystem storage.

M29 image assets are published under:

```text
storage/assets/{taskId}/m29/
/files/assets/{taskId}/m29/...
```

Future object storage or signed URLs are out of scope for v0.1.

## Removed Integrations

The removed pre-M29 backend chain used old visual primitive, patch, text replacement, component, slice, icon, perception, and SAM harnesses. M29 Direct compare, legacy M30 product materializer, and M31-M39 downstream experiments are also no longer active upload integrations. Historical details remain in ADRs and `docs/reference/legacy/`.
