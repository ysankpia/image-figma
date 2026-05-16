# 001: Figma 插件不接受现代 JS 语法残留

- 状态：resolved
- 日期：2026-05-16

## Symptom

Figma 开发插件加载后报错：

```text
Syntax error on line 19: Unexpected token ?
url: resolveUrl(source.url ?? asset.url, assetBaseUrl)
```

## Cause

插件 Main bundle 使用 `es2020` target，产物中保留了 nullish coalescing。Figma 插件主线程解析器不能稳定接受 `??` 和 `?.` 这类现代语法残留。

## Fix

- 插件 Main 和 dev harness 构建 target 降为 `es2017`。
- bundle 扫描新增 `??` 和 `?.` 检查。

## Regression Guard

```bash
pnpm --filter @image-figma/figma-plugin run build
pnpm run check
```
