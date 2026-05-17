# 本地设置

当前仓库已经初始化最小 monorepo，并实现了 `@image-figma/dsl-schema`、`@image-figma/image-to-figma-renderer`、Figma 插件最小 UI、FastAPI 后端、deterministic region fallback 上传链路、M8 visual primitive contract harness、M9 OCR/DSL patch harness、M10 百度 PP-OCRv5 异步 OCR provider、M11 低风险可见文字替换 harness、M12 文字替换覆盖率扩展、M13 text replacement 质量控制、M14 UI-aware sampling、M15 text-primitive binding、M16 component structure、M17 component annotation/layer naming、M18 layer separation candidate、M19 local asset slice/simple fill experiment harness、M20 icon candidate extraction/crop harness、M21 icon coverage audit/placement readiness harness、M22 region-guided icon gap candidate harness、M23 icon placement plan/layering readiness harness、M24 visible icon fallback replay experiment harness 和 M25 region-guided business icon candidate harness、M26 visual perception provider benchmark harness。

## Prerequisites

需要：

- Node.js 24.x。当前开发机使用 Homebrew `node@24`。
- pnpm 10.33.2。
- Python 3.12.7，由 asdf 管理。
- Git。

`.tool-versions` 当前只固定：

```text
python 3.12.7
```

本机 asdf 当前没有 nodejs 插件，所以本轮不把 Node 写入 `.tool-versions`。

## Run Locally

安装依赖：

```bash
pnpm install
```

运行全部当前检查：

```bash
pnpm run check
```

只检查 DSL Schema 包：

```bash
pnpm --filter @image-figma/dsl-schema run typecheck
pnpm --filter @image-figma/dsl-schema run test
```

只检查 Renderer 包：

```bash
pnpm --filter @image-figma/image-to-figma-renderer run typecheck
pnpm --filter @image-figma/image-to-figma-renderer run test
```

安装后端依赖：

```bash
cd backend
uv sync
```

运行后端测试：

```bash
cd backend
uv run pytest
```

启动后端：

```bash
cd backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

构建 Figma 插件：

```bash
pnpm --filter @image-figma/figma-plugin run build
```

只构建底层 dev harness：

```bash
pnpm --filter @image-figma/figma-plugin run build:dev
```

在 Figma 中验证：

1. 打开 Figma。
2. 进入插件开发模式。
3. 加载 `figma-plugin/manifest.json`。
4. 运行 `Image-to-Figma Design`。
5. 插件应打开 `420 x 560` 工具面板。
6. 启动后端：`cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`。
7. 选择一个 PNG。
8. 点击 `Generate from PNG`。
9. 当前页面应生成尺寸等于 PNG 的 `uploaded_png` root Frame。
10. Layers 中应出现 hidden `Original PNG Reference` 和可见 region fallback。
11. UI 应显示生成节点数和 warning 数。

当前 M5 插件主链路会调用 `http://localhost:8000/api`。`Sample` 按钮保留为开发备用入口，不调用后端。

M8 primitive extraction 默认使用 fake provider，不需要 OpenAI key：

```bash
VISUAL_PRIMITIVE_PROVIDER=fake
```

上传后可以查询 primitive candidates：

```bash
curl http://localhost:8000/api/tasks/{taskId}/primitives
```

OpenAI provider 只用于可选 smoke，必须显式启用：

```bash
cd backend
VISUAL_PRIMITIVE_PROVIDER=openai \
OPENAI_API_KEY=... \
OPENAI_VISION_MODEL=gpt-5.5 \
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

即使 OpenAI provider 失败，上传任务和 `/api/tasks/{taskId}/dsl` 也应继续成功；M9 patch 失败时会回退 base DSL。

OCR 和 patch 默认配置：

```bash
OCR_PROVIDER=fake
DSL_PATCH_MODE=debug
```

百度 PP-OCRv5 异步 OCR smoke：

```bash
cd backend
OCR_PROVIDER=baidu_ppocrv5 \
BAIDU_PADDLE_OCR_TOKEN=... \
BAIDU_PADDLE_OCR_MODEL=PP-OCRv5 \
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

百度 token 是 bearer token，只能放在本地环境变量或未提交的 `.env` 中，不能写入仓库。百度 OCR 失败时上传任务仍应 completed，`/dsl` 回退 fallback DSL。

上传后可以查询：

```bash
curl http://localhost:8000/api/tasks/{taskId}/ocr
curl http://localhost:8000/api/tasks/{taskId}/dsl-patch
curl http://localhost:8000/api/tasks/{taskId}/text-replacements
curl http://localhost:8000/api/tasks/{taskId}/text-bindings
curl http://localhost:8000/api/tasks/{taskId}/component-structures
curl http://localhost:8000/api/tasks/{taskId}/component-annotations
curl http://localhost:8000/api/tasks/{taskId}/layer-separation-candidates
curl http://localhost:8000/api/tasks/{taskId}/asset-slice-candidates
curl http://localhost:8000/api/tasks/{taskId}/icon-candidates
curl http://localhost:8000/api/tasks/{taskId}/icon-coverage-audit
curl http://localhost:8000/api/tasks/{taskId}/icon-gap-candidates
curl http://localhost:8000/api/tasks/{taskId}/icon-placement-plan
curl http://localhost:8000/api/tasks/{taskId}/icon-visible-fallback
curl http://localhost:8000/api/tasks/{taskId}/icon-business-candidates
curl http://localhost:8000/api/tasks/{taskId}/perception-benchmark
```

M14 text replacement 默认只记录 decisions、sampling strategy 和 quality/application 报告，不改变可见 DSL：

```bash
cd backend
TEXT_REPLACEMENT_MODE=debug uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

本地 smoke 可显式启用 apply。M14 只会写入通过 UI-aware sampling decision 和 quality gate 的 replacement：

```bash
cd backend
TEXT_REPLACEMENT_MODE=apply \
TEXT_REPLACEMENT_ENABLE_COLORED_BG=true \
TEXT_REPLACEMENT_UI_AWARE_SAMPLING=true \
TEXT_BINDING_ENABLED=true \
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

M15 text binding 默认开启，只生成 `/text-bindings` 报告和 DSL meta，不改变 Figma 可见输出。它的 inferred containers 是 M16 输入，不会写回 `/primitives`。

M16 component structure 默认开启，只生成 `/component-structures` 报告和 DSL meta，不改变 Figma 可见输出。它消费 M15 binding report，输出 component candidates 和 layout groups，供 M17+ 图层命名、分组实验和局部结构化替换使用；不会创建 Figma Component/Instance，也不会删除 fallback region。

M17 component annotation 默认开启，生成 `/component-annotations` 报告，并只更新已有 DSL element 的 `name` 和 `meta`：

```bash
COMPONENT_ANNOTATION_ENABLED=true
COMPONENT_ANNOTATION_LAYER_NAMING=true
COMPONENT_ANNOTATION_MIN_CONFIDENCE=0.70
```

M17 的 layer naming 使用已有 DSL `name` 字段，Renderer 已按该字段命名 Figma node。M17 不切图、不删除 fallback、不创建真实 Figma group、Component/Instance 或 Auto Layout，也不做图标、圆形、三角形、五角星或复杂图形重建。

M18 layer separation candidate 默认开启，生成 `/layer-separation-candidates` 报告，并只更新 DSL 顶层 meta：

```bash
LAYER_SEPARATION_ENABLED=true
LAYER_SEPARATION_MIN_CONFIDENCE=0.70
LAYER_SEPARATION_SIMPLE_FILL_TOLERANCE=24
LAYER_SEPARATION_MAX_COMPONENT_AREA_RATIO=0.35
```

M18 用于判断 component 后续是否适合 shape + editable text、image slice with simple fill candidate、future repair、embedded text 或 no text。它不切图、不生成填充 PNG、不删除 fallback、不修改已有 DSL element、不做 AI inpainting、不引入 Pillow/OpenCV，也不做图标、圆形、三角形、五角星或复杂图形重建。

M19 local asset slice candidate 默认开启，生成 `/asset-slice-candidates` 报告和本地实验 PNG，并只更新 DSL 顶层 meta：

```bash
ASSET_SLICE_ENABLED=true
ASSET_SLICE_MAX_CANDIDATES=24
ASSET_SLICE_MIN_CONFIDENCE=0.70
ASSET_SLICE_MAX_AREA_RATIO=0.25
ASSET_SLICE_GENERATE_FILLED=true
```

M19 基于 M18 低风险候选生成 original slice 和可选 filled slice，写入 `backend/storage/assets/{taskId}/slices/`。这些 slice 不进入 DSL `assets`，不会改变 Figma 可见输出。M19 不删除 fallback、不做正式局部替换、不做 AI inpainting、不引入 Pillow/OpenCV，也不做图标、圆形、三角形、五角星或复杂图形重建。

M20 icon candidate extraction 默认开启，生成 `/icon-candidates` 报告和本地 icon PNG，并只更新 DSL 顶层 meta：

```bash
ICON_CANDIDATE_ENABLED=true
ICON_CANDIDATE_MIN_CONFIDENCE=0.70
ICON_CANDIDATE_MAX_CANDIDATES=64
ICON_CANDIDATE_MIN_SIZE=8
ICON_CANDIDATE_MAX_SIZE=96
ICON_CANDIDATE_FOREGROUND_DISTANCE=32
ICON_CANDIDATE_MAX_COMPONENT_AREA_RATIO=0.20
```

M20 基于 M15-M17 结构索引，在 component 内部找高置信小图标 bbox，并用标准库 PNG 工具裁剪到 `backend/storage/assets/{taskId}/icons/`。这些 icon 不进入 DSL `assets`，不会改变 Figma 可见输出。M20 不删除 fallback、不做 SVG/icon 语义识别、不做图标库匹配、不做可见 icon replacement、不做 AI inpainting、不引入 Pillow/OpenCV，也不做圆形、三角形、五角星或复杂图形重建。

M21 icon coverage audit 默认开启，生成 `/icon-coverage-audit` 报告和 debug overlay PNG，并只更新 DSL 顶层 meta：

```bash
ICON_COVERAGE_AUDIT_ENABLED=true
ICON_COVERAGE_OVERLAY_ENABLED=true
ICON_COVERAGE_MISSED_HINTS_ENABLED=true
ICON_COVERAGE_MIN_HINT_CONFIDENCE=0.60
ICON_COVERAGE_MAX_MISSED_HINTS=80
ICON_COVERAGE_FOREGROUND_DISTANCE=32
```

M21 基于 M20 icon candidates 判断未来放回 DSL/Figma 前的 readiness，并在局部高价值区域生成 missedIconHints。overlay 写入 `backend/storage/assets/{taskId}/debug/icon_coverage_overlay.png`，只画彩色 bbox，不画文字标签。overlay、icon 和 missed hints 都不进入 DSL `assets`，不会改变 Figma 可见输出。M21 不把 M20 icon 放进画布、不删除 fallback、不做 SVG/icon 语义识别、不做图标库匹配、不按中文文案特化、不做 AI inpainting、不引入 Pillow/OpenCV。

M22 icon gap candidate 默认开启，生成 `/icon-gap-candidates` 报告、本地 gap icon PNG 和 debug overlay PNG，并只更新 DSL 顶层 meta：

```bash
ICON_GAP_CANDIDATE_ENABLED=true
ICON_GAP_CANDIDATE_MIN_CONFIDENCE=0.72
ICON_GAP_CANDIDATE_MAX_CANDIDATES=48
ICON_GAP_CANDIDATE_MIN_SIZE=8
ICON_GAP_CANDIDATE_MAX_SIZE=80
ICON_GAP_CANDIDATE_FOREGROUND_DISTANCE=32
ICON_GAP_CANDIDATE_RETRY_PADDING=12
ICON_GAP_CANDIDATE_EDGE_CLIP_TOLERANCE=3
ICON_GAP_CANDIDATE_OVERLAY_ENABLED=true
```

M22 基于 M21 missedIconHints 和少量 header、bottom nav、shortcut、trailing 局部 probe 补裁可靠漏裁图标，写入 `backend/storage/assets/{taskId}/icons_gap/`。overlay 写入 `backend/storage/assets/{taskId}/debug/icon_gap_overlay.png`，只画彩色 bbox，不画文字标签。gap icon 和 overlay 都不进入 DSL `assets`，不会改变 Figma 可见输出。M22 不做全局 icon detection、不做 Codia 式全量可拖动图层、不把 gap icon 放进画布、不删除 fallback、不做 SVG/icon 语义识别、不做图标库匹配、不按中文文案特化、不做 AI inpainting、不引入 Pillow/OpenCV。

M23 icon placement plan 默认开启，生成 `/icon-placement-plan` 报告和 debug overlay PNG，并只更新 DSL 顶层 meta：

```bash
ICON_PLACEMENT_PLAN_ENABLED=true
ICON_PLACEMENT_PLAN_OVERLAY_ENABLED=true
ICON_PLACEMENT_PLAN_DEDUP_IOU=0.50
ICON_PLACEMENT_PLAN_TEXT_OVERLAP_IOU=0.10
ICON_PLACEMENT_PLAN_SLICE_OVERLAP_IOU=0.50
ICON_PLACEMENT_PLAN_MAX_PLACEMENTS=128
```

M23 基于 M20/M22 icon assets、M19 slice candidates 和当前 DSL collision facts 规划 dedupe、blocked、needs_fallback_mask、needs_slice_coordination、needs_fallback_coordination、review_required 和 ready_for_visible_icon。overlay 写入 `backend/storage/assets/{taskId}/debug/icon_placement_overlay.png`，只画彩色 bbox，不画文字标签。placement plan、futureDslNodeHint 和 overlay 都不进入 DSL `assets`，不会改变 Figma 可见输出。M23 不裁新 icon、不把 icon 放进画布、不删除 fallback、不做全局 icon detection、不做 Codia 式全量可拖动图层、不做 SVG/icon 语义识别、不做图标库匹配、不做 AI inpainting、不引入 Pillow/OpenCV。

M24 visible icon fallback replay 默认关闭。它会改变可见 DSL/Figma 输出，只有实验或 smoke 时才显式开启：

```bash
ICON_VISIBLE_FALLBACK_ENABLED=false
ICON_VISIBLE_FALLBACK_MAX_PLACEMENTS=12
ICON_VISIBLE_FALLBACK_MIN_CONFIDENCE=0.85
ICON_VISIBLE_FALLBACK_MASK_PADDING=2
ICON_VISIBLE_FALLBACK_MAX_MASK_SIZE=96
ICON_VISIBLE_FALLBACK_SOLID_BG_TOLERANCE=28
ICON_VISIBLE_FALLBACK_ALLOWED_ROLES=nav_icon,header_nav_icon,header_action_icon,leading_icon
ICON_VISIBLE_FALLBACK_OVERLAY_ENABLED=true
```

开启后，M24 基于 M23 `needs_fallback_mask` placement 小范围回放 M20/M22 已裁出的 nav/header/leading icon。它会 append `icon_fallback_cover` shape、`visible_icon_fallback` image node，并只把实际使用的 icon asset 追加进 DSL `assets`。M24 写入 `backend/storage/icon_visible_fallbacks/{taskId}.json` 和 `backend/storage/assets/{taskId}/debug/icon_visible_fallback_overlay.png`，通过 `/api/tasks/{taskId}/icon-visible-fallback` 查询。M24 不处理没拆出来的 icon、不补 M21 missed hints、不处理 M22 blocked hints、不做新的 icon crop、不做全局 icon detection、不做 Codia 式全量可拖动图层、不做透明 PNG/SVG/icon 语义识别、不做图标库替换、不引入 Pillow/OpenCV。

M25 region-guided business icon candidate 默认开启，只生成报告、业务 icon PNG 和 overlay，不改变 Figma 可见输出：

```bash
ICON_BUSINESS_CANDIDATE_ENABLED=true
ICON_BUSINESS_CANDIDATE_MAX_CANDIDATES=80
ICON_BUSINESS_CANDIDATE_MIN_CONFIDENCE=0.70
ICON_BUSINESS_CANDIDATE_MIN_SIZE=8
ICON_BUSINESS_CANDIDATE_MAX_SIZE=96
ICON_BUSINESS_CANDIDATE_FOREGROUND_DISTANCE=32
ICON_BUSINESS_CANDIDATE_RETRY_PADDING=12
ICON_BUSINESS_CANDIDATE_EDGE_CLIP_TOLERANCE=3
ICON_BUSINESS_CANDIDATE_OVERLAY_ENABLED=true
ICON_BUSINESS_BOTTOM_NAV_ENABLED=true
ICON_BUSINESS_PRIMARY_BUTTON_ENABLED=true
ICON_BUSINESS_SHORTCUT_CARD_ENABLED=true
ICON_BUSINESS_METRIC_CARD_ENABLED=true
ICON_BUSINESS_ROOM_CARD_ENABLED=true
ICON_BUSINESS_TRAILING_ENABLED=true
ICON_BUSINESS_TIP_INFO_ENABLED=true
```

M25 绕开 M16 业务组件识别不足，直接在 bottom nav、primary button trailing arrow、shortcut tile、metric card、room card、trailing 和 tip/info 等稳定区域 probe 业务 icon candidate，写入 `backend/storage/icon_business_candidates/{taskId}.json`、`backend/storage/assets/{taskId}/icons_business/*.png` 和 `backend/storage/assets/{taskId}/debug/icon_business_overlay.png`，通过 `/api/tasks/{taskId}/icon-business-candidates` 查询。M25 只追加 DSL 顶层 meta，不新增可见节点，不修改 DSL `assets`，不把 icon 放进画布；它也不做全图无边界 detection、Codia 式全量拆层、插画/头像/建筑/床位平面图复杂资产处理、SVG/icon 语义识别、图标库匹配、AI inpainting 或 Pillow/OpenCV。

M26 visual perception provider benchmark 默认关闭，只生成评估报告和 provider overlay，不改变 DSL/Figma 输出：

```bash
PERCEPTION_BENCHMARK_ENABLED=false
PERCEPTION_BENCHMARK_PROVIDERS=current_rules,opencv
PERCEPTION_BENCHMARK_MAX_CANDIDATES_PER_PROVIDER=300
PERCEPTION_BENCHMARK_OVERLAY_ENABLED=true
PERCEPTION_OPENCV_ENABLED=false
PERCEPTION_OPENCV_IMPORT_NAME=cv2
PERCEPTION_SAM2_ENABLED=false
PERCEPTION_SAM2_MODEL_CFG=
PERCEPTION_SAM2_CHECKPOINT=
PERCEPTION_SAM2_DEVICE=auto
PERCEPTION_SAM2_MAX_IMAGE_EDGE=1280
PERCEPTION_SAM2_MAX_MASKS=300
PERCEPTION_UIED_ENABLED=false
PERCEPTION_UIED_COMMAND=
```

开启后，M26 把 `current_rules`、可选 OpenCV、可选 SAM2 automatic masks 和可选 UIED command adapter 放到统一候选合同下比较，写入 `backend/storage/perception_benchmarks/{taskId}.json` 和 `backend/storage/assets/{taskId}/debug/perception_overlay_*.png`，通过 `/api/tasks/{taskId}/perception-benchmark` 查询。M26 不追加 DSL meta，不裁新 icon asset，不把 provider 输出喂给 Renderer，也不默认安装 OpenCV、torch、sam2 或 UIED。

M26 smoke：

```bash
cd backend
uv run python scripts/run_m26_perception_smoke.py --providers current_rules
uv run --with opencv-python-headless python scripts/run_m26_perception_smoke.py --providers current_rules,opencv
```

SAM2 smoke 需要本机已有 checkpoint 和依赖：

```bash
cd backend
PERCEPTION_SAM2_CHECKPOINT=/absolute/path/to/sam2.1_hiera_tiny.pt \
uv run python scripts/run_m26_perception_smoke.py --providers current_rules,sam2
```

UIED smoke 只在配置外部命令时运行：

```bash
cd backend
PERCEPTION_UIED_COMMAND="python /absolute/path/to/uied_adapter.py" \
uv run python scripts/run_m26_perception_smoke.py --providers current_rules,uied
```

如果要确认完全回退 M7 base DSL：

```bash
cd backend
DSL_PATCH_MODE=off uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`localhost` 只配置在 `manifest.json` 的 `networkAccess.devAllowedDomains`。Figma 不允许把 localhost 放进正式 `allowedDomains`，除非同时提供审核用 `reasoning` 字段。开发期如果要阻断正式网络域名，`allowedDomains` 必须写成 `["none"]`，不能写空数组。

Figma 插件主线程的 JavaScript 解析器比现代浏览器页面更保守。插件 bundle 目标使用 `es2017`，并在构建后扫描 `??`、`?.`、ESM import/export、`structuredClone`、`Object.hasOwn` 和 `for await` 残留。

后续目标命令应覆盖：

```text
运行 DSL 测试
运行 Renderer 测试
运行 API 测试
```

## M7 Sample Smoke

用户提供的当前验收样例目录：

```text
/Users/luhui/Downloads/宿舍床位可视化选择系统_UI设计图/学生端
```

已知 PNG 样例：

```text
01_学生端-首页选床活动.png  941x1672
02_学生端-楼层选择.png      941x1672
03_学生端-房间选择.png      941x1672
04_学生端-床位选择.png      941x1672
05_学生端-确认选床.png      941x1672
06_学生端-选床结果.png      941x1672
07_学生端-登录注册.png      958x1641
```

M7 后端 smoke 可以先用主样例：

```bash
curl -F "file=@/Users/luhui/Downloads/宿舍床位可视化选择系统_UI设计图/学生端/01_学生端-首页选床活动.png" \
  http://localhost:8000/api/upload
```

预期：

- task completed。
- DSL root frame 为 `941 x 1672`。
- `meta.notes` 默认为 `deterministic_region_dsl+m9_patch_debug`。
- `meta.platformHint` 为 `mobile`。
- root children 包含 `original_ref`、`fallback_region_header`、`fallback_region_content`、`fallback_region_bottom` 和 hidden `candidate_text`。
- `/api/tasks/{taskId}/primitives` 返回 `provider: "fake"` 和 `vp_region_header/content/bottom`。
- 默认 `/api/tasks/{taskId}/ocr` 返回 `provider: "fake"`；启用百度后返回 `provider: "baidu_ppocrv5"` 和 `model: "PP-OCRv5"`。
- `/api/tasks/{taskId}/dsl-patch` 返回 `mode: "debug"`。
- `/api/tasks/{taskId}/text-replacements` 默认返回 `mode: "debug"`，包含 accepted/rejected decisions。
- `/api/tasks/{taskId}/text-bindings` 默认返回 `status: "completed"`，包含 containers、bindings 或 unboundTextIds。
- `/api/tasks/{taskId}/component-structures` 默认返回 `status: "completed"`，包含 components、groups 或 unstructuredContainerIds。
- `/api/tasks/{taskId}/component-annotations` 默认返回 `status: "completed"`，包含 annotations、groupHints、unannotatedElementIds 或 unresolvedComponentIds。
- `/api/tasks/{taskId}/layer-separation-candidates` 默认返回 `status: "completed"`，包含 candidates、fallbackContexts、blockedComponentIds 和 meta。
- `/api/tasks/{taskId}/asset-slice-candidates` 默认返回 `status: "completed"`，包含 slices、blockedComponentIds 和 meta。
- `/api/tasks/{taskId}/icon-candidates` 默认返回 `status: "completed"`，包含 icons、blockedComponentIds 和 meta。
- `/api/tasks/{taskId}/icon-coverage-audit` 默认返回 `status: "completed"`，包含 placements、missedIconHints、coverageOverlay 和 meta。
- `/api/tasks/{taskId}/icon-gap-candidates` 默认返回 `status: "completed"`，包含 gapIcons、blockedHints、gapOverlay 和 meta。
- `/api/tasks/{taskId}/icon-placement-plan` 默认返回 `status: "completed"`，包含 placements、dedupedIcons、blockedIcons、placementOverlay 和 meta。
- `/api/tasks/{taskId}/icon-business-candidates` 默认返回 `status: "completed"`，包含 businessIcons、blockedCandidates、businessOverlay 和 meta。
- `/api/tasks/{taskId}/perception-benchmark` 默认返回 `PERCEPTION_BENCHMARK_NOT_FOUND`；只有显式开启 M26 benchmark 后才返回 providers、comparison 和 meta。
- 上传链路不出现 sample 专属的 `search_icon` warning。

## Configuration

环境变量记录在 [../reference/env-vars.md](../reference/env-vars.md)。
