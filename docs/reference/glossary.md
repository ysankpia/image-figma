# 术语表

## Image-to-Figma Design

本项目名称，把 PNG 截图或设计稿转换成 Figma 可编辑草稿。

## Editable Draft Layer Pipeline

当前产品主线。它从 PNG、OCR、M29 physical evidence 和可选 vision candidates/review 生成 Editable Layer Graph，再导出 Draft Runtime DSL 给 Renderer。

## Editable Layer Graph

Go Draft backend 的主合同，文件名为 `editable_layer_graph.v1.json`。它表达 layer ownership、bbox、z-order、source refs、semantic tags 和 emit/consume/suppress/refine 决策原因。

## Draft Runtime DSL

Renderer 输入合同，文件名为 `draft_runtime.dsl.v1.json`。它由 Editable Layer Graph 机械导出，不负责 ownership 决策。

## Renderer

把 Draft Runtime DSL 转成 Figma 节点的 TypeScript 包。Renderer 不运行 OCR、M29、vision、裁图、ownership 或 Codia eval。

## Plugin UI

Figma 插件里的用户界面，负责选择 PNG、触发 Draft 生成、显示进度、完成和失败状态。

## Plugin Main

Figma 插件主线程，负责调用 `/api/draft-preview`、获取 DSL/assets、调用 Renderer、操作 Figma Plugin API。

## ReferenceImage

保留在 Draft graph 中的原始 PNG 诊断参考。它必须 hidden/locked 或仅存在于 artifact 中，不能作为 visible full-page backing。

## TextLayer

可编辑文字层。普通 OCR 文字默认应保留为 TextLayer，并在同区域 ShapeLayer/RasterLayer 上方。

## RasterLayer

由源图裁切出的图片层，用于局部媒体、图标、头像、封面、缩略图或复杂 fallback 区域。RasterLayer 必须引用可解析 asset。

## ShapeLayer

背景、卡片、分割线、简单几何和基础视觉支撑层。ShapeLayer 不应携带前景文字像素。

## GroupLayer

组织移动和选择的分组层。GroupLayer 不拥有像素。

## M29 Physical Evidence

从 PNG 像素和 OCR 中提取的物理证据，例如 bbox、颜色、边缘、纹理、OCR mask、relation 和 source fragments。M29 提供证据，不直接创建最终 Draft layer。

## Vision Provider

OpenAI-compatible 视觉模型 provider。它提供 UI detector candidates 和可选 review decisions，不直接生成 DSL 或 Figma tree。

## Codia Eval

官方 Codia JSON/golden 样本的比较和审计用途。Codia eval 只能在 `internal/eval/codia` 和 `cmd/drafteval` 中使用，不能被 generation packages import。

## Asset

RasterLayer 引用的本地 PNG 文件。每个 completed task 的 visible image node 必须能通过 `/api/draft-preview/{taskId}/assets/{assetId}.png` 解析。

## Task

一次单张 PNG 处理任务，用 `taskId` 串联上传、状态、artifact、DSL、asset 和日志。

## Fallback

将复杂或低置信度区域裁切为 RasterLayer 放回 Figma。Fallback 是质量策略，不是失败；但它不能变成整页 visible backing。
