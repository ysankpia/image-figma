# M31.1.1 Fast M31 Fallback Crop From Decoded Pixels

- 状态：active
- 创建日期：2026-05-20
- 负责人：未指定

## Goal

M31 upload diagnostics 在真实上传样本中暴露出性能 bug：`m31_reconstruction` 曾单独耗时 116s，占完整链路 84.8%。根因是 M31 已经解码 source PNG 为 `PngPixels`，但每个 reconstruction unit 生成 fallback crop 时又通过 `crop_png()` 重新 parse/decompress/unfilter 整张 PNG。

本阶段只修 M31 fallback crop 的 source object：

```text
decode source PNG once
-> crop each unit from PngPixels.rows
-> encode crop PNG
```

## Scope

包含：

- 新增 decoded-pixels crop helper。
- M31 unit fallback asset 改用已解码 `PngPixels`。
- 移除 M31 对 compressed source PNG bytes 的 unit crop 依赖。
- 增加功能等价和防回归测试。
- 同步文档和 ADR。

不包含：

- 不改 M31 grouping/ownership 规则。
- 不改 M31 tree/report schema。
- 不改 M30 DSL、Renderer、插件 UI。
- 不做异步 M31、后台队列、M32/M33/M34。
- 不删除 `crop_png()`，其他模块仍可使用。

## Acceptance

- M31 fallback crop 不再调用 `crop_png()`。
- M31 fallback assets 仍全部生成。
- fallback crop PNG 尺寸和像素内容来自对应 `PngPixels` 区域。
- M31 report invariants 不变：
  ```text
  createdDetectionBBoxCount = 0
  permissionViolationCount = 0
  rootLeafPrimitiveCount = 0
  unitFallbackCoverage = 1.0
  forbiddenHitCount = 0
  ```
- M31 upload diagnostics enabled 时仍生成 `m31/` tree/report/fallback assets。
- M31 upload diagnostics disabled、optional failure、strict failure 行为不变。
- 同类真实图手动 smoke 中 `m31_reconstruction` 不再接近 116s，目标 < 10s。

## Validation

Focused:

```bash
cd backend
uv run pytest tests/test_png_tools.py tests/test_reconstruction_ui_tree.py tests/test_m30_upload_pipeline.py -q
```

Full:

```bash
cd backend && uv run pytest -q
pnpm run check
git diff --check
git status --short
```

Manual smoke:

```bash
cd backend
M30_PREVIEW_PROFILE=production \
M31_UPLOAD_DIAGNOSTICS_ENABLED=true \
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Upload the same class of PNG and inspect `stage_timings.json`.
