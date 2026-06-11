# 产品愿景

Image-to-Figma Design 当前要解决的问题很窄：把一张或多张 UI 截图/设计稿，快速转换成用户可修、可确认、可交付的 Pencil/Figma 项目包和前端切图资源。

## 一句话定义

用户上传 1..N 张图片后，Slice Studio 保存原图，用户手动画框或使用 AI 批量画框，然后人工调整确认；保存后的 slice 成为最终导出 truth source；系统导出 `assets.zip` 和 `project.zip/design.pen`。

旧 Go Draft backend、Draft Runtime DSL、Renderer、Figma plugin、Python Pencil backend 和 Codia-like 路线都是历史/参考/延后资产，不是当前默认产品主线。

## 目标用户

- 设计师：把截图或旧稿快速转成可在 Pencil/Figma 里继续整理的项目包。
- 设计工作室：批量处理多张设计稿，降低重复切图和 handoff 成本。
- 前端开发者：从参考截图中确认并导出真实开发会用到的图片/icon/视觉资产。
- 独立开发者：快速把 App、小程序、Web 或后台截图变成可继续编辑和交付的素材包。

## 当前成功判断

当前不追求商业化完整产品。它证明这条链路：

```text
1..N images
-> Slice Studio project workspace
-> manual / AI-assisted slice boxes
-> saved slices in SQLite
-> assets.zip
-> project.zip / design.pen
```

成功标准是：

- 多页项目能创建、恢复、重命名、重排和删除页面。
- 用户能手动画框、调整、删除、命名并保存。
- AI 能作为批量画框工具提供稳定的初稿，漏切少于少切。
- `rect | subject | card` 三种 cut mode 能覆盖常见资产导出。
- exported slices 按 source image 坐标 1:1 放回 `.pen`。
- `assets.zip` 和 `project.zip` 可复跑验收。
- `.pen` 内 visible asset refs 无绝对路径、无 `source.png`、无 raw crops、无 masks、无 debug、无 `../`。
- OCR/M29 只增加 editable text handoff，不覆盖用户确认 slice。

## 最高原则

先稳定交付，再继续提升自动化。

优先级：

1. 用户确认后的 slice 能稳定保存和导出。
2. Pencil/Figma handoff 包合同可靠。
3. AI 画框减少用户手工成本，但不成为新的 truth source。
4. OCR/M29 提高文字可编辑性，但不重建 UI 结构。
5. 旧研究代码保留价值，但不再主导当前产品方向。
