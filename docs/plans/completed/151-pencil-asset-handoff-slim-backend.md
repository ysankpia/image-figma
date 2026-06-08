# 151 Pencil Asset Handoff Slim Backend

Status: completed

## Summary

新增 `services/pencil-asset-backend/`，把产品目标收敛为：

```text
1..N UI screenshots
-> YOLO/M29/PSD-like/OCR evidence
-> image/icon candidates
-> Canvas Review
-> manual_slices.v1.json
-> PNG assets
-> pencil-handoff project.zip
-> selected-assets.zip
```

新服务只交付工程师真正需要的 image/icon PNG 资产，并把资产按原坐标放进 Pencil 项目。旧 `services/pencil-python-backend` 不改主线逻辑，只作为实现参考。

## Key Decisions

- `manual_slices.v1.json` 是唯一最终真相源。
- v1 只导出 `image` 和 `icon`，全部为 PNG。
- 不做 SVG、复杂透明抠图、自动 Figma tree、Draft graph、Codia-like tree、TextLayer knockout。
- YOLO 必需配置；M29/PSD-like/OCR 是辅助证据，失败记录 warning。
- 输出单一模式 `pencil-handoff`，不输出 `clean-editable` / `visual-fidelity` / `visual-ocr`。

## Implementation Scope

- 新建 FastAPI 服务、Canvas review、项目存储、合同校验、PNG 裁图、Pencil `.pen` ZIP、selected assets ZIP。
- 新增 YOLO/M29/PSD-like/OCR evidence runner 的最小可用实现。
- 新增 `make check` 和 `make asset-acceptance`。
- 新增 API/单元测试和真实样例验收脚本。
- 更新当前代码地图、legacy inventory、环境变量或 README 中的相关导航。

## Validation

```bash
cd services/pencil-asset-backend
make check
make asset-acceptance IMAGE=/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png OUT=/Volumes/WorkDrive/pencil-exports/asset-acceptance-151/tencent
cd ../..
git diff --check
git status --short --branch
```

## Completion Evidence

Implemented:

- 新增 `services/pencil-asset-backend/` FastAPI 服务。
- 新增 YOLO/M29/PSD-like/OCR evidence runner。
- 新增 image/icon candidate fusion、Canvas Review、`manual_slices.v1.json` 校验。
- 新增 `pencil-handoff` 单模式 `.pen` 导出、`project.zip`、`selected-assets.zip`、contact sheet。
- 新增 `scripts/asset_acceptance.py`、`make check`、`make asset-acceptance`。
- 更新 README、current code map、legacy inventory、环境变量文档和 docs index。

Validation completed:

```bash
cd services/pencil-asset-backend
make check
```

Result:

```text
6 passed, 1 warning
```

Single real sample:

```bash
make asset-acceptance \
  IMAGE=/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png \
  OUT=/Volumes/WorkDrive/pencil-exports/asset-acceptance-151/tencent
```

Result:

```text
sample_01_腾讯动漫_018_1440: pages=1 candidates=194 selected=3 exported=3 pngs=3 badRefs=0 missingRefs=0
```

Batch real samples:

```bash
uv run python scripts/asset_acceptance.py \
  --base-url http://127.0.0.1:8110 \
  --input "/Users/luhui/Downloads/PencilBridge_Admin_UI_XcodeDark/01_UI_Pages" \
  --input "/Users/luhui/Downloads/dorm_selection_ui_assets 2" \
  --out /Volumes/WorkDrive/pencil-exports/asset-acceptance-151/batch \
  --project-name "Pencil Asset Batch"
```

Result:

```text
sample_01_01_UI_Pages: pages=6 candidates=3587 selected=18 exported=18 pngs=18 badRefs=0 missingRefs=0
sample_02_dorm_selection_ui_assets_2: pages=6 candidates=292 selected=16 exported=16 pngs=16 badRefs=0 missingRefs=0
```

Chrome DevTools smoke:

```text
workspace loaded
review loaded
project/candidates/manual-slices/source requests returned 200
favicon returned 204
console errors/warnings: none
screenshot: /Volumes/WorkDrive/pencil-exports/asset-acceptance-151/tencent/chrome-review-final.png
```

Final checks:

```bash
git diff --check
git status --short --branch
```
