# M7 Deterministic Region Slicer

- 状态：completed
- 创建日期：2026-05-16
- 负责人：Codex

## Goal

在 M6 整图 fallback 基础上，把真实 PNG 按 deterministic 规则切成多个可独立渲染的 fallback region。目标不是识别文字或布局，而是让 Figma 画布里出现稳定命名、可单独替换的区域层。

## Scope

包含：

- 标准库 PNG metadata 读取。
- 标准库 PNG cropper。
- portrait/mobile-like PNG 三段切分。
- `header`、`content`、`bottom` region asset 生成。
- DSL 输出 `fallback_region_header`、`fallback_region_content`、`fallback_region_bottom`。
- 不支持 crop 的 PNG 退回整图 fallback。
- 后端 API 测试覆盖 region DSL、region asset 和 fallback 降级。

不包含：

- OCR。
- AI。
- 文字识别。
- 真实布局理解。
- 图标渲染。
- 插件 UI/Main 协议变更。
- 队列和异步任务。

## Region Rules

portrait/mobile-like 判断：

```text
height >= width * 1.2 && width <= 1200
```

三段切分：

```text
header = min(max(round(height * 0.14), 120), 260)
bottom = min(max(round(height * 0.12), 100), 220)
content = height - header - bottom
```

如果图片不适合切三段，或 cropper 不支持该 PNG 格式，后端退回 M6 的整图 fallback，不让任务失败。

## Acceptance

- 上传合法 portrait/mobile-like PNG 后返回 completed task。
- DSL page/root 尺寸等于真实 PNG 尺寸。
- DSL `meta.notes` 为 `deterministic_region_dsl`。
- DSL `meta.fallbackCount` 为 `3`。
- DSL 包含隐藏 `original_ref`。
- DSL 包含 `fallback_region_header`、`fallback_region_content`、`fallback_region_bottom`。
- 三个 region layout 连续覆盖整图，无空洞、无重叠。
- 三个 region asset 文件存在且是 PNG。
- DSL 不包含 `title`、`search_card`、`search_icon`、`divider` 这些 sample-only 元素。
- 不支持 crop 的 PNG 退回 `fallback_full_image`，并写入 `qualityFlags: ["region_crop_unsupported"]`。

## Validation

自动验证：

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
```

手动 Figma 验收：

1. 构建插件：`pnpm --filter @image-figma/figma-plugin run build`。
2. 启动后端：`cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`。
3. 在 Figma 中运行 `Image-to-Figma Design`。
4. 上传 `/Users/luhui/Downloads/宿舍床位可视化选择系统_UI设计图/学生端/01_学生端-首页选床活动.png`。
5. root frame 尺寸应为 `941 x 1672`。
6. Layers 中应有 hidden `Original PNG Reference`。
7. Layers 中应有 `Fallback Region / header`、`Fallback Region / content`、`Fallback Region / bottom`。
8. 三个 region 视觉上拼回原图，不应明显错位或留白。
9. 上传链路不应出现 `UNSUPPORTED_ELEMENT_TYPE / search_icon`。

## Evidence

当前自动测试覆盖：

- PNG metadata 字段读取。
- 941x1672 样例比例的三段 region 规划。
- PNG cropper 输出 region 尺寸。
- unsupported color type 降级。
- 上传后生成 region DSL 和 region asset。
- 非 PNG、坏 IHDR、过大 PNG 错误路径。
- CORS、task、DSL、asset 查询。

已验证命令：

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
```

真实样例 smoke 已通过：

```text
01_学生端-首页选床活动.png: 941x1672 children=[original_ref, fallback_region_header, fallback_region_content, fallback_region_bottom]
02_学生端-楼层选择.png: 941x1672 children=[original_ref, fallback_region_header, fallback_region_content, fallback_region_bottom]
03_学生端-房间选择.png: 941x1672 children=[original_ref, fallback_region_header, fallback_region_content, fallback_region_bottom]
04_学生端-床位选择.png: 941x1672 children=[original_ref, fallback_region_header, fallback_region_content, fallback_region_bottom]
05_学生端-确认选床.png: 941x1672 children=[original_ref, fallback_region_header, fallback_region_content, fallback_region_bottom]
06_学生端-选床结果.png: 941x1672 children=[original_ref, fallback_region_header, fallback_region_content, fallback_region_bottom]
07_学生端-登录注册.png: 958x1641 children=[original_ref, fallback_region_header, fallback_region_content, fallback_region_bottom]
```
