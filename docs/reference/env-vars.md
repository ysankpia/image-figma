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
| `M30_PREVIEW_PROFILE` | M30 preview artifact profile，支持 `production`、`development` | `production` | 否 |
| `OCR_TEXT_EDITABILITY_ENABLED` | 是否在 M30 materialization 前执行 text editability decision | `true` | 否 |
| `OCR_GRAPHIC_TEXT_PRESERVE_ENABLED` | 是否把旋转、媒体区、复杂背景等高风险文字保留在 fallback | `true` | 否 |
| `OCR_TEXT_SYMBOL_LEAKAGE_CLEANUP_ENABLED` | 是否在 M30 物化前清理高置信 leading text-symbol leakage | `true` | 否 |
| `OCR_MAX_ROTATION_ANGLE` | 允许物化为普通 text layer 的最大 OCR polygon 偏转角度 | `3.0` | 否 |
| `OCR_MAX_BACKGROUND_TEXTURE` | 图形文字 preserve 判定使用的背景纹理阈值 | `0.45` | 否 |
| `OCR_MAX_BACKGROUND_COLOR_COUNT` | 图形文字 preserve 判定使用的颜色数阈值 | `32` | 否 |
| `M30_SHAPE_ERASURE_ENABLED` | 是否从 fallback 图中擦除已物化 shape bbox | `true` | 否 |
| `M30_IMAGE_ERASURE_ENABLED` | 是否从 fallback 图中擦除已物化 image bbox | `true` | 否 |
| `M30_ACCEPTED_IMAGE_MATERIALIZATION_ENABLED` | 是否启用 M30.6 低文字重叠大 image asset 物化策略 | `true` | 否 |
| `M30_ACCEPTED_IMAGE_MAX_TEXT_OVERLAP` | M30.6 大 image asset 可接受的最大文字重叠比例 | `0.02` | 否 |
| `M30_ACCEPTED_IMAGE_MIN_AREA` | M30.6 大 image asset 可物化的最小 bbox 面积 | `20000` | 否 |
| `M30_IMAGE_ASSET_TEXT_ERASURE_ENABLED` | 是否从 M30 copied media asset 中擦除已物化 editable text bbox | `true` | 否 |
| `M30_COMPOSITE_MEDIA_MATERIALIZATION_ENABLED` | 是否把大面积 `partially_separated` composite media 物化为独立 image node | `true` | 否 |
| `M30_COMPOSITE_MEDIA_MIN_AREA` | M30.7 composite media 可物化的最小 bbox 面积 | `50000` | 否 |

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

`production` is the default plugin preview runtime. It keeps OCR JSON, structured M29/M29.0.x/M30 JSON, M29.0.5 formal visual assets needed by M30, M29 Direct artifacts when available, published renderer assets, M30 DSL/report, and `stage_timings.json`. It skips overlays, preview sheets, review/contact sheets, and M30 preview PNGs.

```bash
M30_PREVIEW_PROFILE=development
```

`development` keeps full diagnostics for local evidence debugging. This variable affects only `/api/upload-m30-preview`; single-stage M29/M30 scripts keep their own development defaults.

## OCR Text Editability

```bash
OCR_TEXT_EDITABILITY_ENABLED=true
OCR_GRAPHIC_TEXT_PRESERVE_ENABLED=true
OCR_TEXT_SYMBOL_LEAKAGE_CLEANUP_ENABLED=true
```

默认启用 M30 text editability decision。OCR text boxes 不会在 M29 前被删除；M30 根据现有 OCR/M29.0.2/M29.0.5 证据决定：

```text
editable_text
graphic_text_preserve_in_fallback
review_text
```

只有 `editable_text` 会生成 `m30_text_member` 并参与 fallback erasure。`graphic_text_preserve_in_fallback` 保留在 fallback 图像里，并出现在 M30 report 的 `preservedGraphicTextItems` 中。

`OCR_ARTISTIC_TEXT_FILTER_ENABLED` 是兼容旧 M34 配置的 alias：当未显式设置 `OCR_GRAPHIC_TEXT_PRESERVE_ENABLED` 时，它会影响 preserve 开关。它不再表示删除 OCR text boxes。

## M30 Accepted Image And Composite Media

```bash
M30_ACCEPTED_IMAGE_MATERIALIZATION_ENABLED=true
M30_ACCEPTED_IMAGE_MAX_TEXT_OVERLAP=0.02
M30_ACCEPTED_IMAGE_MIN_AREA=20000
M30_IMAGE_ASSET_TEXT_ERASURE_ENABLED=true
M30_COMPOSITE_MEDIA_MATERIALIZATION_ENABLED=true
M30_COMPOSITE_MEDIA_MIN_AREA=50000
```

M30.6 默认启用。它只影响 M30 内部 large accepted image asset policy：当 M29.0.5 已经产出 `assetUse=image_asset`，且文字重叠很低、面积足够大、没有高风险 text/boundary flags、并能通过 M29.0.4/M29.0.3 血统追溯回 raw M29 image node 时，M30 会把它物化成 `role=m30_visual_asset` 的 DSL image node。

M30.7 也在 M30 内部运行，不新增 runtime stage。`M30_IMAGE_ASSET_TEXT_ERASURE_ENABLED=true` 时，M30 只会修改自己复制到 `m30/assets/` 下的 media PNG：如果 editable `m30_text_member` 的 bbox 几乎完全落在 `m30_visual_asset` 或 `m30_composite_media_asset` 内部，就把该 bbox 在 copied image asset 中补成局部背景色，避免拖走上层文字后露出烘焙文字重影。原始 M29.0.5 asset 不会被修改。

`M30_COMPOSITE_MEDIA_MATERIALIZATION_ENABLED=true` 时，M30 会把大面积 `decision=partially_separated` 且有 `combinedAssetPath` 的 composite media 作为 `role=m30_composite_media_asset` image node 物化。它用于让轮播图/Banner 整块可选中、可拖动；第一版保留图内艺术标题烘焙在 raster 中，不做内部文字编辑。

## Removed Variables

这些变量不再是 active runtime configuration。不要把它们加回 `.env.local` 期待恢复旧链路：

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
M31_UPLOAD_DIAGNOSTICS_ENABLED
M31_UPLOAD_DIAGNOSTICS_STRICT
M38_HIERARCHY_MATERIALIZATION_ENABLED
M38_HIERARCHY_MATERIALIZATION_STRICT
M38_HIERARCHY_MAX_CONTAINERS
M39_CONTENT_CHROME_CLASSIFICATION_ENABLED
M39_ONNX_PROPOSER_ENABLED
M39_ONNX_MODEL_PATH
M39_1_UNIT_STRUCTURE_READINESS_ENABLED
M39_1_ONNX_UNIT_PROPOSER_ENABLED
M39_1_ONNX_MODEL_PATH
```

Historical meanings are available only in archived docs, completed plans, ADRs, and git history.
