# Manual UI Slice Workbench

Manual UI Slice Workbench 是一个本地项目制截图资产切图工具，也可以继续作为 Figma 插件页面运行。当前默认入口只做一件事：上传 1..N 张 UI 截图，用户手动画出开发要用的 image/icon 资产，保存到本地项目，导出 `assets.zip`。

旧版 AI 生图、图生图、透明底、SVG、H5 reconstruction 代码仍保留在 `ui.html` 和 `server.js` 里作为参考能力，但不再是默认产品入口。

## 核心能力

- 上传截图：支持选择文件、拖拽、粘贴图片
- 项目管理：支持新建、打开、重命名、删除本地项目
- 本地持久化：原图保存到 `storage/projects/`，SQLite 保存页面和切图元数据
- 多图切换：每张截图独立保存切图资产
- 手动切图：在截图上直接框选 image/icon 资产
- 可编辑选区：支持移动、8 点缩放、删除、重命名
- 自动保存：项目模式下画框、移动、缩放、删除、改名、改 kind 会自动保存
- 资产导出：导出 `assets.zip`，包含 `originals/`、`slices/`、`manifest.json` 和 `project.json`
- 坐标保留：切图资产保留原图中的位置和尺寸
- 放入 Figma：无项目模式下保留当前页导入 Figma 的原有能力

## 手动切图操作

- `B`：进入连续画框模式，在原图上连续拖拽创建资产框。
- `V`：进入选择模式，点击已有资产框后可移动、8 点缩放、删除和改名。
- `Delete` / `Backspace`：删除当前选中的资产框。
- 画框模式下，已有框只作为低干扰参考线显示，不显示名称和缩放点，也不会挡住继续画框。
- 画布上只显示短编号，完整资产名在右侧 `Selected Assets` 面板里编辑。

## 适用场景

- 从小程序/App UI 设计稿截图中切出开发需要的图片资产
- 从截图中拆分图标、头像、Logo、插画、商品图等复杂视觉资产
- 把原图和切图资产一起放入 Figma，后续继续人工整理或二次设计

## 项目结构

```text
.
├── manifest.json      # Figma 插件清单
├── code.js            # Figma 插件主线程，负责创建画布和导入图片
├── workspace.html     # 本地项目首页
├── manual-slice.html  # 当前默认手动切图工作台
├── project-server.js  # 本地项目服务，SQLite + 文件存储 + assets.zip 导出
├── ui.html            # 旧版 AI 生图/实验入口，当前不默认加载
├── server.js          # 旧版本地 API 代理，当前手动切图不依赖它
├── figma-sim.html     # 本地浏览器模拟 Figma 插件环境
├── package.json       # 本地启动脚本
├── .env.example       # 环境变量示例
└── docs/              # 产品规划和阶段计划
```

## 本地运行

需要 Node.js 20+。

更完整的使用流程、功能说明和常见问题见：

- [使用说明与功能说明](docs/使用说明与功能说明.md)
- [2.0 更新说明](docs/2.0-update.md)
- [2.0 Roadmap](docs/v2-roadmap.md)

1. 安装依赖：

```bash
npm install
```

2. 启动本地项目工具：

```bash
npm run studio
```

打开：

```text
http://127.0.0.1:4173/workspace.html
```

项目数据会写入：

```text
storage/
  app.sqlite
  projects/{projectId}/originals/
  projects/{projectId}/exports/assets.zip
```

`storage/` 是本地运行数据，不提交到 Git。

如果只想跑旧的纯静态预览：

```bash
npm run preview
```

打开：

```text
http://127.0.0.1:4173/figma-sim.html
```

也可以直接在 Figma Desktop 中导入 `manifest.json` 运行插件。插件模式不带 `projectId`，仍走纯前端内存状态和当前页 Figma 导入。

当前默认手动切图入口不需要 API Key，也不需要启动 `npm run api`。

## 本地项目 API

`npm run studio` 提供这些本地接口：

```text
GET    /api/health
GET    /api/projects
POST   /api/projects
GET    /api/projects/{projectId}
PATCH  /api/projects/{projectId}
DELETE /api/projects/{projectId}
POST   /api/projects/{projectId}/pages
GET    /api/projects/{projectId}/pages/{pageId}/source
PUT    /api/projects/{projectId}/slices
POST   /api/projects/{projectId}/export-assets
GET    /api/projects/{projectId}/assets.zip
```

上传图片第一版使用 JSON data URL，服务端统一落盘为 PNG。SQLite 只存项目、页面和 slice 元数据，不存图片 blob/base64。

`assets.zip` 结构固定：

```text
originals/page_0001.png
originals/page_0002.png
slices/page_0001/slice_0001.png
slices/page_0001/slice_0002.png
manifest.json
project.json
```

## 在 Figma 中加载

1. 打开 Figma Desktop
2. 进入 `Plugins > Development > Import plugin from manifest...`
3. 选择本目录的 `manifest.json`
4. 运行 `AI UI Asset Generator`
5. 上传 UI 截图
6. 框选需要的 image/icon 资产
7. 点击 `放入 Figma`

## 供应商配置

插件目前支持三类供应商：

- 第三方：默认模型 `gpt-image-2-all`
- 官方 OpenAI：默认模型 `gpt-image-2`
- OpenRouter：固定模型 `gpt-5.4-image-2`

前端会请求本地代理：

```text
http://127.0.0.1:18787
```

如果出现 `Failed to fetch`，通常表示本地 API 代理没有启动，请先运行：

```bash
npm run api
```

## 后端接口

### `POST /api/images/generate`

文生图。请求示例：

```json
{
  "prompt": "生成一个健身 App 首页",
  "width": 390,
  "height": 844,
  "count": 4,
  "quality": "high",
  "outputFormat": "png"
}
```

### `POST /api/images/edit`

图生图。插件会把本地参考图读取为 data URL，后端再转换成对应供应商需要的请求格式。

```json
{
  "prompt": "根据参考图生成一个健身 App 首页",
  "width": 390,
  "height": 844,
  "images": [
    {
      "name": "reference.png",
      "type": "image/png",
      "dataUrl": "data:image/png;base64,..."
    }
  ]
}
```

### `POST /api/assets/generate-transparent`

透明 PNG 切图素材生成接口。当前主要用于将切出的素材进一步处理为透明底。

## 安全说明

发布到 GitHub 前请确认不要提交这些文件：

- `.local-provider-config.json`
- `.env`
- 任何包含真实 API Key 的截图或日志
- `node_modules/`

建议使用 `.env.example` 只保留示例配置。

## 路线规划

- 更稳定的背景修复模式
- 自动识别 UI 元素并生成切图建议
- 切图资产批量命名和管理
- 图片/icon 转 SVG 的可编辑化能力
- 结构化生成 Figma 可编辑图层
