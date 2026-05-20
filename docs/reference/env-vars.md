# 环境变量

后端有本地默认值，不需要 `.env` 才能启动。`.env.local` 会在默认情况下被加载；设置 `IMAGE_FIGMA_LOAD_LOCAL_ENV=false` 可关闭本地 env 文件加载。

## Current Variables

| 名称 | 用途 | 默认值 | 是否必需 |
| --- | --- | --- | --- |
| `API_BASE_URL` | 插件调用后端 API | `http://localhost:8000/api` | 否 |
| `PUBLIC_BASE_URL` | 后端生成 `/files/...` URL | `http://localhost:8000` | 否 |
| `CORS_ALLOW_ORIGINS` | 允许调用后端的 Origin，逗号分隔 | `*` | 否 |
| `STORAGE_ROOT` | 本地文件存储根目录 | `backend/storage` | 否 |
| `DATABASE_PATH` | SQLite 数据库路径 | `backend/storage/app.db` | 否 |
| `MAX_UPLOAD_BYTES` | PNG 上传大小上限 | `10485760` | 否 |
| `IMAGE_FIGMA_LOAD_LOCAL_ENV` | 是否加载仓库根目录 `.env.local` | `true` | 否 |
| `OCR_PROVIDER` | OCR provider，支持 `fake`、`baidu_ppocrv5` | `fake` | 否 |
| `OCR_MIN_CONFIDENCE` | OCR block 最低置信度 | `0.70` | 否 |
| `BAIDU_PADDLE_OCR_TOKEN` | 百度 AI Studio OCR bearer token | 无 | 仅 `OCR_PROVIDER=baidu_ppocrv5` 时需要 |
| `BAIDU_PADDLE_OCR_JOB_URL` | 百度 AI Studio OCR jobs endpoint | `https://paddleocr.aistudio-app.com/api/v2/ocr/jobs` | 否 |
| `BAIDU_PADDLE_OCR_MODEL` | 百度 OCR 模型 | `PP-OCRv5` | 否 |
| `BAIDU_PADDLE_OCR_POLL_INTERVAL_SECONDS` | 百度异步 OCR 轮询间隔秒数 | `5` | 否 |
| `BAIDU_PADDLE_OCR_TIMEOUT_SECONDS` | 百度异步 OCR 单任务超时秒数 | `120` | 否 |
| `M30_PREVIEW_PROFILE` | M30.1 插件 preview artifact profile，支持 `production`、`development` | `production` | 否 |
| `M31_UPLOAD_DIAGNOSTICS_ENABLED` | 是否在 `/api/upload-m30-preview` 后台链路中生成 M31 reconstruction diagnostics | `true` | 否 |
| `M31_UPLOAD_DIAGNOSTICS_STRICT` | M31 diagnostics 失败是否阻断 task completed | `false` | 否 |
| `OCR_TEXT_EDITABILITY_ENABLED` | 是否在 M30 materialization 前执行 text editability decision | `true` | 否 |
| `OCR_GRAPHIC_TEXT_PRESERVE_ENABLED` | 是否把旋转、媒体区、复杂背景等高风险文字保留在 fallback 而不是物化成普通 text layer | `true` | 否 |
| `OCR_TEXT_SYMBOL_LEAKAGE_CLEANUP_ENABLED` | 是否在 M30 物化前清理高置信 leading text-symbol leakage | `true` | 否 |
| `OCR_MAX_ROTATION_ANGLE` | 允许物化为普通 text layer 的最大 OCR polygon 偏转角度 | `3.0` | 否 |
| `OCR_MAX_BACKGROUND_TEXTURE` | 图形文字 preserve 判定使用的背景纹理阈值 | `0.45` | 否 |
| `OCR_MAX_BACKGROUND_COLOR_COUNT` | 图形文字 preserve 判定使用的颜色数阈值 | `32` | 否 |
| `M30_SHAPE_ERASURE_ENABLED` | 是否从 fallback 图中擦除已物化 shape bbox | `true` | 否 |
| `M30_IMAGE_ERASURE_ENABLED` | 是否从 fallback 图中擦除已物化 image bbox | `true` | 否 |

## OCR

Default local provider:

```bash
OCR_PROVIDER=fake
```

Baidu PP-OCRv5 async provider:

```bash
OCR_PROVIDER=baidu_ppocrv5
BAIDU_PADDLE_OCR_TOKEN=...
```

`BAIDU_PADDLE_OCR_TOKEN` must be supplied through local environment or an untracked env file. Do not commit real tokens.

## M30 Preview Profile

```bash
M30_PREVIEW_PROFILE=production
```

`production` is the default plugin preview runtime. It keeps OCR JSON, structured M29/M30 JSON, M29.0.5 formal visual assets needed by M30, published renderer assets, M30 DSL/report, and `stage_timings.json`. It skips overlays, preview sheets, review/contact sheets, and M30 preview PNGs.

```bash
M30_PREVIEW_PROFILE=development
```

`development` keeps full diagnostics for local evidence debugging. This variable affects only `/api/upload-m30-preview`; single-stage M29/M30 scripts keep their own development defaults.

## M31 Upload Diagnostics

```bash
M31_UPLOAD_DIAGNOSTICS_ENABLED=true
```

默认每次 `/api/upload-m30-preview` 都在 M29 后生成 M31 reconstruction tree/report。M31 只消费 source PNG、OCR JSON/document 和 M29 `nodes.json`/document，不读取 M29.0.x 或 M30 DSL 作为结构事实来源。

```bash
M31_UPLOAD_DIAGNOSTICS_ENABLED=false
```

关闭后不生成 `storage/m30_1_uploads/{taskId}/m31/`，`GET /api/tasks/{taskId}/m31-reconstruction` 返回 `M31_RECONSTRUCTION_NOT_FOUND`。

```bash
M31_UPLOAD_DIAGNOSTICS_STRICT=false
```

默认非阻塞：M31 失败只写 `stage_timings.json` 和 `error_logs`，M30 DSL 继续生成。

```bash
M31_UPLOAD_DIAGNOSTICS_STRICT=true
```

开发验收模式：M31 失败会让 task failed，stage 为 `m31_reconstruction`。

## OCR Text Editability

```bash
OCR_TEXT_EDITABILITY_ENABLED=true
OCR_GRAPHIC_TEXT_PRESERVE_ENABLED=true
OCR_TEXT_SYMBOL_LEAKAGE_CLEANUP_ENABLED=true
```

默认启用 M34.1 文本可编辑性决策。OCR text boxes 不会在 M29 前被删除；M30 根据现有 OCR/M29.0.2/M29.0.5 证据决定：

```text
editable_text
graphic_text_preserve_in_fallback
review_text
```

只有 `editable_text` 会生成 `m30_text_member` 并参与 fallback erasure。`graphic_text_preserve_in_fallback` 保留在 fallback 图像里，并出现在 M30 report 的 `preservedGraphicTextItems` 中。

M34.2 后，M30 会把弱 preserve signal 和通用几何 counter signal 一起记录到 report：

```text
metrics.preserveSignals
metrics.editableCounterSignals
```

这些 counter signal 只来自相对几何和局部像素，例如 aligned text row、compact overlay badge、metadata cluster 和 stable local background；不会使用业务词或固定屏幕坐标。

M34.3 默认启用 text-symbol leakage cleanup。它只在 M30 物化 editable text 前运行，第一版自动清理高置信 leading uppercase `Q` 泄漏，并且必须有源像素投影间隙证据。OCR JSON、M29 nodes、M31 tree 和 Renderer 合同都不改变。

M36 text foreground color sampling 是 M30 materialization 的默认行为，没有单独环境变量。它只影响已物化的 editable `m30_text_member`，不会重画 preserved graphic text。

M37 hierarchy readiness 是 M31/M30 产物存在时生成的诊断阶段，没有单独环境变量。它不改变 `/api/tasks/{taskId}/dsl`。

`OCR_ARTISTIC_TEXT_FILTER_ENABLED` 是兼容旧 M34 配置的 alias：当未显式设置 `OCR_GRAPHIC_TEXT_PRESERVE_ENABLED` 时，它会影响 preserve 开关。它不再表示删除 OCR text boxes。

## Removed Variables

M30.2.2 removed the frozen pre-M29 backend chain. These variables are no longer active runtime configuration:

```text
LEGACY_PRE_M29_UPLOAD_ENABLED
VISUAL_PRIMITIVE_PROVIDER
DSL_PATCH_MODE
TEXT_REPLACEMENT_MODE
TEXT_BINDING_ENABLED
COMPONENT_STRUCTURE_ENABLED
COMPONENT_ANNOTATION_ENABLED
LAYER_SEPARATION_ENABLED
ASSET_SLICE_ENABLED
ICON_CANDIDATE_ENABLED
ICON_COVERAGE_AUDIT_ENABLED
ICON_GAP_CANDIDATE_ENABLED
ICON_PLACEMENT_PLAN_ENABLED
ICON_VISIBLE_FALLBACK_ENABLED
ICON_BUSINESS_CANDIDATE_ENABLED
PERCEPTION_BENCHMARK_ENABLED
SAM_VISUAL_CANDIDATE_ENABLED
OPENAI_API_KEY
OPENAI_VISION_MODEL
```

Historical meanings are available only in archived docs and git history.
