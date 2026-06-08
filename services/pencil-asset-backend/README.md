# Pencil Asset Backend

瘦后端，只做 UI 截图中的工程资产 handoff：

```text
1..N UI screenshots
-> YOLO/M29/PSD-like/OCR evidence
-> image/icon candidates
-> Canvas Review
-> review_state.v1.json
-> manual_slices.v1.json
-> PNG assets
-> design.pen
-> project.zip + selected-assets.zip
```

这个服务不生成 Codia-like tree，不接 Draft graph，不调用 Figma plugin runtime，也不输出 `clean-editable` / `visual-fidelity` / `visual-ocr` 三套模式。v1 只交付 `image` 和 `icon` 两类 PNG 资产，并按原图坐标放进 Pencil handoff 项目。`.pen` 同时包含一个 source reference 层用于人工复核上下文，但 reference 不进入 `selected-assets.zip`。自动候选只是建议；错误候选的隐藏状态写入 `review_state.v1.json`，最终导出仍只看 `manual_slices.v1.json`。

## Environment

`PENCIL_ASSET_YOLO_MODEL` 是必需配置。M29/PSD-like/OCR 是辅助证据源；它们失败会记录 warning，但不会覆盖用户确认的 `manual_slices.v1.json`。

```bash
export PENCIL_ASSET_YOLO_MODEL=/Volumes/WorkDrive/Datasets/vins_rico_yolov8/VINS-RICO-UPLABS-ANDROID.v2i.yolov8/runs/detect/runs/detect/train/weights/best.pt
export PENCIL_ASSET_M29EXTRACT=/Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/backend-go/bin/m29extract
export PENCIL_ASSET_PSDLIKE_ROOT=/Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
export OCR_PROVIDER=none
```

Defaults:

```text
PENCIL_ASSET_STORAGE_ROOT=services/pencil-asset-backend/storage
PENCIL_ASSET_YOLO_CONF=0.18
PENCIL_ASSET_YOLO_IOU=0.45
PENCIL_ASSET_YOLO_IMGSZ=640
PENCIL_ASSET_YOLO_DEVICE=auto
PENCIL_ASSET_MAX_FILES=20
PENCIL_ASSET_MAX_UPLOAD_BYTES=10485760
```

## Run

```bash
cd services/pencil-asset-backend
uv sync
make serve
```

Open:

```text
http://127.0.0.1:8110/api/asset-projects/workspace
```

## API

```text
GET  /api/health
GET  /api/ready
POST /api/asset-projects
GET  /api/asset-projects
GET  /api/asset-projects/{projectId}
GET  /api/asset-projects/{projectId}/review
GET  /api/asset-projects/{projectId}/source/{pageId}
GET  /api/asset-projects/{projectId}/evidence
GET  /api/asset-projects/{projectId}/candidates
GET  /api/asset-projects/{projectId}/review-state
PUT  /api/asset-projects/{projectId}/review-state
GET  /api/asset-projects/{projectId}/manual-slices
PUT  /api/asset-projects/{projectId}/manual-slices
POST /api/asset-projects/{projectId}/export-preview
POST /api/asset-projects/{projectId}/export
GET  /api/asset-projects/{projectId}/download.zip
GET  /api/asset-projects/{projectId}/selected-assets.zip
```

## Review Interaction

Canvas Review uses source-image coordinates as the only saved geometry:

```text
left click candidate        -> confirm as selected image/icon slice
Alt+left click candidate    -> hide wrong candidate
right click candidate       -> hide wrong candidate
blank drag                  -> draw missing slice manually
Delete/Backspace            -> delete active selected slice
```

Hidden candidates are persisted in `review_state.v1.json`. They do not enter
`manual_slices.v1.json`, `project.zip`, or `selected-assets.zip`. Use the Review
page buttons to show hidden candidates as gray dashed boxes or restore hidden
candidates for the current page.

## Output

`project.zip`:

```text
design.pen
assets/reference/page_0001/source.png
assets/visible/page_0001/slice_0001.png
manifest.json
manual_slices.v1.json
export-preview/contact-sheet.png
debug/pages/page_0001/manual_overlay.png
```

`selected-assets.zip`:

```text
page_0001/slice_0001.png
manifest.json
```

Hard contract:

- selected assets are cropped from `pages/page_XXXX/source.png`.
- `manual_slices.v1.json` is the final delivery truth source.
- `review_state.v1.json` is review UI state only.
- `.pen` deliverable slice refs must point to `./assets/visible/...`.
- `.pen` review-only source reference refs must point to `./assets/reference/page_XXXX/source.png`.
- `selected-assets.zip` must contain selected slices only; it must not contain source reference images.
- `.pen` must not reference absolute paths, debug assets, raw crops, masks, or `../`.

## Validation

```bash
cd services/pencil-asset-backend
make check
make asset-acceptance \
  IMAGE=/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png \
  OUT=/Volumes/WorkDrive/pencil-exports/asset-acceptance-151/tencent
```
