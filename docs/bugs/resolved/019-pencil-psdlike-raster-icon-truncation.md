# Bug: Pencil PSD-like raster icon truncated before .pen export

- 状态：resolved
- 创建日期：2026-06-03
- 影响范围：`services/pencil-python-backend` 使用 `boundarySource=psdlike|hybrid` 时的局部 raster asset

## Summary

`/Users/luhui/Downloads/兼职` 导出的 page_0003 指标卡片里，原图是完整圆形图标，
但 Pencil 预览只显示下半截图标。

## Reproduction

1. 查看 `/Volumes/WorkDrive/pencil-exports/jianzhi-psdlike-boundary-realocr-v2/clean-editable/design.pen`。
2. 聚焦 page_0003 的 `今日提交数` / `今日完成数` 两个指标卡片。
3. 对比 source、PSD-like draft、Pencil preview 和最终 `.pen` 节点。

## Root Cause

PSD-like 边界分解阶段已经丢失图标上半部分：

```text
source icon bbox ≈ 74x75 / 73x73
PSD-like raster bbox = 72x48 / 80x48
.pen rectangle bbox = 72x48 / 80x48
```

Pencil exporter 只是忠实输出 PSD-like 给出的短 raster crop。根因不是 Pencil
渲染器、Figma importer、OCR 或 TextLayer safe bounds。

## Fix

在 `app/psdlike_adapter.py` 中为 bounded local raster 添加 source-based
boundary repair：

- 在 `source.png` 的局部窗口中估计背景。
- 生成前景差异 mask。
- 从当前 raster bbox 内的前景像素出发找连通域。
- 如果连通域越过 PSD-like bbox 且面积/尺寸/OCR overlap 合理，从 `source.png`
  重裁完整 bbox。
- 在 `compileHints.rasterBoundaryRepair` 记录原始 bbox、修复 bbox 和策略。

## Regression Guard

新增测试 `test_psdlike_adapter_repairs_truncated_local_raster_from_source`：

- 构造完整圆形图标 source。
- PSD-like raster 只给下半截 bbox/crop。
- adapter 必须恢复完整局部图标 bbox 并输出对应 crop。

## Validation Evidence

- `cd services/pencil-python-backend && uv run python -m py_compile $(find app tests -name '*.py' | sort)`
- `cd services/pencil-python-backend && uv run pytest -q`
- Real page_0003 adapter replay:
  `/Volumes/WorkDrive/pencil-exports/page0003-raster-repair-adapter-check`
- Repaired bboxes:
  - `psd_raster_0021`: `112,512,72,48 -> 108,482,79,83`
  - `psd_raster_0022`: `520,512,80,48 -> 524,482,78,80`
- Pencil CLI preview comparison:
  `/Volumes/WorkDrive/pencil-exports/page0003-raster-repair-single-check/preview/source_vs_fixed_metrics.png`

## Prevention Notes

不要把 PSD-like raster bbox 当作不可质疑的源真相。它是边界分解结果，不是源像素。
局部 raster crop 如果存在可见前景连通到 bbox 外，必须回 `source.png` 验证并修复。
