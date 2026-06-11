# 176 Slice Studio Pencil Project Export

## Summary

把 `apps/slice-studio` 从 `assets.zip` 切图交付扩展到 Pencil handoff 交付。第一阶段和第二阶段固定为：

```text
SQLite project + originals + confirmed slices
-> export assets.zip unchanged
-> generate per-page remainder.png
-> generate one project-level design.pen
-> package project.zip
```

本轮不做 OCR、TextLayer、字体识别、Figma 导入、AI 自动结构复刻。Pencil 导出只消费用户已经确认的 manual slices；`remainder.png` 是导出时派生的背景层，不能反向修改原图和 SQLite。

## Key Decisions

- `assets.zip` 继续保持当前合同，给前端开发稳定切图资产。
- 新增 `project.zip`，给 Pencil/Figma handoff 使用。
- `design.pen` 是项目级文件，一个项目一个总 `.pen`，包含所有页面 frame。
- 每页 frame 包含：
  ```text
  locked hidden/diagnostic original reference metadata
  visible remainder image layer
  visible slice image layers at original coordinates
  ```
- `remainder.png` 生成方式：
  ```text
  source.png
  - selected slice bbox areas filled transparent
  = remainder.png
  ```
  第一版按 slice bbox 挖空，不按 subject/card alpha mask 挖空。原因是 `.pen` 视觉合成里 slice layer 会覆盖原坐标，bbox 透明挖空足够防止重复像素；后续如需要更精细，再扩展 alpha-aware remainder。
- Slice layer 使用当前 `cropSliceToPng()` 输出，保留 `rect | subject | card` 三种裁切模式。
- `.pen` image refs 必须是包内相对路径，禁止绝对路径、`../`、debug/raw 引用。

## Public Interfaces

新增 API：

```text
POST /api/projects/:projectId/export-project
GET  /api/projects/:projectId/project.zip
```

`POST /export-project` 返回：

```json
{
  "ok": true,
  "assetCount": 12,
  "pageCount": 3,
  "url": "/api/projects/project_xxx/project.zip"
}
```

`project.zip` 结构：

```text
design.pen
manifest.json
project.json
assets/
  originals/P1-首页.png
  visible/remainders/P1-首页/remainder.png
  visible/slices/P1-首页/slice_0001.png
  visible/slices/P1-首页/slice_0002.png
```

## Implementation Changes

- 新增后端模块：
  ```text
  apps/slice-studio/server/pencil-exporter.ts
  ```
- 复用：
  ```text
  getProjectDetail()
  getPageOriginalPath()
  cropSliceToPng()
  buildExportManifest()
  pageExportDirectory()
  createZipBuffer()
  ```
- `server/index.ts` 新增导出和下载路由。
- 前端 Review 顶部保留 `导出 assets.zip`，新增 `导出 project.zip`。
- README 记录两种导出：
  ```text
  assets.zip: 给前端开发
  project.zip/design.pen: 给 Pencil/Figma handoff
  ```

## Test Plan

- 单元测试：
  ```text
  remainder generation clears slice bbox alpha
  project.zip contains design.pen, manifest, project.json, originals, remainders, slices
  design.pen refs are relative and all exist in ZIP
  project manifest page/slice count matches DB
  ```
- Smoke：
  ```text
  create project
  upload image
  save slices with mixed cut modes
  export assets.zip
  export project.zip
  verify ZIP entries and .pen image refs
  ```
- 必跑：
  ```bash
  cd apps/slice-studio
  bun run check
  bun run build
  bun run smoke

  cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma
  git diff --check
  git status --short --branch
  ```

## Assumptions

- 当前项目仍是快速开发期，不做旧 project.zip 兼容。
- 手动画 slice 是图层真相源，OCR 不参与本轮。
- 按 bbox 生成 transparent remainder 是第一版最简单、可验证、稳定的合成策略。
- 后续 OCR 阶段只在未被 user slices 覆盖的区域生成候选，不反过来覆盖 slice 真相源。
