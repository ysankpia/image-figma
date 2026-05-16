# 术语表

## Image-to-Figma Design

本项目名称，把 PNG 截图或设计稿转换成 Figma 可编辑稿。

## DSL v0.1

后端和 Renderer 之间的数据合同。后端生成，Renderer 消费。

## Renderer

把 DSL v0.1 转成 Figma 节点的 TypeScript 包。

## Plugin UI

Figma 插件里的 React 用户界面，负责上传、预览、进度、完成和失败状态。

## Plugin Main

Figma 插件主线程，负责调用 API、获取 DSL、调用 Renderer、操作 Figma Plugin API。

## Fallback

将复杂或低置信度区域裁切为图片放回 Figma。Fallback 是质量策略，不是失败。

## Original Reference

保留在 root Frame 内的原始 PNG 参考层，默认隐藏。

## Asset

原图、裁切图、fallback 图、头像、商品图、Banner 等图片资源。

## Task

一次单张 PNG 处理任务，用 `taskId` 串联上传、识别、DSL、资产和日志。
