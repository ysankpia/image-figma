# 157 Figma Design Manual Slice Workbench

## Summary

把新拉入的 `Figma-design` 项目收敛成一个能马上用于小程序 UI 资产交付的窄链路：

```text
1..N UI screenshots
-> 用户手动画框确认资产
-> assets.zip
-> Figma 插件按原坐标放回原图和切图资产
```

本轮不继续修 `services/pencil-handoff-studio` 的自动候选路线，不接 M29/PSD/OCR/YOLO，不做自动 UI 还原，不默认生成大量候选框。

## Scope

- 在 `Figma-design` 中新增纯手动切图入口。
- 默认插件 UI 改为纯手动切图工作台。
- 保留旧 `ui.html/server.js`，但不作为默认入口。
- 复用现有 `code.js` 的 `create-ui-asset-screen` Figma 回填合同。
- 支持上传/拖拽/粘贴多张图。
- 每页支持画框、选中、移动、8 点缩放、删除、重命名。
- 导出 `assets.zip`，结构包含 originals、slices、manifest。
- 点击“放入 Figma”发送 `create-ui-asset-screen`，原图 locked reference，切图资产按坐标放回。

## Non Goals

- 不做自动候选默认展示。
- 不导出 basic/text/shape/line。
- 不做 AI 生图、AI 透明底、SVG、H5 reconstruction。
- 不改旧 Python/Pencil 服务。

## Acceptance

- 浏览器 simulator 能打开新工作台。
- 上传真实 UI 图后原图清晰显示。
- 手动画框能创建资产。
- 资产可移动、缩放、删除、重命名。
- 多图切换时各自资产不串。
- `assets.zip` 内 PNG 数量等于用户确认资产数，并包含 originals。
- simulator 收到 `create-ui-asset-screen` 后能显示原图和切图资产。
- Chrome DevTools 当前导航无 JS error。
