# 环境变量

当前后端和插件已有本地运行代码。后端都有默认值，不需要 `.env` 才能启动。

## Variables

| 名称 | 用途 | 默认值 | 是否必需 |
| --- | --- | --- | --- |
| `API_BASE_URL` | 插件调用后端 API | `http://localhost:8000/api` | 当前插件硬编码同值，后续设置页再读取 |
| `PUBLIC_BASE_URL` | 后端生成 `/files/...` URL | `http://localhost:8000` | 否 |
| `CORS_ALLOW_ORIGINS` | 允许浏览器/Figma 插件调用后端的 Origin，逗号分隔 | `*` | 否 |
| `VISUAL_PRIMITIVE_PROVIDER` | M8 primitive provider，支持 `fake`、`openai` | `fake` | 否 |
| `OCR_PROVIDER` | OCR provider，支持 `fake`、`baidu_ppocrv5` | `fake` | 否 |
| `OCR_MIN_CONFIDENCE` | OCR block 最低置信度，低于该值丢弃 | `0.70` | 否 |
| `DSL_PATCH_MODE` | M9 DSL patch 模式，支持 `off`、`debug`、`apply` | `debug` | 否 |
| `TEXT_REPLACEMENT_MODE` | M12 text replacement 模式，支持 `off`、`debug`、`apply` | `debug` | 否 |
| `TEXT_REPLACEMENT_MAX_BLOCKS` | M12 apply 最多接受的 OCR block 数，用作异常 OCR/超长图熔断阀 | `100` | 否 |
| `TEXT_REPLACEMENT_MIN_CONFIDENCE` | M12 replacement 最低 OCR 置信度 | `0.95` | 否 |
| `TEXT_REPLACEMENT_SOLID_BG_TOLERANCE` | M12 低复杂度背景容差 | `18` | 否 |
| `TEXT_REPLACEMENT_MAX_HEIGHT` | M12 可替换 OCR bbox 最大高度 | `64` | 否 |
| `TEXT_REPLACEMENT_MIN_WIDTH` | M12 可替换 OCR bbox 最小宽度 | `12` | 否 |
| `TEXT_REPLACEMENT_MIN_HEIGHT` | M12 可替换 OCR bbox 最小高度 | `10` | 否 |
| `TEXT_REPLACEMENT_ENABLE_COLORED_BG` | 是否允许彩色/深色低复杂度背景上的浅色文字替换 | `true` | 否 |
| `TEXT_REPLACEMENT_MIN_CONTRAST` | replacement 前景文字与背景最小亮度差 | `90` | 否 |
| `TEXT_REPLACEMENT_EDGE_SAMPLE_PADDING` | 背景采样 bbox 外扩像素 | `4` | 否 |
| `TEXT_REPLACEMENT_TEXT_SAMPLE_INSET` | 前景文字采样 bbox 内缩像素 | `1` | 否 |
| `TEXT_REPLACEMENT_UI_AWARE_SAMPLING` | 是否开启 M14 UI-aware 多策略采样，减少 badge、图例、按钮、卡片和底栏文本的 `complex_background` 误杀 | `true` | 否 |
| `TEXT_REPLACEMENT_LOCAL_BG_TOLERANCE` | M14 局部背景采样容差，不改变全局 solid background 容差 | `24` | 否 |
| `TEXT_REPLACEMENT_MAX_RESCUE_STRATEGIES` | 单个 OCR candidate 最多尝试的 M14 rescue 采样策略数 | `4` | 否 |
| `TEXT_BINDING_ENABLED` | 是否生成 M15 text binding 报告；不改变 Figma 可见输出 | `true` | 否 |
| `TEXT_BINDING_MIN_CONFIDENCE` | M15 text-to-container binding 最低置信度，低于该值进入 `unboundTextIds` | `0.70` | 否 |
| `COMPONENT_STRUCTURE_ENABLED` | 是否生成 M16 component structure 报告；不改变 Figma 可见输出 | `true` | 否 |
| `COMPONENT_STRUCTURE_MIN_CONFIDENCE` | M16 container-to-component 聚合最低置信度，低于该值进入 `unstructuredContainerIds` | `0.70` | 否 |
| `COMPONENT_ANNOTATION_ENABLED` | 是否生成 M17 component annotation 报告并把结构写入已有 DSL element `name/meta`；不改变 Figma 可见输出 | `true` | 否 |
| `COMPONENT_ANNOTATION_LAYER_NAMING` | 是否用 M17 annotation 更新已有 DSL element `name`，供 Renderer 命名 Figma layer | `true` | 否 |
| `COMPONENT_ANNOTATION_MIN_CONFIDENCE` | M17 component annotation 最低 component 置信度，低于该值进入 `unresolvedComponentIds` | `0.70` | 否 |
| `LAYER_SEPARATION_ENABLED` | 是否生成 M18 layer separation candidate 报告；不改变 Figma 可见输出 | `true` | 否 |
| `LAYER_SEPARATION_MIN_CONFIDENCE` | M18 component 分层候选最低置信度，低于该值 blocked | `0.70` | 否 |
| `LAYER_SEPARATION_SIMPLE_FILL_TOLERANCE` | M18 simple fill candidate 的背景最大通道差容忍度，只用于分层候选报告 | `24` | 否 |
| `LAYER_SEPARATION_MAX_COMPONENT_AREA_RATIO` | M18 单个 component bbox 占整页最大面积比例，超过后 blocked | `0.35` | 否 |
| `ASSET_SLICE_ENABLED` | 是否生成 M19 local asset slice candidate 报告和实验 PNG；不改变 Figma 可见输出 | `true` | 否 |
| `ASSET_SLICE_MAX_CANDIDATES` | M19 单任务最多实际生成的 slice candidate 数 | `24` | 否 |
| `ASSET_SLICE_MIN_CONFIDENCE` | M19 component 最低置信度，低于该值 blocked | `0.70` | 否 |
| `ASSET_SLICE_MAX_AREA_RATIO` | M19 单个 slice bbox 占整页最大面积比例，超过后 blocked | `0.25` | 否 |
| `ASSET_SLICE_GENERATE_FILLED` | 是否为 simple fill candidate 生成 filled slice PNG | `true` | 否 |
| `ICON_CANDIDATE_ENABLED` | 是否生成 M20 icon candidate 报告和 icon PNG 候选资产；不改变 Figma 可见输出 | `true` | 否 |
| `ICON_CANDIDATE_MIN_CONFIDENCE` | M20 icon candidate 最低置信度，低于该值不裁剪 | `0.70` | 否 |
| `ICON_CANDIDATE_MAX_CANDIDATES` | M20 单任务最多实际生成的 icon candidate 数 | `64` | 否 |
| `ICON_CANDIDATE_MIN_SIZE` | M20 icon bbox 最小宽高像素 | `8` | 否 |
| `ICON_CANDIDATE_MAX_SIZE` | M20 icon bbox 最大宽高像素 | `96` | 否 |
| `ICON_CANDIDATE_FOREGROUND_DISTANCE` | M20 局部前景像素与背景色的最小 RGB 通道距离 | `32` | 否 |
| `ICON_CANDIDATE_MAX_COMPONENT_AREA_RATIO` | M20 单个 component bbox 占整页最大面积比例，超过后不做 icon scan | `0.20` | 否 |
| `ICON_COVERAGE_AUDIT_ENABLED` | 是否生成 M21 icon coverage audit 报告；不改变 Figma 可见输出 | `true` | 否 |
| `ICON_COVERAGE_OVERLAY_ENABLED` | 是否生成 M21 icon coverage debug overlay PNG | `true` | 否 |
| `ICON_COVERAGE_MISSED_HINTS_ENABLED` | 是否在 M21 报告中生成 missedIconHints | `true` | 否 |
| `ICON_COVERAGE_MIN_HINT_CONFIDENCE` | M21 missed icon hint 最低置信度 | `0.60` | 否 |
| `ICON_COVERAGE_MAX_MISSED_HINTS` | M21 单任务最多 missed icon hints 数 | `80` | 否 |
| `ICON_COVERAGE_FOREGROUND_DISTANCE` | M21 hint 扫描的前景像素与背景色最小 RGB 通道距离 | `32` | 否 |
| `ICON_GAP_CANDIDATE_ENABLED` | 是否生成 M22 region-guided icon gap candidate 报告、gap icon PNG 和 overlay；不改变 Figma 可见输出 | `true` | 否 |
| `ICON_GAP_CANDIDATE_MIN_CONFIDENCE` | M22 gap icon candidate 最低置信度，低于该值不裁剪 | `0.72` | 否 |
| `ICON_GAP_CANDIDATE_MAX_CANDIDATES` | M22 单任务最多实际生成的 gap icon candidate 数 | `48` | 否 |
| `ICON_GAP_CANDIDATE_MIN_SIZE` | M22 gap icon bbox 最小宽高像素 | `8` | 否 |
| `ICON_GAP_CANDIDATE_MAX_SIZE` | M22 gap icon bbox 最大宽高像素 | `80` | 否 |
| `ICON_GAP_CANDIDATE_FOREGROUND_DISTANCE` | M22 gap scan 的前景像素与背景色最小 RGB 通道距离 | `32` | 否 |
| `ICON_GAP_CANDIDATE_RETRY_PADDING` | M22 候选贴 search window 边界时扩大重试的 padding 像素 | `12` | 否 |
| `ICON_GAP_CANDIDATE_EDGE_CLIP_TOLERANCE` | M22 判断候选贴边/半截风险的像素容差 | `3` | 否 |
| `ICON_GAP_CANDIDATE_OVERLAY_ENABLED` | 是否生成 M22 icon gap debug overlay PNG | `true` | 否 |
| `ICON_PLACEMENT_PLAN_ENABLED` | 是否生成 M23 icon placement plan 报告和 placement overlay；不改变 Figma 可见输出 | `true` | 否 |
| `ICON_PLACEMENT_PLAN_OVERLAY_ENABLED` | 是否生成 M23 icon placement debug overlay PNG | `true` | 否 |
| `ICON_PLACEMENT_PLAN_DEDUP_IOU` | M23 判定 M20/M22 icon 重复的 bbox IoU 阈值 | `0.50` | 否 |
| `ICON_PLACEMENT_PLAN_TEXT_OVERLAP_IOU` | M23 判定 icon 与 visible text/cover/candidate_text 冲突的 IoU 阈值 | `0.10` | 否 |
| `ICON_PLACEMENT_PLAN_SLICE_OVERLAP_IOU` | M23 判定 icon 与 M19 slice 冲突的 IoU 阈值 | `0.50` | 否 |
| `ICON_PLACEMENT_PLAN_MAX_PLACEMENTS` | M23 单任务最多 placement plan 数 | `128` | 否 |
| `ICON_VISIBLE_FALLBACK_ENABLED` | 是否启用 M24 visible icon fallback replay；会改变 Figma 可见输出，默认关闭 | `false` | 否 |
| `ICON_VISIBLE_FALLBACK_MAX_PLACEMENTS` | M24 单任务最多回放 placement 数 | `12` | 否 |
| `ICON_VISIBLE_FALLBACK_MIN_CONFIDENCE` | M24 允许回放的 M23 placement 最低置信度 | `0.85` | 否 |
| `ICON_VISIBLE_FALLBACK_MASK_PADDING` | M24 shape cover 相对 icon bbox 的外扩像素 | `2` | 否 |
| `ICON_VISIBLE_FALLBACK_MAX_MASK_SIZE` | M24 shape cover bbox 最大边长 | `96` | 否 |
| `ICON_VISIBLE_FALLBACK_SOLID_BG_TOLERANCE` | M24 solid background sampling 最大通道差容忍度 | `28` | 否 |
| `ICON_VISIBLE_FALLBACK_ALLOWED_ROLES` | M24 允许回放的 placementRole 列表 | `nav_icon,header_nav_icon,header_action_icon,leading_icon` | 否 |
| `ICON_VISIBLE_FALLBACK_OVERLAY_ENABLED` | 是否生成 M24 visible fallback debug overlay PNG | `true` | 否 |
| `ICON_BUSINESS_CANDIDATE_ENABLED` | 是否生成 M25 region-guided business icon candidate 报告、业务 icon PNG 和 overlay；不改变 Figma 可见输出 | `true` | 否 |
| `ICON_BUSINESS_CANDIDATE_MAX_CANDIDATES` | M25 单任务最多实际生成的 business icon candidate 数 | `80` | 否 |
| `ICON_BUSINESS_CANDIDATE_MIN_CONFIDENCE` | M25 business icon candidate 最低置信度，低于该值不裁剪 | `0.70` | 否 |
| `ICON_BUSINESS_CANDIDATE_MIN_SIZE` | M25 business icon bbox 最小宽高像素 | `8` | 否 |
| `ICON_BUSINESS_CANDIDATE_MAX_SIZE` | M25 business icon bbox 最大宽高像素 | `96` | 否 |
| `ICON_BUSINESS_CANDIDATE_FOREGROUND_DISTANCE` | M25 局部前景像素与背景色的最小 RGB 通道距离 | `32` | 否 |
| `ICON_BUSINESS_CANDIDATE_RETRY_PADDING` | M25 候选贴 search window 边界时扩大重试的 padding 像素 | `12` | 否 |
| `ICON_BUSINESS_CANDIDATE_EDGE_CLIP_TOLERANCE` | M25 判断候选贴边/半截风险的像素容差 | `3` | 否 |
| `ICON_BUSINESS_CANDIDATE_OVERLAY_ENABLED` | 是否生成 M25 business icon debug overlay PNG | `true` | 否 |
| `ICON_BUSINESS_BOTTOM_NAV_ENABLED` | 是否启用 M25 bottom nav region probe | `true` | 否 |
| `ICON_BUSINESS_PRIMARY_BUTTON_ENABLED` | 是否启用 M25 primary button probe | `true` | 否 |
| `ICON_BUSINESS_SHORTCUT_CARD_ENABLED` | 是否启用 M25 shortcut/menu tile probe | `true` | 否 |
| `ICON_BUSINESS_METRIC_CARD_ENABLED` | 是否启用 M25 metric/stat card probe | `true` | 否 |
| `ICON_BUSINESS_ROOM_CARD_ENABLED` | 是否启用 M25 room card/status icon probe | `true` | 否 |
| `ICON_BUSINESS_TRAILING_ENABLED` | 是否启用 M25 row/card trailing icon probe | `true` | 否 |
| `ICON_BUSINESS_TIP_INFO_ENABLED` | 是否启用 M25 tip/info leading icon probe | `true` | 否 |
| `PERCEPTION_BENCHMARK_ENABLED` | 是否在上传链路中生成 M26 visual perception provider benchmark；默认关闭，不改变 DSL/Figma 输出 | `false` | 否 |
| `PERCEPTION_BENCHMARK_PROVIDERS` | M26 benchmark provider 列表，支持 `current_rules,opencv,sam2,uied` | `current_rules,opencv` | 否 |
| `PERCEPTION_BENCHMARK_MAX_CANDIDATES_PER_PROVIDER` | M26 单 provider 最多保留候选数 | `300` | 否 |
| `PERCEPTION_BENCHMARK_OVERLAY_ENABLED` | 是否生成 M26 provider debug overlay PNG | `true` | 否 |
| `PERCEPTION_OPENCV_ENABLED` | 是否允许 M26 OpenCV provider 运行；仍要求本地可 import `cv2` 和 `numpy` | `false` | 否 |
| `PERCEPTION_OPENCV_IMPORT_NAME` | M26 OpenCV provider 的 import 名称 | `cv2` | 否 |
| `PERCEPTION_SAM2_ENABLED` | 是否允许 M26 SAM2 provider 运行；仍要求 checkpoint、torch 和 sam2 可用 | `false` | 否 |
| `PERCEPTION_SAM2_MODEL_CFG` | M26 SAM2 model config 路径或包内 config 名；为空时按 checkpoint 名推断 | 空 | 否 |
| `PERCEPTION_SAM2_CHECKPOINT` | M26 SAM2 checkpoint 路径 | 空 | 仅启用 SAM2 时需要 |
| `PERCEPTION_SAM2_DEVICE` | M26 SAM2 推理设备，支持 `auto`、`cpu`、`mps`、`cuda` 等 torch device | `auto` | 否 |
| `PERCEPTION_SAM2_MAX_IMAGE_EDGE` | M26 SAM2 推理前最长边缩放上限 | `1280` | 否 |
| `PERCEPTION_SAM2_MAX_MASKS` | M26 SAM2 最多读取 automatic masks 数 | `300` | 否 |
| `PERCEPTION_UIED_ENABLED` | 是否允许 M26 UIED external command adapter 运行 | `false` | 否 |
| `PERCEPTION_UIED_COMMAND` | M26 UIED adapter 命令；stdin 读 PNG bytes，stdout 输出 JSON candidates | 空 | 仅启用 UIED 时需要 |
| `M30_PREVIEW_PROFILE` | M30.1 插件 preview artifact profile；`production` 只保留运行必要产物，`development` 保留全量诊断产物 | `production` | 否 |
| `LEGACY_PRE_M29_UPLOAD_ENABLED` | 是否注册 pre-M29 legacy `/api/upload` 和旧 task debug endpoints；仅用于历史诊断和回归 | `false` | 否 |
| `SAM_VISUAL_CANDIDATE_ENABLED` | 是否在上传链路中生成 M27 SAM visual candidate filtering 报告；默认关闭，不改变 DSL/Figma 输出 | `false` | 否 |
| `SAM_VISUAL_CANDIDATE_MODEL_CFG` | M27 SAM2 model config 路径或包内 config 名；为空时按 checkpoint 名推断 | 空 | 否 |
| `SAM_VISUAL_CANDIDATE_CHECKPOINT` | M27 SAM2 checkpoint 路径 | 空 | 仅启用 M27 时需要 |
| `SAM_VISUAL_CANDIDATE_DEVICE` | M27 SAM2 推理设备，支持 `auto`、`cpu`、`mps`、`cuda` 等 torch device | `auto` | 否 |
| `SAM_VISUAL_CANDIDATE_MAX_IMAGE_EDGE` | M27 SAM2 推理前最长边缩放上限；UI bbox 候选默认低于 M26 benchmark 的密集分割设置 | `960` | 否 |
| `SAM_VISUAL_CANDIDATE_MAX_MASKS` | M27 最多读取 automatic masks 数 | `300` | 否 |
| `SAM_VISUAL_CANDIDATE_POINTS_PER_SIDE` | M27 SAM2 automatic mask 每边采样点数；成本近似按平方增长 | `8` | 否 |
| `SAM_VISUAL_CANDIDATE_POINTS_PER_BATCH` | M27 SAM2 automatic mask prompt batch size | `64` | 否 |
| `SAM_VISUAL_CANDIDATE_MAX_CANDIDATES` | M27 最多保留 accepted visual candidates 数 | `120` | 否 |
| `SAM_VISUAL_CANDIDATE_MIN_CONFIDENCE` | M27 accepted candidate 最低规则置信度 | `0.72` | 否 |
| `SAM_VISUAL_CANDIDATE_MIN_AREA` | M27 maskArea 最小面积 | `64` | 否 |
| `SAM_VISUAL_CANDIDATE_MAX_AREA_RATIO` | M27 单 bbox 占整图最大面积比例 | `0.12` | 否 |
| `SAM_VISUAL_CANDIDATE_TEXT_OVERLAP_IOU` | M27 与 visible text、cover、candidate_text 的冲突 IoU 阈值 | `0.10` | 否 |
| `SAM_VISUAL_CANDIDATE_EXISTING_ICON_IOU` | M27 与 M20/M22/M23/M24/M25 existing icon 判重 IoU 阈值 | `0.50` | 否 |
| `SAM_VISUAL_CANDIDATE_OVERLAY_ENABLED` | 是否生成 M27 SAM visual candidate debug overlay PNG | `true` | 否 |
| `BAIDU_PADDLE_OCR_TOKEN` | 百度 AI Studio OCR bearer token | 无 | 仅 `OCR_PROVIDER=baidu_ppocrv5` 时需要 |
| `BAIDU_PADDLE_OCR_JOB_URL` | 百度 AI Studio OCR jobs endpoint | `https://paddleocr.aistudio-app.com/api/v2/ocr/jobs` | 否 |
| `BAIDU_PADDLE_OCR_MODEL` | 百度 OCR 模型 | `PP-OCRv5` | 否 |
| `BAIDU_PADDLE_OCR_POLL_INTERVAL_SECONDS` | 百度异步 OCR 轮询间隔 | `5` | 否 |
| `BAIDU_PADDLE_OCR_TIMEOUT_SECONDS` | 百度异步 OCR 单任务超时 | `120` | 否 |
| `OPENAI_API_KEY` | OpenAI primitive provider 密钥 | 无 | 仅 `VISUAL_PRIMITIVE_PROVIDER=openai` 时需要 |
| `OPENAI_VISION_MODEL` | OpenAI primitive provider 使用的视觉模型 | `gpt-5.5` | 否 |
| `OPENAI_TIMEOUT_SECONDS` | OpenAI 请求超时秒数 | `30` | 否 |
| `STORAGE_ROOT` | 本地文件存储根目录 | `backend/storage` | 否 |
| `DATABASE_PATH` | SQLite 数据库路径 | `backend/storage/app.db` | 否 |
| `MAX_UPLOAD_BYTES` | PNG 上传大小上限 | `10485760` | 否 |

真实密钥不得写入仓库。

默认 `fake` provider 不调用 OpenAI 或百度，也不需要外部密钥。

`M30_PREVIEW_PROFILE=production` 是 `/api/upload-m30-preview` 的默认真实预览运行态。它保留 OCR、结构化 M29/M30 JSON、M29.0.5 formal visual assets、M30 DSL/report、published renderer assets 和 `stage_timings.json`，但不生成 M29 overlay、preview sheet、review crop 或 M30 preview overlay。`M30_PREVIEW_PROFILE=development` 保留这些诊断产物，用于本地调试和证据审计。该变量不影响 M29/M30 单阶段脚本的默认开发态输出。

`LEGACY_PRE_M29_UPLOAD_ENABLED=false` 是默认产品运行态。默认后端不注册旧 `/api/upload`、`/api/tasks/{taskId}/primitives`、`/api/tasks/{taskId}/ocr`、`/api/tasks/{taskId}/dsl-patch` 以及 M12-M28 旧调试 endpoints。需要复查历史诊断链路时才显式设为 `true`。

`BAIDU_PADDLE_OCR_TOKEN` 是 bearer token，必须只通过本地环境变量或未提交的 `.env` 提供，不能写入仓库。

`DSL_PATCH_MODE=apply` 仍不做可见文字替换。M14 可见替换由 `TEXT_REPLACEMENT_MODE=apply` 单独控制，默认 `debug` 只记录 decisions、sampling strategy、quality 和 application。

M15 binding 由 `TEXT_BINDING_ENABLED` 控制，默认开启并只生成 `/text-bindings` 报告和 DSL meta。它不会重组图层、删除 fallback 或把 inferred containers 写回 visual primitives。

M16 component structure 由 `COMPONENT_STRUCTURE_ENABLED` 控制，默认开启并只生成 `/component-structures` 报告和 DSL meta。它消费 M15 bindings，聚合 component candidates 和 layout groups；不会创建 Figma Component/Instance、不会删除 fallback、不会新增可见 DSL 节点，也不会把 inferred components 写回 visual primitives。

M17 component annotation 由 `COMPONENT_ANNOTATION_ENABLED` 控制，默认开启并生成 `/component-annotations` 报告。它消费 M16 structures，通过确定性 ID join 只修改已有 DSL element 的 `name` 和 `meta`，并追加 DSL meta。`COMPONENT_ANNOTATION_LAYER_NAMING=false` 时仍生成 annotation 报告和 element meta，但不改 element name。M17 不切图、不删除 fallback、不创建真实 Figma group、Component/Instance 或 Auto Layout。

M18 layer separation 由 `LAYER_SEPARATION_ENABLED` 控制，默认开启并生成 `/layer-separation-candidates` 报告。它消费 M14 replacement、M15 binding、M16 structure 和 M17 annotation facts，只追加 DSL 顶层 meta。M18 第一版只输出 `solid_color_fill` simple fill candidate，不生成实际 PNG、不切图、不删除 fallback、不修改已有 DSL element、不做 AI inpainting、不引入 Pillow/OpenCV，也不重建图标、圆形、三角形、五角星或复杂图形。

M19 asset slice 由 `ASSET_SLICE_ENABLED` 控制，默认开启并生成 `/asset-slice-candidates` 报告和本地实验 PNG。它消费 M18 layer separation candidates，只对低风险 slice-priority component 生成 original slice 和可选 filled slice。M19 只追加 DSL 顶层 meta，不修改已有 DSL element，不修改 DSL `assets` 数组，不删除 fallback，不做正式局部替换，不做 AI inpainting，不引入 Pillow/OpenCV，也不重建图标、圆形、三角形、五角星或复杂图形。

M20 icon candidate 由 `ICON_CANDIDATE_ENABLED` 控制，默认开启并生成 `/icon-candidates` 报告和本地 icon PNG 候选资产。它消费 M15-M17 的结构索引，在 component 内部限定 search window 找小型前景块并用标准库 PNG 工具裁剪。M20 只追加 DSL 顶层 meta，不修改已有 DSL element，不修改 DSL `assets` 数组，不删除 fallback，不做 SVG/icon 语义识别、图标库匹配、可见 icon 替换、AI inpainting，不引入 Pillow/OpenCV，也不重建复杂形状。

M21 icon coverage audit 由 `ICON_COVERAGE_AUDIT_ENABLED` 控制，默认开启并生成 `/icon-coverage-audit` 报告和 debug overlay PNG。它消费 M20 icon candidates、M19 slice candidates 和当前 DSL，输出 placements、missedIconHints、collision/readiness 统计和 overlay。M21 只追加 DSL 顶层 meta，不修改已有 DSL element，不修改 DSL `assets` 数组，不删除 fallback，不把 M20 icon 放进画布，不做 SVG/icon 语义识别、图标库匹配、可见 icon replacement、AI inpainting，不引入 Pillow/OpenCV。overlay 只画彩色 bbox，不画文字标签。

M22 icon gap candidate 由 `ICON_GAP_CANDIDATE_ENABLED` 控制，默认开启并生成 `/icon-gap-candidates` 报告、`icons_gap/*.png` 候选资产和 debug overlay PNG。它消费 M21 missedIconHints、M20 icon candidates 和少量 region-guided probe，补裁可靠的 header、bottom nav、shortcut、trailing icon gap。M22 只追加 DSL 顶层 meta，不修改已有 DSL element，不修改 DSL `assets` 数组，不删除 fallback，不把 gap icon 放进画布，不做全局 icon detection、不做 Codia 式全量可拖动图层、不做 SVG/icon 语义识别、图标库匹配、可见 icon replacement、AI inpainting，不引入 Pillow/OpenCV。overlay 只画彩色 bbox，不画文字标签。

M23 icon placement plan 由 `ICON_PLACEMENT_PLAN_ENABLED` 控制，默认开启并生成 `/icon-placement-plan` 报告和 debug overlay PNG。它消费 M20 icon candidates、M22 gap icon candidates、M19 slice candidates 和当前 DSL collision facts，统一判断 dedupe、blocked、needs_fallback_mask、needs_slice_coordination、needs_fallback_coordination、review_required 和 ready_for_visible_icon。M23 只追加 DSL 顶层 meta，不修改已有 DSL element，不修改 DSL `assets` 数组，不删除 fallback，不裁新 icon，不把 icon 放进画布，不做全局 icon detection、不做 Codia 式全量可拖动图层、不做 SVG/icon 语义识别、图标库匹配、可见 icon replacement、AI inpainting，不引入 Pillow/OpenCV。`futureDslNodeHint` 只存在于报告，不是 Renderer 输入。

M24 visible icon fallback replay 由 `ICON_VISIBLE_FALLBACK_ENABLED` 控制，默认关闭，因为它会改变可见 DSL/Figma 输出。开启后，它只消费 M23 `needs_fallback_mask` placement，把 M20/M22 已裁出且低风险的 nav/header/leading icon 用 `icon_fallback_cover` shape + `visible_icon_fallback` image node 小范围回放，并只把实际使用的 icon asset 追加进 DSL `assets`。M24 不处理没拆出来的 icon，不补 M21 missed hints，不处理 M22 blocked hints，不做新的 icon crop、不做全局 icon detection、不做 Codia 式全量可拖动图层、不做透明 PNG/SVG/icon 语义识别、不做图标库替换、不引入 Pillow/OpenCV。

M25 business icon candidate 由 `ICON_BUSINESS_CANDIDATE_ENABLED` 控制，默认开启，因为它只生成旁路报告、候选 PNG、overlay 和 DSL 顶层 meta，不改变 Figma 可见输出。它绕开 M16 业务组件识别不足，基于 bottom nav、primary button trailing arrow、shortcut tile、metric card、room card、trailing 和 tip/info 等稳定区域 probe 裁业务 icon 候选。M25 不修改 DSL `assets`，不把 icon 放进画布，不做可见 replay，不做全图无边界 detection，不做 Codia 式全量拆层，不处理插画、头像、建筑或床位平面图复杂资产，不做 SVG/icon 语义识别、不做图标库替换、不引入 Pillow/OpenCV。

M26 perception benchmark 由 `PERCEPTION_BENCHMARK_ENABLED` 控制，默认关闭，因为它是评估层，不是上传质量阶段。开启后生成 `/perception-benchmark` 报告和 provider overlay，把 `current_rules`、可选 OpenCV、可选 SAM2 automatic mask 和可选 UIED command adapter 放到统一合同下比较。M26 不修改 DSL，不追加 DSL meta，不裁新 icon asset，不改变 Figma 可见输出，不默认下载模型，也不默认引入 OpenCV、torch、sam2 或 UIED 到生产依赖。

M27 SAM visual candidate filtering 由 `SAM_VISUAL_CANDIDATE_ENABLED` 控制，默认关闭，因为它需要本地 SAM2 runtime 和 checkpoint。开启后生成 `/sam-visual-candidates` 报告和 overlay，把 SAM2 automatic masks 过滤成 accepted/blocked visual candidates。M27 会在 backend 进程内缓存 SAM2 runtime，默认使用 `SAM_VISUAL_CANDIDATE_MAX_IMAGE_EDGE=960` 和 `SAM_VISUAL_CANDIDATE_POINTS_PER_SIDE=8` 控制 automatic mask 成本。M27 不修改 DSL，不追加 DSL meta，不裁新 icon asset，不生成透明 PNG，不改变 Figma 可见输出。当前本机 checkpoint 建议放在 `/Volumes/WorkDrive/Models/sam2/sam2.1_hiera_tiny.pt`，不要提交到 git。
