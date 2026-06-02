# 107 PSD-like Python Figma Plugin Integration

- 状态：completed
- 日期：2026-06-02
- 范围：`figma-plugin`、`services/psdlike-python`

## Summary

本阶段把 Figma plugin 的 Draft 生成入口接到当前可用的 PSD-like Python service：

```text
Figma Plugin
-> services/psdlike-python POST /api/draft-preview
-> GET /api/draft-preview/{taskId}/dsl
-> image-to-figma-renderer
-> editable Figma draft
```

这不是算法阶段。本阶段不改 PSD-like OCR、ownership、model evidence 或 renderer ownership 行为。

## Implemented Changes

- Plugin API 默认后端改为：
  ```text
  http://127.0.0.1:8010/api
  ```
- PNG upload multipart field 改为 `image`，匹配 `services/psdlike-python`。
- Plugin API client 兼容：
  ```text
  envelope success response
  direct psdlike-python response
  pure Draft Runtime DSL JSON
  envelope {data:{dsl}} DSL response
  ```
- Plugin upload 流程兼容同步完成：
  ```text
  upload.status == completed -> skip poll
  otherwise -> poll task endpoint
  ```
- Plugin success UI 显示 PSD-like diagnostics：
  ```text
  OCR provider/cache/text count
  Text/Raster/Shape layer counts
  missingAssetCount
  ```
- Figma manifest 开发域名增加：
  ```text
  http://localhost:8010
  http://127.0.0.1:8010
  ```
  正式 `allowedDomains` 仍保持 `["none"]`。
- `services/psdlike-python` 增加本地开发 CORS，允许 Figma 调用本地服务。

## Validation Evidence

Static and unit:

```text
pnpm --filter @image-figma/figma-plugin run typecheck: passed
pnpm --filter @image-figma/figma-plugin run test: 8 passed
pnpm --filter @image-figma/figma-plugin run build: passed, bundle scan passed
pnpm --filter @image-figma/image-to-figma-renderer run typecheck: passed
pnpm --filter @image-figma/image-to-figma-renderer run test: 18 passed
cd services/psdlike-python && python -m py_compile $(find app tools -name '*.py' | sort): passed
cd services/psdlike-python && uv run pytest -q: 15 passed
```

API smoke:

```text
server: OCR_PROVIDER=baidu_ppocrv5 uv run uvicorn app.main:app --host 127.0.0.1 --port 8010
POST /api/draft-preview with PNG field image: completed
taskId: a135fc0ab8b041e98679e72680b8e73e
ocrProvider: baidu_ppocrv5
ocrCacheHit: true
ocrTextCount: 29
textLayerCount: 27
rasterLayerCount: 36
shapeLayerCount: 26
missingAssetCount: 0
fullPageVisibleRaster: 0
shapeAssetCount: 0
GET /api/draft-preview/{taskId}/dsl: pure Draft Runtime DSL JSON
DSL kind/version: draft_runtime / 1.0
root children: 89
asset count: 36
GET /api/draft-preview/{taskId}/assets/raster_0001.png: PNG 144x32 RGBA served
```

## Notes

- `services/backend-go` remains untouched in this stage.
- Old `backend` and `services/backend-python` remain reference-only.
- Model semantic evidence remains metadata-only unless a later phase explicitly implements local physical re-search.
