# 术语表

## Image-to-Figma Design

本项目名称。当前分支把 UI 截图或设计稿转换成用户确认后的 Pencil/Figma 交付包和前端切图资源。

## Slice Studio

当前产品主线。它从 1..N 张 UI 图创建本地项目，保存原图、页面和 SliceRecord，导出 `assets.zip` 与 `project.zip/design.pen`。

## SliceRecord

当前编辑和导出的 truth source。它记录 page、bbox、name、cut mode 等信息，保存在 Slice Studio SQLite 项目状态里。

## manual_ui_slices.v1

Slice Studio export manifest schema。它描述导出包里的页面、已确认 slices、源图和 package-local asset refs。

## AI Slice Boxes

Slice Studio AI 批量画框结果。AI 只返回短生命周期 bbox；前端把它们合并成普通 SliceRecord 并通过现有保存路径落库。

## Cut Mode

Slice Studio slice export mode：

```text
rect
subject
card
```

`rect` 是矩形裁切，`subject` 去掉局部背景保留主体，`card` 去掉外边背景并保留内部图文内容。

## OCR Text

OCR 提供 editable text content 和原始 bbox。OCR 不重建按钮、卡片、图标、图片或 Auto Layout。

## M29 Physical Evidence

从 PNG 像素提取的物理证据。在当前 Slice Studio 中，TypeScript M29 只服务 OCR text bbox placement。Go `m29extract` 是显式 fallback/reference。

## Pencil Project Package

Slice Studio 导出的 `project.zip`，内部包含 `design.pen`、manifest、project metadata、originals、remainders 和 visible slice assets。

## Pencil Assisted Slice Workspace

旧 Python Pencil route。它从 1..N 张图片生成 `candidates.v1.json`，让用户在 HTML Canvas 工作台确认或手动画框，保存 `manual_slices.v1.json`，再导出 `project.zip` 和 `selected-assets.zip`。当前只作为 superseded product/reference。

## manual_slices.v1.json

旧 Python Pencil route 的交付真相源，不是当前 Slice Studio manifest schema。

## Slice Candidates

旧 Python Pencil route 的自动候选文件，文件名为 `candidates.v1.json`。PSD-like、M29、OCR、foreground audit 和模型证据都只能进入候选/调试层，不能直接决定最终 visible asset。

## Review State

旧 Python Pencil route 的工作台状态文件，文件名为 `review_state.v1.json`。它记录 rejected candidates、筛选和最后处理页等 UI 状态，不参与最终交付真相。

## Editable Draft Layer Pipeline

历史/延后自动化路线。它从 PNG、OCR、M29 physical evidence 和可选 vision candidates/review 生成 Editable Layer Graph，再导出 Draft Runtime DSL 给 Renderer。

## Editable Layer Graph

Go Draft backend 的主合同，文件名为 `editable_layer_graph.v1.json`。它表达 layer ownership、bbox、z-order、source refs、semantic tags 和 emit/consume/suppress/refine 决策原因。

## Draft Runtime DSL

Renderer 输入合同，文件名为 `draft_runtime.dsl.v1.json`。它由 Editable Layer Graph 机械导出，不负责 ownership 决策。

## Renderer

把 Draft Runtime DSL 转成 Figma 节点的 TypeScript 包。Renderer 不运行 OCR、M29、vision、裁图、ownership 或 Codia eval。

## Figma Plugin

历史/延后 Draft route 的交互入口。当前 Slice Studio handoff 通过 `project.zip/design.pen`，不依赖插件作为默认交付路径。

## Codia Eval

官方 Codia JSON/golden 样本的比较和审计用途。Codia eval 只能作为 reference/eval，不能被当前生成路径读取。

## Fallback

当某条自动路线无法可靠重建结构时，保留更简单、更可修的输出。当前产品的主要 repair path 是 Slice Studio 手工/AI 画框后人工确认，而不是继续追求全自动树。
