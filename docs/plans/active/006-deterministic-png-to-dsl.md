# M6 真实 PNG -> Deterministic DSL Builder

- 状态：completed
- 创建日期：2026-05-16
- 负责人：Codex

## Goal

拆掉后端运行时对固定 `mobile-home.dsl.json` 的依赖，让上传的真实 PNG 生成对应尺寸、对应资产、可渲染的 DSL v0.1。

## Scope

包含：

- 标准库解析 PNG IHDR 宽高。
- 基于真实 PNG 尺寸生成 deterministic fallback DSL。
- 原图隐藏层和整图 fallback 层。
- 资产记录真实宽高。
- 后端测试覆盖尺寸、DSL 输出、错误路径和 CORS。

不包含：

- OCR。
- AI。
- 真实布局理解。
- 文字识别。
- 图标渲染。
- 裁切算法。
- 异步队列。

## Acceptance

- 上传合法 PNG 后返回 completed task。
- task message 为 `Deterministic DSL is ready.`。
- DSL page/root 尺寸等于真实 PNG 尺寸。
- DSL 不包含 `title`、`search_card`、`search_icon`、`divider` 这些 sample-only 元素。
- DSL 包含隐藏 `original_ref` 和可见 `fallback_full_image`。
- 无法读取尺寸的 PNG 返回 `INVALID_IMAGE_DIMENSIONS`。

## Validation

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
```

手动 Figma 验收：

- 构建插件。
- 启动后端。
- 选择真实 PNG。
- 点击 `Generate from PNG`。
- root frame 尺寸应等于上传 PNG 尺寸。
- 上传链路不应出现 `UNSUPPORTED_ELEMENT_TYPE / search_icon`。

## Notes

`asset_banner` 暂时保留旧 asset id 以避免改动 API 和插件假设。M6 中它的语义是 full-image fallback asset。
