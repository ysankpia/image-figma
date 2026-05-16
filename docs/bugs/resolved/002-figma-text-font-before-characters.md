# 002: Figma TextNode 写入前未应用已加载字体

- 状态：resolved
- 日期：2026-05-16

## Symptom

Figma 插件渲染 sample DSL 时，标题文字没有写入，UI warning 显示：

```text
ELEMENT_RENDER_FAILED / title
in set_characters: Cannot write to node with unloaded font "Inter Regular".
```

## Cause

Renderer 调用了 `figma.loadFontAsync`，但没有在写入 `characters` 前把 TextNode 的 `fontName` 设置为同一个已加载字体。Figma 写文字时检查的是节点当前字体，而不是仅检查是否调用过 `loadFontAsync`。

## Fix

- `FigmaAdapter.loadFont` 返回实际加载的 `FontName`。
- `setTextStyle` 在写入文字前设置 TextNode 的 `fontName`。
- `renderText` 先应用文本样式，再设置 `characters`。

## Regression Guard

```bash
pnpm --filter @image-figma/image-to-figma-renderer run test
pnpm run check
```
