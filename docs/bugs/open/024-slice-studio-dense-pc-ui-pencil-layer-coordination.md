# Bug: Dense PC UI screenshots degrade in Slice Studio Pencil layer coordination

- 状态：open
- 创建日期：2026-06-12
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

待定。

不要在本 bug 里先写解决方案。后续修复方向由用户提供；历史实验链路中已有相关处理经验，需要在实际动手前重新对齐。

## Regression Guard

待定。

修复时至少需要覆盖密集 PC/Web UI 图，而不只覆盖移动端 UI 图。建议届时把以下样本纳入验证材料：

```text
project_mqar9qpo_93b911d9
/Users/luhui/Downloads/P1.png
/Users/luhui/Downloads/project_mqar9qpo_93b911d9-project
```

## Validation Evidence

当前只记录 bug 事实，不验证修复。

已完成的诊断证据：

- Pencil MCP 能打开 `design.pen`。
- Pencil `snapshot_layout` 未报告 layout problem。
- 导出包检查确认 `sliceCount=36`、`textLayerCount=208`、`sourceLineCount=219`。
- 用户从 Pencil 导出的 `/Users/luhui/Downloads/P1.png` 直观看到文字重影、字号异常和视觉污染。

## Prevention Notes

后续修复前需要避免两个误区：

- 不要只凭这一个样本硬编码坐标、文案、文件名、主题或页面类型。
- 不要把问题简化成“关掉 OCR”或“多切/少切 AI 框”这种单点开关；真正问题是密集 UI 下 remainder、slice、OCR text layer 的协同合同。
