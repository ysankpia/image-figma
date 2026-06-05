# 148 Assisted Slice Workspace Browser Acceptance

Status: completed
Created: 2026-06-05 20:22 +0800
Completed: 2026-06-05 20:42 +0800

## Objective

用 Chrome DevTools 对 Pencil Assisted Slice Workspace 做真实浏览器验收，只修验收中暴露的 P0/P1 体验和稳定性问题。验收通过后提交。

当前主线不变：

```text
1..N images
-> candidates.v1.json
-> HTML Canvas assisted slice workspace
-> user-confirmed manual_slices.v1.json
-> export-preview
-> project.zip + selected-assets.zip
```

## Scope

Allowed:

- 启动 `services/pencil-python-backend` 本地服务。
- 用 Chrome DevTools 跑 `/api/pencil/slice-projects/workspace` 和 `/review`。
- 修 P0/P1 级浏览器体验问题：页面崩溃、点击无效、状态丢失、刷新不一致、导出按钮/链接不明确、跨页定位错误、缩略图不加载、批量操作误删、保存反馈错误。
- 修改 `services/pencil-python-backend` 的 plain HTML + Canvas + native JS、API 测试、验收文档。

Forbidden:

- P3/P4 或更后续 backlog。
- React/Vue/正式前端重构。
- YOLO/model 作为最终裁判。
- 全自动 ownership 裁判回归。
- Codia/Draft/Go Draft/Figma plugin 路线恢复。
- 默认透明底。
- 按样例名、路径、固定坐标、固定文字、品牌或页面结构写特化逻辑。

## Browser Acceptance Flow

Use Chrome DevTools to verify:

```text
open /api/pencil/slice-projects/workspace
create a project from real image input
enter review
box-select visible candidates
batch add candidates
reject and restore candidates
switch page when project has multiple pages
search selected assets
click selected asset to focus canvas item
batch rename display names
batch delete visible selected assets
save
refresh review
confirm manual slices, rejected candidates, filters, active page, and selected-assets panel state survived
build export preview
export
confirm project.zip and selected-assets.zip links are visible and clickable
```

## Samples

Primary browser sample:

```text
/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png
```

Optional multi-page browser sample when needed:

```text
/Users/luhui/Downloads/dorm_selection_ui_assets 2
```

Script regression samples:

```text
/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png
/Users/luhui/Downloads/PencilBridge_Admin_UI_XcodeDark/01_UI_Pages
/Users/luhui/Downloads/dorm_selection_ui_assets 2
```

## Acceptance Criteria

- Browser flow completes without JS console errors that break interaction.
- Review canvas renders source image and candidate/selected overlays.
- User can create/select/draw/update/delete slices and save them.
- Refresh does not lose saved `manual_slices.v1.json` or `review_state.v1.json` state.
- Export preview and final export succeed.
- Both download links are visible after export.
- Script acceptance reports `badRefs=0` and `missingRefs=0`.
- `make check`, `git diff --check`, and `git status --short --branch` pass before final commit.

## Commands

```bash
cd services/pencil-python-backend
PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=psdlike OCR_PROVIDER=none \
uv run uvicorn app.main:app --host 127.0.0.1 --port 8100

make check
make slice-acceptance IMAGE=/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png OUT=/Volumes/WorkDrive/pencil-exports/slice-acceptance-148/tencent-comic
uv run python scripts/slice_workspace_acceptance.py \
  --base-url http://127.0.0.1:8100 \
  --input "/Users/luhui/Downloads/PencilBridge_Admin_UI_XcodeDark/01_UI_Pages" \
  --input "/Users/luhui/Downloads/dorm_selection_ui_assets 2" \
  --out /Volumes/WorkDrive/pencil-exports/slice-acceptance-148/batch
git diff --check
git status --short --branch
```

## Stop Conditions

- The observed problem requires P3/P4 scope or a frontend rewrite.
- The observed problem is automatic candidate quality rather than browser/workspace behavior.
- The fix would require restoring a forbidden route.
- The fix cannot be isolated safely from unrelated user-owned changes.

## Browser Evidence

Chrome DevTools real browser acceptance was run against:

```text
http://127.0.0.1:8100/api/pencil/slice-projects/workspace
http://127.0.0.1:8100/api/pencil/slice-projects/{projectId}/review
```

Primary browser sample:

```text
/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png
```

Observed flow:

```text
workspace upload -> create project -> review loaded
candidate box selection -> bulk add candidates -> manual slice add
reject candidate -> restore -> reject one candidate for persistence check
save -> refresh -> 9 selected slices and 1 rejected candidate restored
search selected assets -> batch rename visible result -> delete visible result only
export preview -> export -> project.zip and selected-assets.zip visible
export/download links fetched in browser
multi-page project opened -> selected asset focus switched from page_0001 to page_0002
```

One P1 was found:

```text
After building export-preview and then running final export, the visible export-preview/index.html
and export-preview/contact-sheet.png links returned 404 because final export cleared paths.output.
```

Fix:

```text
export_manual_slice_project now regenerates export-preview during final export and records
exportPreview / exportPreviewUrl in the returned manifest.
```

Post-fix browser link check:

```text
project.zip: 200 application/zip
selected-assets.zip: 200 application/zip
export-preview/index.html: 200 text/html
export-preview/contact-sheet.png: 200 image/png
console errors after reload: 0
```

## Script Evidence

Commands:

```bash
cd services/pencil-python-backend
make check
make slice-acceptance IMAGE=/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png OUT=/Volumes/WorkDrive/pencil-exports/slice-acceptance-148/tencent-comic PROJECT_NAME="Slice Acceptance 148 Tencent"
uv run python scripts/slice_workspace_acceptance.py \
  --base-url http://127.0.0.1:8100 \
  --input "/Users/luhui/Downloads/PencilBridge_Admin_UI_XcodeDark/01_UI_Pages" \
  --input "/Users/luhui/Downloads/dorm_selection_ui_assets 2" \
  --out /Volumes/WorkDrive/pencil-exports/slice-acceptance-148/batch \
  --project-name "Slice Acceptance 148 Batch"
```

Results:

```text
make check: 35 passed

tencent-comic:
passed=1 failed=0 missingSample=0
pages=1 candidates=63 selected=3 preview=3 exported=3 pngs=3 badRefs=0 missingRefs=0

batch:
passed=2 failed=0 missingSample=0
sample_01_01_UI_Pages: pages=6 candidates=776 selected=18 preview=18 exported=18 pngs=18 badRefs=0 missingRefs=0
sample_02_dorm_selection_ui_assets_2: pages=6 candidates=68 selected=11 preview=11 exported=11 pngs=11 badRefs=0 missingRefs=0
```
