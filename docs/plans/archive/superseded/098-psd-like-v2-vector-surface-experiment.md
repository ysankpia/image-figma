# 098 PSD-like v2 Vector Surface A/B Experiment

- 状态：active
- 创建日期：2026-06-02
- 分支：`feat/omniparser-vlm-pipeline`
- 负责人：Codex
- 前置 checkpoint：`4abd456 feat: add backend python draft MVP experiments`

## Summary

本计划新开一条独立的 PSD-like v2 实验，不继续在 v1 的 raster residual / inpaint 路线上补洞。v2 的第一原则是：能由矢量表达的 UI surface，不应先裁成 raster asset。

目标不是复刻 PSD 或 Codia，而是验证：

```text
PNG
-> OCR text mask
-> vector surface extraction
-> rounded rect fitting
-> shape ownership planner
-> raster fallback
-> Draft Runtime DSL
```

v1 保留为 baseline。v2 只有在 `/Users/luhui/Downloads/测试` 的 86 个去重样本上 A/B 明确胜出，才允许替换当前实验入口；否则保留失败证据并丢弃 v2 路线，不回到单图 residual 补丁循环。

## Key Changes

- 新增独立 v2 工具和测试：
  - `services/backend-python/tools/psd_like_v2_vector_surface_experiment.py`
  - `services/backend-python/tools/psd_like_v2_batch_eval.py`
  - `services/backend-python/tests/test_psd_like_v2_vector_surface.py`
- v2 从原图直接提取可矢量化 surface，按钮、卡片、输入框、栏背景优先生成 `ShapeLayer + TextLayer`。
- raster 只作为 fallback，用于照片、头像、商品图、复杂插画、无法可靠矢量化的区域。
- 第一版只做 solid fill + rounded rectangle；stroke、gradient、shadow、Telea/LaMa/PatchMatch 后置。
- OpenCV/contour 允许受控实验，但第一实现不新增依赖；若本机已有 `cv2`，可加 `--contour-engine opencv` 作为可选分支。新增 `opencv-python-headless` 必须单独 stage 和 commit。

## Implementation Stages

### Stage 1: Plan And Baseline

- 落本文档并提交。
- 基线事实：
  - `uv run pytest -q` 在 `services/backend-python` 通过。
  - v1 对 `/Users/luhui/Downloads/测试` 去重 86 case 可全量跑通。
  - v1 已知问题：按钮从 raster promote 回 shape 后，仍可能引入 residual/inpaint 和视觉退化。

### Stage 2: Vector Surface Candidate Extraction

- 新建 v2 工具，复用 v1 的 OCR 读取、bbox、text mask、preview/DSL 输出思路，但不复制 v1 的 residual 修补路径。
- 在 OCR text mask 外寻找颜色稳定、低纹理、连通的 surface。
- 输出 `vector_surfaces.v1.json`、`surface_overlay.png`、`surface_diagnostics.md`。
- 候选必须记录 `bbox`、`fill`、`cornerRadius`、`confidence`、`containedTextIds`、`reason`。
- 接受条件必须基于物理证据：文本包含、padding、非文字主色稳定、面积非整页、低复杂度。

### Stage 3: Shape Ownership Planner

- accepted vector surface 直接生成 shape layer，不生成按钮整块 raster asset。
- OCR text 继续是唯一文本权威，不允许由 shape 或模型改写。
- raster fallback 不得覆盖已被 vector surface 拥有的背景区域；不得覆盖 OCR text，除非作为复杂图片 fallback 并写明 text knockout diagnostics。
- 输出 `layer_stack.v2.json`、`draft_runtime.v2.dsl.v1_0.json`、`preview.v2.html`、`draft_preview.v2.png`、`ownership_report.v2.json`。

### Stage 4: A/B Batch Runner

- 新增 v2 batch eval，对同一输入同时跑 v1 和 v2：

```text
v1/<case>/
v2/<case>/
ab_summary.json
ab_summary.md
regression_ledger.md
source_v1_v2_contact_sheet.png
```

- 固定输入目录：`/Users/luhui/Downloads/测试`。
- 固定 OCR cache：`/Users/luhui/Downloads/psd_like_ocr_cache_test`。
- 对比指标：DSL valid、failure types、text/shape/raster counts、asset count、raw text overlap、knockout count、full-page raster、tiny fragments、visualMae、visualDiff30Ratio、improved/regressed cases。

### Stage 5: Optional Contour Trial

- 只有 v2 solid surface 在圆角拟合上明显不足时，才进入 contour trial。
- contour 只作用于 already-detected local surface crop，不做全图 Canny。
- OCR mask 必须先移除文字边缘。
- contour 只能辅助 shape boundary / radius，不创建文本、asset 或最终 DSL 结构。
- 如果 contour 误吞图片、shape 飘移或 failure 增加，记录失败并停止，不继续打补丁。

## Test Plan

- Unit tests:
  - OCR text mask 不生成 shape。
  - solid rounded button + OCR 生成 ShapeLayer + TextLayer，且无按钮整块 raster asset。
  - high texture photo containing text 不被误判为 shape。
  - card-like flat surface 可生成 shape，但不能吃掉内部照片。
  - full-page background 不生成 visible full-page backing。
  - cornerRadius 对圆角矩形有效，对方形接近 0。
  - raster fallback 不覆盖 vector-owned control background。

- Local checks:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/backend-python
uv run pytest -q
python -m py_compile tools/psd_like_v2_vector_surface_experiment.py tools/psd_like_v2_batch_eval.py app/*.py
```

- Real A/B:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/backend-python
uv run python tools/psd_like_v2_batch_eval.py \
  --input-dir /Users/luhui/Downloads/测试 \
  --out /Users/luhui/Downloads/psd_like_v2_ab_eval_test_all \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test
```

- DSL validation:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma
pnpm --filter @image-figma/dsl-schema run build
node --input-type=module -e "import { validateDraftRuntimeDSL } from './packages/dsl-schema/dist/index.js'; /* validate every v2 draft_runtime */"
```

- Final checks:

```bash
git diff --check
git status --short --branch
```

## Decision Gate

v2 只有满足以下条件才算赢：

- 86/86 case 不崩。
- DSL valid = 100%。
- `rawTextOverlapRaster` 平均值低于 v1。
- `rasterTextKnockoutCount` 平均值低于 v1。
- `assetCount` 不高于 v1。
- `visualMae` 平均值不能系统性变差，默认门槛：`v2_avg <= v1_avg + 0.05`。
- 最坏视觉退化 case 必须有 ledger，且不是 shape 误吞照片。
- 反特化检查通过：无样本名、路径、文案、品牌、固定坐标、固定 bbox、固定屏幕尺寸规则。

## Stop Conditions

- 同一根因连续三次修复仍失败。
- 每次修复改善一类 case 同时明显退化另一类 case。
- 只能靠单样本规则通过。
- 需要公共 DSL/API 合同变更。
- 依赖或验证不可用。

命中 stop condition 时，提交 blocker/failure report，不继续夜间漂移。
