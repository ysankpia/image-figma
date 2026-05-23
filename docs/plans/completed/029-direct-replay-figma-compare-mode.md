# M29 Direct Replay Figma Compare Mode

- 状态：completed
- 创建日期：2026-05-22
- 负责人：未指定

## Goal

把 M29 Direct Replay 的路线判断从 JSON/report 拉到 Figma 画布里验证。同一张 PNG 只上传一次，同一个 task 同时产出：

```text
M29 Direct Replay flat DSL
Current Mainline M30/M38/M39 DSL
```

插件新增 `Generate Compare`，把两份 DSL 左右并排写入当前 Figma 页面。用户直接拖动、编辑、肉眼检查重影和图层混乱度。

## Scope

包含：

- 在 `/api/upload-m30-preview` 后台任务里复用同一次 OCR 和 M29 evidence 生成 `m29_direct` variant。
- 写出 `storage/m30_1_uploads/{taskId}/m29_direct/m29_direct_replay_dsl.json`。
- 写出 `storage/m30_1_uploads/{taskId}/m29_direct/m29_direct_replay_report.json`。
- 将 M29 direct assets 发布到 `/files/assets/{taskId}/m29_direct/...`。
- 新增 `GET /api/tasks/{taskId}/m29-direct-dsl`。
- 插件新增 `Generate Compare`，上传一次后拉取 `/m29-direct-dsl` 和 `/dsl`，左侧渲染 M29 direct，右侧渲染主线。

不包含：

- 不替换默认 `/api/tasks/{taskId}/dsl`。
- 不删除 M30/M37/M38/M39/M39.1。
- 不把 M29 direct replay 设为产品默认路线。
- 不做 Auto Layout、Figma Component/Instance、代码生成。
- 不为黑条、搜索框、轮播图写单点规则。

## Backend Design

Pipeline 顺序：

```text
OCR
-> M29 visual primitive graph
-> M29 direct replay variant
-> M29 direct asset publish
-> current mainline M31/M29.1/M29.0.x/M30/M39/M37/M38/M39.1
```

M29 direct variant 使用 `m29_direct` 子目录和独立 asset URL namespace：

```text
storage/m30_1_uploads/{taskId}/m29_direct/
storage/assets/{taskId}/m29_direct/
```

`dsl_results` 仍只保存主线 final DSL：

```text
storage/m30_1_uploads/{taskId}/m30/m30_materialized_dsl.json
```

M29 direct 是实验 variant，不能阻断默认主线。`m29_direct_replay` 或 `m29_direct_asset_publish` 失败时，task 仍可继续完成主线 `/api/tasks/{taskId}/dsl`；`/api/tasks/{taskId}/m29-direct-dsl` 返回 `M29_DIRECT_DSL_NOT_FOUND`。

## Plugin Design

保留原按钮：

```text
Generate from PNG
```

该按钮继续只渲染主线 `/api/tasks/{taskId}/dsl`。

新增实验按钮：

```text
Generate Compare
```

流程：

```text
upload PNG once
-> wait task completed
-> fetch /api/tasks/{taskId}/m29-direct-dsl
-> fetch /api/tasks/{taskId}/dsl
-> render M29 Direct Replay at x=0
-> render Current Mainline at x=page.width+80
```

Root frame 名称：

```text
M29 Direct Replay / {filename}
Current Mainline / {filename}
```

## Acceptance

- 同一 task 下生成两份 DSL。
- `/api/tasks/{taskId}/dsl` 仍返回主线 DSL。
- `/api/tasks/{taskId}/m29-direct-dsl` 返回 M29 direct DSL、summary、warnings、report path 和 stage timings。
- M29 direct image assets 通过 `/files/assets/{taskId}/m29_direct/...` 可访问。
- M29 direct 失败不阻断主线 `/api/tasks/{taskId}/dsl`。
- 插件 `Generate Compare` 在 Figma 中创建左右两个 root frame，互不重叠。
- M29 direct root 和基础 asset id 使用 `m29_direct_*` namespace，避免与主线 DSL 混淆。
- 主线 M30/M38/M39 行为不回归。

## Validation

```bash
cd backend
uv run pytest \
  tests/test_m29_direct_replay.py \
  tests/test_m30_upload_pipeline.py \
  tests/test_routes_tasks.py \
  tests/test_evidence_grounded_dsl_materialization.py -q

uv run pytest -q

cd ..
pnpm run check
git diff --check
git status --short --branch
```

Manual smoke:

```text
start backend
open Figma plugin
choose one PNG
click Generate Compare
inspect left/right drafts in Figma
```

## Notes

这是路线判断工具，不是路线切换。M29 direct 如果在 Figma 肉眼测试中明显优于主线，下一阶段再讨论是否把它变成实验 draft path 开关；本阶段只做并排比较闭环。
