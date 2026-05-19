# ADR: Crop M31 Fallbacks From Decoded Pixels

- 状态：accepted
- 日期：2026-05-20

## Context

M31.1 接入 upload pipeline 后，真实样本显示 `m31_reconstruction` 单独耗时 116s。M31 入口已经把 source PNG 解码成 `PngPixels`，但 unit fallback asset 生成仍调用 `crop_png(source_png, region)`。

`crop_png()` 每次都会重新 parse PNG chunks、decompress IDAT、unfilter full image rows，再裁一小块。103 个 reconstruction units 就会重复解码整图 103 次。

## Decision

M31 fallback crop 的 source object 改为已解码 `PngPixels`。

新增 helper：

```text
crop_pixels_to_png(PngPixels, PngRegion) -> PNG bytes
```

M31 `add_unit()` 用该 helper 从 `context.pixels.rows` 裁剪 unit bbox，再用 `encode_rgb_png()` 写 crop PNG。

`crop_png()` 保留给其他需要从 compressed PNG bytes 直接裁剪的旧调用者。

## Consequences

好处：

- M31 source PNG 只解码一次。
- unit fallback crop 成本从 O(unit_count * full_image_decode) 降为 O(sum(unit_crop_pixels))。
- M31 diagnostics 可以重新打开做真实上传质量观测。

代价：

- `png_tools.py` 增加一个与 `crop_png()` 并列的 decoded-pixels crop helper。
- M31 依赖 `PngPixels` 作为 fallback crop source，未来如果要保留 alpha，需要另开阶段扩展像素模型；当前 M31 和 M30 路径已经使用 RGB pixels。

明确不做：

- 不改 M31 grouping。
- 不改 M31 schema。
- 不改 DSL、Renderer、插件。
- 不做异步 M31 或任务队列。
