# M5 Figma 插件接入后端上传链路计划

- 状态：completed
- 创建日期：2026-05-16
- 负责人：Codex

## Goal

把插件主链路从内置 sample DSL 升级为：选择 PNG、上传 M4 后端、查询任务、获取 DSL、调用 Renderer 写入 Figma。

## Scope

包含：

- PNG 文件选择。
- `Generate from PNG` 主按钮。
- Main 调用 `POST /api/upload`、`GET /api/tasks/{taskId}`、`GET /api/tasks/{taskId}/dsl`。
- 最多 10 次、间隔 500ms 的任务轮询。
- 后端错误和网络错误展示。
- 保留 `Sample` 开发备用入口。

不包含：

- OCR/AI。
- 后端 API 变更。
- 设置页。
- React/Vite。
- icon renderer。

## Steps

1. 扩展 UI/Main 消息协议。状态：完成。
2. 新增插件 API client。状态：完成。
3. 增加 PNG 选择和上传生成 UI。状态：完成。
4. Main 编排 upload -> task -> dsl -> renderer。状态：完成。
5. 同步架构、测试和本地运行文档。状态：完成。

## Acceptance

- 插件能选择 PNG。
- 后端运行时，点击 `Generate from PNG` 能生成 Figma Frame。
- UI 展示上传、处理、写入和完成状态。
- 后端不可用时 UI 显示失败。
- `Sample` 入口仍可用于开发烟测。

## Validation

```bash
pnpm --filter @image-figma/figma-plugin run typecheck
pnpm --filter @image-figma/figma-plugin run build
pnpm run check
cd backend && uv run pytest
```

已验证：

- `pnpm --filter @image-figma/figma-plugin run typecheck` 通过。
- `pnpm --filter @image-figma/figma-plugin run build` 通过，bundle scan 通过。
- `pnpm run check` 通过。
- `cd backend && uv run pytest` 通过，7 个测试通过。
- 本地启动 `uvicorn app.main:app --host 127.0.0.1 --port 8000` 后，用临时 PNG 验证 `health -> upload -> task -> dsl -> asset -> /files` API 链路通过。

## Notes

M5 后端地址暂时固定为 `http://localhost:8000/api`。设置页和可配置 API 地址后续再做。
