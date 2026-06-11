# 用户流程

当前主流程是 Slice Studio 本地项目制切图，不是 Figma 插件上传单张 PNG。

## 项目流程

```text
打开 /projects
-> 新建项目
-> 进入 Review Workbench
-> 上传一张或多张页面图片
-> 页面显示在左侧缩略图 rail
-> 在画布中手动画框或运行 AI 当前页/全部页
-> 调整、删除、命名 slices
-> 选择 rect/subject/card cut mode
-> 自动保存
-> 导出 assets.zip 或 project.zip
```

## AI 画框流程

```text
点击 AI 当前页或 AI 全部页
-> API 将原图切成重叠 tile 并压缩
-> provider 返回 bbox JSON
-> 服务端裁边、过滤、去重、合并
-> 前端把 boxes 转成普通 rect SliceRecord
-> 走现有 saveSlices 保存
-> 用户继续人工删改
```

AI 不创建独立 proposal 状态。进入工作台后的 AI box 就是普通 slice。

## 导出流程

`assets.zip`：

```text
读取 SQLite 项目和 saved slices
-> 按页面顺序读取 original PNG
-> 按 slice bbox 和 cut mode 裁切
-> 写 originals / slices / manifest.json / project.json
```

`project.zip`：

```text
读取同一批 saved slices
-> 生成 remainder.png
-> 放置 slice PNG 到 source-image 坐标
-> 可选 OCR + M29 physical bbox 生成 editable text nodes
-> 写 design.pen / manifest.json / project.json / assets
```

## 页面状态

- Project home：项目列表、搜索、筛选、排序、grid/list、新建、重命名、删除。
- Review Workbench：左侧页面 rail、中间 Konva canvas、右侧 asset inspector 和 asset gallery。
- AI progress：批量运行时显示完成页数、失败页数、新增/跳过框数量，可最小化或关闭。
- Save state：自动保存中、已保存、保存失败。

## 修复路径

用户通过 Review Workbench 修复：

- 增删改 slice；
- 调整 bbox；
- 改名称；
- 改 cut mode；
- 删除或替换页面；
- 重排页面；
- 重新导出。

## 失败流程

- 上传失败：显示错误，不创建不完整页面。
- 保存失败：保留当前 UI 状态并提示。
- AI 失败：当前页或失败页记录状态；批量继续处理其他页。
- OCR/M29 失败：`project.zip` 仍可导出，文字层缺失或 fallback 记录在 manifest/metadata。
- 导出失败：返回明确错误，用户保存的 slices 不丢。
