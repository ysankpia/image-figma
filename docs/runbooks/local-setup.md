# 本地设置

当前仓库已经初始化最小 monorepo，并实现了第一批 `@image-figma/dsl-schema` 合同包和 `@image-figma/image-to-figma-renderer`。

## Prerequisites

需要：

- Node.js 24.x。当前开发机使用 Homebrew `node@24`。
- pnpm 10.33.2。
- Python 3.12.7，由 asdf 管理。
- Git。

`.tool-versions` 当前只固定：

```text
python 3.12.7
```

本机 asdf 当前没有 nodejs 插件，所以本轮不把 Node 写入 `.tool-versions`。

## Run Locally

安装依赖：

```bash
pnpm install
```

运行全部当前检查：

```bash
pnpm run check
```

只检查 DSL Schema 包：

```bash
pnpm --filter @image-figma/dsl-schema run typecheck
pnpm --filter @image-figma/dsl-schema run test
```

只检查 Renderer 包：

```bash
pnpm --filter @image-figma/image-to-figma-renderer run typecheck
pnpm --filter @image-figma/image-to-figma-renderer run test
```

构建 Figma dev harness：

```bash
pnpm --filter @image-figma/figma-plugin run build
```

在 Figma 中验证：

1. 打开 Figma。
2. 进入插件开发模式。
3. 加载 `figma-plugin/manifest.json`。
4. 运行 `Image-to-Figma Dev Harness`。
5. 当前页面应生成 `mobile_home` root Frame。

当前还没有后端服务或正式 Figma 插件 UI。

后续目标命令应覆盖：

```text
启动后端
启动正式插件 UI 构建
运行 DSL 测试
运行 Renderer 测试
运行 API 测试
```

## Configuration

环境变量记录在 [../reference/env-vars.md](../reference/env-vars.md)。
