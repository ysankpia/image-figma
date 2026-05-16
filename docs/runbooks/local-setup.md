# 本地设置

当前仓库已经初始化最小 monorepo，并实现了 `@image-figma/dsl-schema`、`@image-figma/image-to-figma-renderer`、Figma 插件最小 UI、FastAPI 后端、deterministic region fallback 上传链路、M8 visual primitive contract harness、M9 OCR/DSL patch harness 和 M10 百度 PP-OCRv5 异步 OCR provider。

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

安装后端依赖：

```bash
cd backend
uv sync
```

运行后端测试：

```bash
cd backend
uv run pytest
```

启动后端：

```bash
cd backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

构建 Figma 插件：

```bash
pnpm --filter @image-figma/figma-plugin run build
```

只构建底层 dev harness：

```bash
pnpm --filter @image-figma/figma-plugin run build:dev
```

在 Figma 中验证：

1. 打开 Figma。
2. 进入插件开发模式。
3. 加载 `figma-plugin/manifest.json`。
4. 运行 `Image-to-Figma Design`。
5. 插件应打开 `420 x 560` 工具面板。
6. 启动后端：`cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`。
7. 选择一个 PNG。
8. 点击 `Generate from PNG`。
9. 当前页面应生成尺寸等于 PNG 的 `uploaded_png` root Frame。
10. Layers 中应出现 hidden `Original PNG Reference` 和可见 region fallback。
11. UI 应显示生成节点数和 warning 数。

当前 M5 插件主链路会调用 `http://localhost:8000/api`。`Sample` 按钮保留为开发备用入口，不调用后端。

M8 primitive extraction 默认使用 fake provider，不需要 OpenAI key：

```bash
VISUAL_PRIMITIVE_PROVIDER=fake
```

上传后可以查询 primitive candidates：

```bash
curl http://localhost:8000/api/tasks/{taskId}/primitives
```

OpenAI provider 只用于可选 smoke，必须显式启用：

```bash
cd backend
VISUAL_PRIMITIVE_PROVIDER=openai \
OPENAI_API_KEY=... \
OPENAI_VISION_MODEL=gpt-5.5 \
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

即使 OpenAI provider 失败，上传任务和 `/api/tasks/{taskId}/dsl` 也应继续成功；M9 patch 失败时会回退 base DSL。

OCR 和 patch 默认配置：

```bash
OCR_PROVIDER=fake
DSL_PATCH_MODE=debug
```

百度 PP-OCRv5 异步 OCR smoke：

```bash
cd backend
OCR_PROVIDER=baidu_ppocrv5 \
BAIDU_PADDLE_OCR_TOKEN=... \
BAIDU_PADDLE_OCR_MODEL=PP-OCRv5 \
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

百度 token 是 bearer token，只能放在本地环境变量或未提交的 `.env` 中，不能写入仓库。百度 OCR 失败时上传任务仍应 completed，`/dsl` 回退 fallback DSL。

上传后可以查询：

```bash
curl http://localhost:8000/api/tasks/{taskId}/ocr
curl http://localhost:8000/api/tasks/{taskId}/dsl-patch
```

如果要确认完全回退 M7 base DSL：

```bash
cd backend
DSL_PATCH_MODE=off uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`localhost` 只配置在 `manifest.json` 的 `networkAccess.devAllowedDomains`。Figma 不允许把 localhost 放进正式 `allowedDomains`，除非同时提供审核用 `reasoning` 字段。开发期如果要阻断正式网络域名，`allowedDomains` 必须写成 `["none"]`，不能写空数组。

Figma 插件主线程的 JavaScript 解析器比现代浏览器页面更保守。插件 bundle 目标使用 `es2017`，并在构建后扫描 `??`、`?.`、ESM import/export、`structuredClone`、`Object.hasOwn` 和 `for await` 残留。

后续目标命令应覆盖：

```text
运行 DSL 测试
运行 Renderer 测试
运行 API 测试
```

## M7 Sample Smoke

用户提供的当前验收样例目录：

```text
/Users/luhui/Downloads/宿舍床位可视化选择系统_UI设计图/学生端
```

已知 PNG 样例：

```text
01_学生端-首页选床活动.png  941x1672
02_学生端-楼层选择.png      941x1672
03_学生端-房间选择.png      941x1672
04_学生端-床位选择.png      941x1672
05_学生端-确认选床.png      941x1672
06_学生端-选床结果.png      941x1672
07_学生端-登录注册.png      958x1641
```

M7 后端 smoke 可以先用主样例：

```bash
curl -F "file=@/Users/luhui/Downloads/宿舍床位可视化选择系统_UI设计图/学生端/01_学生端-首页选床活动.png" \
  http://localhost:8000/api/upload
```

预期：

- task completed。
- DSL root frame 为 `941 x 1672`。
- `meta.notes` 默认为 `deterministic_region_dsl+m9_patch_debug`。
- `meta.platformHint` 为 `mobile`。
- root children 包含 `original_ref`、`fallback_region_header`、`fallback_region_content`、`fallback_region_bottom` 和 hidden `candidate_text`。
- `/api/tasks/{taskId}/primitives` 返回 `provider: "fake"` 和 `vp_region_header/content/bottom`。
- 默认 `/api/tasks/{taskId}/ocr` 返回 `provider: "fake"`；启用百度后返回 `provider: "baidu_ppocrv5"` 和 `model: "PP-OCRv5"`。
- `/api/tasks/{taskId}/dsl-patch` 返回 `mode: "debug"`。
- 上传链路不出现 sample 专属的 `search_icon` warning。

## Configuration

环境变量记录在 [../reference/env-vars.md](../reference/env-vars.md)。
