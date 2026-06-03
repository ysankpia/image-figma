# Bug: Pencil empty transparent page becomes black frame

- 状态：resolved
- 创建日期：2026-06-04
- 影响范围：`services/pencil-python-backend` 使用 `boundarySource=psdlike|hybrid` 时，PSD-like 没有产出任何 layer 的透明小 PNG / 局部素材输入

## Summary

`/Users/luhui/Downloads/生鲜主题/images` 批量导出中，部分 28x28、32x32 的透明 PNG 在
`clean-editable` / `visual-fidelity` / `visual-ocr` 预览里变成黑块或空白。

## Reproduction

1. 使用 `boundarySource=psdlike` 导出包含透明小 PNG 的项目。
2. 查看 `batch_001/page_0006` 一类页面。
3. 生成的 `.pen` frame 为 `fill=#000000`，`children=[]`。

典型输入：

```text
/Users/luhui/Downloads/生鲜主题/images/04cbb00fd2fdc25f2d33e7e4347991ca.png
```

该输入是 `RGBA 28x28`，带 alpha。

## Root Cause

PSD-like 对透明小素材没有产出可见 layer：

```text
RGBA source.png
-> PSD-like layer_stack layers=[]
-> Pencil evidence primitives=[]
-> single_page exporter only creates a frame
-> pageBackground inferred as #000000
-> .pen displays a black empty frame
```

根因不是 Pencil CLI、Figma importer、OCR 或 M29 主干。问题在 Pencil 单页导出层缺少
“空证据页必须保留完整源图 raster asset”的合同兜底。

## Fix

在 `app/exporter/single_page.py` 中新增 `empty_evidence_source_raster.v1` fallback：

- 如果 production document 没有任何 visible child，复制 evidence 目录里的 `source.png`
  到 `assets/visible/source_full.png`。
- 在页面内创建一个覆盖全画布的 image rectangle。
- frame 背景固定为 `#FFFFFF`，避免透明源图被黑底污染。
- `.pen` 仍禁止引用 `source.png`、raw crops、masks、debug 路径。
- manifest/report 记录 `sourceFallbackNodes`。

## Regression Guard

新增测试 `test_single_page_empty_transparent_evidence_falls_back_to_source_raster`：

- 构造 `RGBA 28x28` 透明源图。
- 构造空 `primitives=[]` 和空 replay layers。
- 三种 mode 都必须输出 `source_full_raster` visible asset。
- `.pen` 不允许出现 `source.png`。
- 输出 asset 必须保留 RGBA alpha。

## Validation Evidence

- `cd services/pencil-python-backend && uv run python -m py_compile $(find app tests -name '*.py' | sort)`
- `cd services/pencil-python-backend && uv run pytest -q`
- Real transparent PNG smoke:
  `/Volumes/WorkDrive/pencil-exports/transparent-alpha-fallback-fix-20260604/project.zip`
- Real batch_001 smoke:
  `/Volumes/WorkDrive/pencil-exports/shengxian-batch001-alpha-fallback-fix-20260604/project.zip`
- Pencil CLI preview:
  `/Volumes/WorkDrive/pencil-exports/shengxian-batch001-alpha-fallback-fix-20260604/preview/clean-editable.png`
- Before-bad pages now record `sourceFallbackNodes=1`:
  - `page_0006` / `04cbb00fd2fdc25f2d33e7e4347991ca.png`
  - `page_0012` / `0af64f67f508269e8088bbd1627294c9.png`

## Prevention Notes

边界分解没有产出 layer 不代表页面没有可见内容。导出层不能把空 evidence 解释成空设计稿；
必须回到源像素，输出完整 raster fallback，并保留可审计 manifest 标记。
