# 173 Slice Studio Asset Review Gallery

- 状态：completed
- 创建日期：2026-06-11
- 负责人：Codex

## Goal

在 Review 页面增加资产总览检查能力：一张图里切了几十或上百个资产后，用户可以用统一网格查看所有真实裁切结果，按编号快速定位问题资产，并让画布选中、右侧资产列表同步定位。

## Scope

包含：

- `apps/slice-studio` 后端新增单 slice 预览 PNG API。
- Review 右侧资产列表与画布选中同步滚动。
- Review 增加资产总览 modal/grid。

不包含：

- AI/OCR 自动判断资产语义。
- 自动质量评分或自动改名。
- 改变导出 ZIP / manifest 结构。

## Behavior

- 总览展示当前页面所有 slices。
- 每个卡片显示编号、名称、尺寸、裁切模式和真实预览 PNG。
- 预览 PNG 复用后端导出裁切逻辑，矩形和透明底都应与最终导出一致。
- 点击总览卡片：
  - 选中对应 slice。
  - 关闭总览或保持总览高亮均可，但必须让右侧资产列表滚动到对应项。
  - 画布上 active slice 显示。
- 点击画布 slice 或右侧资产行时，右侧列表自动滚动到 active item。

## API

新增：

```text
GET /api/projects/:projectId/slices/:sliceId/preview.png
```

返回单个 slice 的 PNG，使用当前 SQLite 中的 bbox 和 cutMode 从原图裁切。

## Acceptance

- 100 个资产时总览仍能滚动查看。
- 总览看到的 PNG 与导出裁切逻辑一致。
- 画布选中某个 slice 后，右侧资产列表自动滚到对应项。
- 总览点某个编号后，右侧资产列表自动定位并高亮该项。
- 不影响保存、导出、拖动和缩放。

## Validation

- `cd apps/slice-studio && bun run typecheck`
- `cd apps/slice-studio && bun run test`
- `cd apps/slice-studio && bun run build`
- 浏览器打开真实项目，打开总览，点击一个中间编号，确认右侧列表定位。
- `git diff --check`
