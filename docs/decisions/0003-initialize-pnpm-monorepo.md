# ADR 0003: 初始化 pnpm monorepo 并先实现 DSL Schema 包

- 状态：accepted
- 日期：2026-05-16

## Context

项目需要同时承载 Figma 插件、后端、Renderer 和共享 DSL 合同。如果没有共享包和统一检查入口，后端、Renderer、插件会在字段和行为上分叉。

## Decision

使用 pnpm workspace 管理 monorepo。第一批工程实现只创建最小骨架，并优先实现 `@image-figma/dsl-schema`。

本轮不实现 Renderer、插件 UI、后端 API、OCR、AI 或 asset cropper。

## Consequences

好处：

- DSL 合同先稳定，后续 Renderer 和后端都能引用同一套类型和校验。
- 示例 DSL 能成为 Renderer 的第一批输入。
- 本地检查可以先围绕最小包跑起来。

代价：

- 当前 Node 由 Homebrew 提供，`.tool-versions` 暂时只固定 Python。
- CI、脚本目录和更完整工程治理需要下一轮补齐。
