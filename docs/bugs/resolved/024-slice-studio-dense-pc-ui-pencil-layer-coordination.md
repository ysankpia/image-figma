# Bug: Dense PC UI screenshots degrade in Slice Studio Pencil layer coordination

- 状态：resolved
- 创建日期：2026-06-12
- 解决日期：2026-06-12
- 影响范围：`apps/slice-studio` 的 `project.zip/design.pen` 导出，尤其是密集 PC/Web UI 截图或带检测标注的设计图

## Summary

Slice Studio 当前导出链路在普通移动端 UI 图上基本可用，但在信息密度很高的 PC/Web 工作台截图上，会出现 Pencil 预览视觉质量明显下降。

本次真实样本是：

```text
project_mqar9qpo_93b911d9
originalName: 09-pc-platform-meta-template.png
source image: 1536 x 1024
exported package: /Users/luhui/Downloads/project_mqar9qpo_93b911d9-project
user exported Pencil preview: /Users/luhui/Downloads/P1.png
```

导出的 `.pen` 结构本身没有布局报错，但视觉上出现大字号文字、错位文字、重复文字和局部脏乱。当前判断：这不是单个 Pencil schema 错误，也不是 AI 画框完全失效，而是源图信息密度过高时，三套机制没有充分协同：

```text
remainder visual layer
+ AI/manual slice image layers
+ OCR/M29 editable text layers
```

三者各自都在工作，但对密集 PC UI 场景的 ownership、z-order、text knockout、OCR text replay 和已带标注的源图没有形成稳定合同。

## Reproduction

1. 在 Slice Studio 中打开项目：

   ```text
   project_mqar9qpo_93b911d9
   ```

2. 页面原图为生成的 PC 端工作台 UI 图：

   ```text
   09-pc-platform-meta-template.png
   1536 x 1024
   ```

3. 该图本身已经包含大量视觉信息：

   - 顶部工具栏按钮和文字；
   - 左侧页面列表；
   - 中央画布和商品卡片；
   - 右侧资产列表与详情面板；
   - 底部批处理进度面板；
   - 蓝色 AI/asset 检测框和标签；
   - 大量小字号英文 UI 文案。

4. 在 Review Workbench 中用 AI 画框并导出 `project.zip`。

5. 打开 `design.pen`，或从 Pencil 导出预览图 `/Users/luhui/Downloads/P1.png`。

6. 观察到 Pencil 预览出现明显视觉污染：

   - 顶部 `Undo`、`Pan`、`Zoom In/Out` 等文字变得过大；
   - 部分文字和原图文字重叠；
   - 右侧 assets/details 区域出现浅色大字叠层；
   - 左侧页面列表和底部进度区文字有错位/重影；
   - 蓝色检测框、切片标签、OCR 文本和原图内容混在一起。

## Observed Evidence

已用 Pencil MCP 和导出包检查确认：

- `design.pen` 顶层 frame 尺寸为 `1536 x 1024`。
- `snapshot_layout` 未报告结构性 layout problem。
- 导出包含：

  ```text
  assets/originals/P1.png
  assets/visible/remainders/P1/remainder.png
  assets/visible/slices/P1/slice_0001.png ... slice_0036.png
  design.pen
  manifest.json
  project.json
  ```

- `manifest.json` 中当前页：

  ```text
  sliceCount: 36
  ocr.provider: baidu_ppocrv5
  ocr.status: ok
  sourceLineCount: 219
  textLayerCount: 208
  ```

- AI/manual slice 结果包括：

  - 8 个较大的商品图/服装图 slice；
  - logo、search icon、account icon 等小图形；
  - 多个小 marker、checkbox/control fragment；
  - 左侧页面缩略图也被切成 slice。

- Pencil 节点层级为：

  ```text
  page_0001__remainder     z: 0
  page_0001__slice_0001..0036
  page_0001__text_0001..0208
  ```

- 多个 OCR text node 的字号/内容在密集 PC UI 上不稳定，例如：

  ```text
  Pan        fontSize ~= 27.1
  Undo       fontSize ~= 26.2
  Zoom In    fontSize ~= 28.5
  Zoom Out   fontSize ~= 28.5
  Hide       fontSize ~= 23
  Minimize   fontSize ~= 20.7
  QFit 100%  OCR merged icon/text
  ```

- `remainder.png` 在当前导出合同下会处理 slice 区域和 OCR text region，因此它不是简单完整原图；再叠加大量 OCR text node 后，视觉偏差被放大。

## Root Cause

根因不是“某一个模型突然坏了”，而是密集 PC UI 输入触发了当前 Slice Studio handoff 合同的协同缺口。

当前导出链路假设：

```text
source screenshot
-> confirmed visual slices
-> remainder cleanup
-> OCR/M29 text reconstruction
-> Pencil layer stack
```

这个假设在信息密度较低、文字块较少、视觉资产边界清楚的移动端 UI 上相对稳定。但 PC/Web 工作台截图同时具备以下条件：

- 文本数量极多，OCR 生成 200+ text layers；
- UI 控件密度高，小按钮、小 icon、小标签、小数字密集分布；
- 源图中已经存在蓝色检测框和 asset 标签；
- AI slice 会切出商品图、icon、marker、缩略图等多种粒度；
- OCR text replay 的字体、字号、bbox、颜色不可能完全还原源图；
- remainder、slice、OCR text 三方都可能对同一局部像素区域产生可见影响。

因此，三套机制各自合理，但合成后没有统一 ownership/arbitration 策略，导致视觉预览被污染。

## Non-Root Causes

目前不要把这个问题误判为：

- Pencil 文件无法打开；
- `.pen` layout schema 错误；
- AI 画框接口失败；
- OCR provider 完全不可用；
- 保存逻辑或 SQLite 数据丢失；
- 单纯因为图片尺寸是 `1536 x 1024`。

已知 Pencil layout 检查没有报结构问题，API 项目状态也能读到 1 页、36 个 slices。

## Fix

在 Slice Studio 当前主线实现第一版文字/图像所有权仲裁，没有关闭 OCR，也没有恢复旧 Python/Go 导出链路。

实现点：

- 在 `apps/slice-studio/server/text-reconstruction.ts` 增加 `slice_studio_text_ownership.v1`。
- 每条 OCR/M29 文字在生成 Pencil TextLayer 前先分类：
  - `editable_text`：生成可见 TextLayer，并参与 remainder text knockout；
  - `raster_preserve`：保留在 raster/remainder 中，不生成可见 TextLayer，不参与 text knockout；
  - `skipped`：记录为跳过，不生成可见 TextLayer。
- 密集文字页面中，极小 OCR 行和生成式检测标注文本降级为 `raster_preserve`，例如 `img-11`、`Ing-01`、`g-16`。
- M29 物理框如果明显大于 OCR 行，说明它更像控件/组合区域而不是文字本身，退回 OCR bbox 再做字号计算。
- 多条 OCR 行共享同一个 M29 物理框时，退回各自 OCR bbox，避免 `Zoom In` / `Zoom Out` 共享同一个大框。
- local foreground refinement 同样拒绝过宽物理框，避免局部前景把按钮/icon 边界吃进文字框。
- Manifest OCR 元数据增加：

  ```text
  rasterPreservedTextCount
  skippedTextCount
  ownershipPolicy
  ```

没有做的事：

- 没有关闭 OCR。
- 没有按样本坐标、文件名或具体文案硬编码。
- 没有修改 AI prompt、SQLite、API、Pencil schema、前端 UI 或旧服务。
- 没有实现 per-M29 crop OCR padding/upscale/grayscale；当前主线不是这个 OCR 路径，这部分保留为后续实验方向。

## Regression Guard

新增/保留回归保护：

- M29 物理框正常匹配 OCR 文本时，仍使用 M29 bbox 生成可编辑 TextLayer。
- M29 物理框过宽或被多条 OCR 行共享时，退回 OCR bbox，避免按组合控件框算字号。
- 被 confirmed manual slice 覆盖的 OCR 文本仍不会生成 TextLayer。
- 生成式 marker label 保留为 raster，不生成可见 TextLayer。
- 普通 OCR 文本仍生成可编辑 TextLayer，并参与 text knockout。
- 过大 OCR 噪声行继续被过滤。

修复时至少需要覆盖密集 PC/Web UI 图，而不只覆盖移动端 UI 图。建议届时把以下样本纳入验证材料：

```text
project_mqar9qpo_93b911d9
/Users/luhui/Downloads/P1.png
/Users/luhui/Downloads/project_mqar9qpo_93b911d9-project
```

## Validation Evidence

诊断证据：

- Pencil MCP 能打开 `design.pen`。
- Pencil `snapshot_layout` 未报告 layout problem。
- 导出包检查确认 `sliceCount=36`、`textLayerCount=208`、`sourceLineCount=219`。
- 用户从 Pencil 导出的 `/Users/luhui/Downloads/P1.png` 直观看到文字重影、字号异常和视觉污染。

修复验证：

```bash
pnpm --dir apps/slice-studio exec vitest run tests/pencil-exporter.test.ts
pnpm --dir apps/slice-studio run check
pnpm --dir apps/slice-studio run build
git diff --check
```

结果：

```text
tests/pencil-exporter.test.ts: 18 passed
pnpm check: 8 test files / 54 tests passed
pnpm build: passed
git diff --check: passed
```

真实项目重新导出：

```text
POST /api/projects/project_mqar9qpo_93b911d9/export-project
assetCount: 36
pageCount: 2
```

第 1 页密集 PC UI 修复后：

```text
sourceLineCount: 219
textLayerCount: 116
rasterPreservedTextCount: 103
skippedTextCount: 0
ownershipPolicy: slice_studio_text_ownership.v1
```

对比关键异常：

```text
Undo       26.2 -> 9.8
QFit 100%  19.3 -> 10.5
Pan        27.1 -> 16.1
Zoom In    28.5 -> 14.7
Zoom Out   28.5 -> 17.5
```

第 2 页普通移动 UI 没被密集页规则误伤：

```text
sourceLineCount: 84
textLayerCount: 84
rasterPreservedTextCount: 0
```

Pencil MCP 对重新生成的 `design.pen` 截图检查确认：第 1 页不再出现修复前那种大面积 OCR TextLayer 污染；蓝色检测标注和极小密集文字不再作为独立可见文字层叠加。

## Prevention Notes

后续修复前需要避免两个误区：

- 不要只凭这一个样本硬编码坐标、文案、文件名、主题或页面类型。
- 不要把问题简化成“关掉 OCR”或“多切/少切 AI 框”这种单点开关；真正问题是密集 UI 下 remainder、slice、OCR text layer 的协同合同。

残余边界：

- 如果源图本身已经带蓝色检测框/标签，这些像素仍会作为原图视觉内容保留；本修复只阻止它们被二次生成为可见 OCR TextLayer。
- per-M29 crop OCR 的 padding/upscale/grayscale 仍然是后续可做的识别质量优化，不是本次主线修复。
