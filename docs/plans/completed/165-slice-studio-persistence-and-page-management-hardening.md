# 165 Slice Studio Persistence And Page Management Hardening

## Summary

把 `apps/slice-studio` 从可用手动切图工具收口成真实项目连续使用时不容易翻车的本地生产工具。本轮只修稳定性和项目工作流，不接 AI、Pencil、Figma 自动复刻或旧服务。

固定决策：

```text
替换页面原图：清空该页 slices
页面排序后导出：按当前顺序重新生成 P1/P2
Undo：第一版做前端会话级全操作撤销
```

## Key Changes

- 保存一致性：导出前必须 flush 页面命名和 slice 保存；保存失败停止导出。
- 页面管理：新增删除页面、替换页面、调整页面顺序；删除后 `page_index` 连续，替换后清空该页 slices。
- Undo：前端维护会话级 snapshot stack，覆盖 slice 和页面级操作；文件级替换/删除不恢复旧 source 文件。
- 接口与配置：新增页面管理 API；`GET /api/projects` 返回项目卡片预览数据；补 `NEXT_PUBLIC_SLICE_STUDIO_API_URL`、上传大小限制、CORS origin 配置。
- 验证：扩展 smoke 覆盖 3 页、重命名、排序、替换、删除、导出 ZIP 路径和 manifest。

## Validation

- `cd apps/slice-studio && bun run check`
- `cd apps/slice-studio && bun run build`
- `cd apps/slice-studio && bun run smoke`
- Chrome DevTools MCP 验证项目首页和 Review：
  - 项目列表不再 N+1 请求 detail。
  - 页面排序刷新后不丢。
  - 替换页面清空当前页 slices。
  - 删除页面后 P1/P2 连续。
  - Undo 能撤销 slice 和页面级操作。
  - 导出 ZIP 路径按当前页面顺序命名。
  - Console 无 error/warn。
- `git diff --check`
