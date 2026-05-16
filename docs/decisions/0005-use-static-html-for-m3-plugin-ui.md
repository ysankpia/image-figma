# ADR 0005: M3 插件 UI 使用静态 HTML

- 状态：accepted
- 日期：2026-05-16

## Context

M3 的目标是打通 UI -> Main -> Renderer -> Figma Canvas，不是构建复杂前端应用。仓库外已有提交审核的 Figma 插件使用静态 HTML 和 TypeScript Main，这条路径更接近 Figma 插件审核和 sandbox 的实际约束。

## Decision

M3 插件 UI 使用静态 `ui.html`、内联 CSS/JS 和 TypeScript Main，通过 `parent.postMessage` 与 `figma.ui.onmessage` 通信。暂不引入 React/Vite。

## Consequences

好处：

- 构建链路更短。
- Figma 插件加载面更小。
- 更容易验证消息流和 Renderer 写入画布。

代价：

- UI 复杂后手写 DOM 会变重。
- 后续如果加入上传、预览、进度和设置页，可能需要重新评估 React/Vite。
