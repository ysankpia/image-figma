# 产品需求

本文档记录当前 Slice Studio 产品需求。历史 Draft MVP 需求只作背景，不能覆盖当前主线。

## Scope

当前支持本地项目制 UI 切图和 Pencil/Figma handoff：

```text
1..N UI screenshots/design images
-> project workspace
-> manual or AI-assisted slice boxes
-> SQLite-backed saved project state
-> assets.zip
-> project.zip / design.pen
```

输入：

- PNG/JPEG/WebP 等浏览器和 Sharp 可读图片。
- 单项目可包含多张页面图片。
- 目标样本以 App、小程序、移动端和 UI 设计稿为主，也允许简单 Web/后台截图。

## Core Capabilities

P0 能力：

- Landing page。
- 登录/注册、会话 cookie、登出。
- 本地/bootstrap owner 账号。
- 项目归属到 `users.id`，项目 API 按 owner 过滤。
- `/settings` 极简账号入口。
- 创建、重命名、删除本地项目。
- 上传多张页面图片。
- 页面缩略图、页面切换、页面重命名、替换、删除、拖拽重排。
- Canvas review：选择、连续画框、移动、缩放、删除、撤销、pan/zoom。
- Slice 属性：名称、bbox、`rect | subject | card` cut mode。
- 自动保存 slices，并在刷新后恢复。
- `assets.zip` 导出原图、slice PNG、`manifest.json`、`project.json`。
- `project.zip` 导出 `design.pen`、原图、remainder、slice PNG、manifest 和 project metadata。
- Exporter 从原始 source image 裁切，不从 canvas thumbnail 或 debug artifact 裁切。

P1 能力：

- OCR editable text layer：在 Pencil package 中添加普通可编辑文字节点。
- TypeScript M29 physical evidence：默认给 OCR text 提供更紧的 physical bbox，不依赖 Go binary。
- AI 当前页/全部页画框：模型只返回矩形 bbox，前端转换为普通 slice 并走现有保存路径。
- AI batch progress overlay。
- AI overview review：减少跨 tile 大资产被切半。
- 项目 home：搜索、筛选、排序、grid/list 视图和首图预览。

P2 后续能力：

- 生产数据库和对象存储 adapter。
- 可选支付 provider、订单、额度、用量和管理后台；必须走新 active plan，不从旧 189 直接恢复。
- 更好的 AI 重复运行策略。
- 可选“干净模式/全切模式”AI prompt 策略 UI。
- Slice Studio 部署 runbook。
- 更自动化的 `.pen` 视觉验收。

## Output Requirements

`assets.zip` 必须包含：

- `originals/` 页面原图；
- `slices/` 用户确认 slice PNG；
- `manifest.json`；
- `project.json`。

`project.zip` 必须包含：

- `design.pen`；
- `manifest.json`；
- `project.json`；
- package-local originals；
- package-local visible remainders；
- package-local visible slice PNG；
- optional editable text nodes when OCR succeeds.

Visible refs 不得包含：

```text
absolute paths
../
source.png as visible ref
raw crops
masks
debug assets
local storage paths
```

## Error Requirements

失败要能归到明确阶段：

- project create/list/detail;
- page upload/replace/delete/reorder;
- slice save;
- preview crop;
- assets export;
- project export;
- OCR provider;
- M29 physical evidence;
- AI slice provider;
- ZIP/Pencil packaging.

AI、OCR、M29 失败不得破坏已有用户保存的 slices。导出应尽量继续并在 manifest/metadata 中记录跳过或 fallback 原因。
