# 产品愿景

Image-to-Figma Design 当前分支要解决的问题很窄：把一张或多张清晰 PNG 截图/设计稿，快速转换成可人工确认的 Pencil/Figma 交付包。

## 一句话定义

用户上传 1..N 张图片后，Pencil Python Backend 生成候选切片；用户在 HTML Canvas 工作台确认或手动画框；`manual_slices.v1.json` 成为最终真相源；系统导出 `project.zip` 和 `selected-assets.zip`。

旧 Go Draft backend / Draft Runtime DSL / Renderer 路线是历史自动化方向，不是当前可交付产品主线。

## 目标用户

- 设计师：把截图或旧稿快速转成可在 Pencil/Figma 里继续整理的项目包。
- 设计工作室：降低重复复刻页面的时间成本。
- 前端开发者：从参考截图中确认并导出真实开发会用到的切图资源。
- 独立开发者：快速把 App、小程序或简单后台截图变成可交付素材包。

## 一期成功判断

一期不追求商业化完整产品。它只证明这条链路值得继续投入：

```text
1..N PNG 上传
-> 自动候选
-> Canvas 工作台人工确认
-> manual_slices.v1.json
-> Pencil project.zip
-> selected-assets.zip
```

成功标准是：

- 大部分样例能创建候选，不因为局部复杂区域整页失败。
- 用户能选择候选、手动画框、调整、删除、命名并保存。
- selected slices 能按 source image 坐标 1:1 放回 `.pen`。
- `project.zip` 和 `selected-assets.zip` 可复跑验收。
- `.pen` 内 visible asset refs 无绝对路径、无 `source.png`、无 raw crops、无 masks、无 debug、无 `../`。
- 失败时能定位到创建、保存、预览、导出或 ZIP 合同阶段。

## 最高原则

先稳定交付，再追求自动化更好。

一期优先级：

1. 稳定生成。
2. 用户确认后的切片 1:1 回填。
3. 交付包合同可靠。
4. 候选质量逐步提升。
