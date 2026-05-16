# M3 Figma 插件最小 UI 闭环计划

- 状态：active
- 创建日期：2026-05-16
- 负责人：Codex

## Goal

把当前无 UI 的 Figma dev harness 升级为可操作的最小插件。用户打开插件后点击 `Generate sample design`，插件 Main 调用现有 Renderer，把 `mobile-home.dsl.json` 写入当前 Figma 页面，并在 UI 和 `figma.notify` 中展示结果。

## Scope

包含：

- 静态 `ui.html` 工具面板。
- `main.ts` 和 UI/Main 消息协议。
- sample DSL 渲染入口。
- warning 和 error 展示。
- Figma bundle 兼容性扫描。
- 本地构建和 Figma 手动烟测说明。

不包含：

- PNG 上传。
- 后端 API。
- OCR/AI。
- 账号、授权、支付、额度。
- React/Vite。
- `.pen` importer 或旧 renderer 迁移。

## Steps

1. 新增 `messages.ts`，固定 UI/Main 最小消息协议。状态：完成。
2. 新增 `main.ts`，实现 `showUI`、`render-sample`、成功/失败反馈。状态：完成。
3. 新增静态 `ui.html`，提供按钮、状态和 warning 列表。状态：完成。
4. 更新 `manifest.json`，默认加载正式最小 UI。状态：完成。
5. 更新插件构建脚本和 bundle 扫描。状态：完成。
6. 更新架构、测试、本地设置和 ADR 文档。状态：完成。

## Acceptance

- 插件构建生成 `dist/main.global.js` 和 `dist/ui.html`。
- `figma-plugin/manifest.json` 指向正式 UI。
- `localhost` 只出现在 `networkAccess.devAllowedDomains`。
- UI 可以发送 `render-sample`。
- Main 可以调用 Renderer 渲染 sample DSL。
- 渲染成功时 UI 显示节点数和 warning 数。
- 渲染失败时 UI 显示错误摘要。
- 图片加载失败只产生 warning，不阻断文字、shape 和 line。

## Validation

自动化验证：

```bash
pnpm --filter @image-figma/figma-plugin run typecheck
pnpm --filter @image-figma/figma-plugin run build
pnpm run check
```

手动 Figma 烟测：

1. 构建插件。
2. 在 Figma 开发模式加载 `figma-plugin/manifest.json`。
3. 运行 `Image-to-Figma Design`。
4. 点击 `Generate sample design`。
5. 当前页面生成 `mobile_home` root Frame。
6. UI 显示 rendered element count 和 warning count。

## Notes

本轮只借鉴 `/Users/luhui/pencil.2.figma` 的插件壳子经验，不复制它的授权、支付、后端、商业 UI、`.pen` 数据模型或旧 renderer。
