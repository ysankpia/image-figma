# 数据模型

当前产品数据模型属于 Slice Studio：

```text
apps/slice-studio/storage/app.sqlite
apps/slice-studio/storage/projects/{projectId}/originals/
apps/slice-studio/storage/projects/{projectId}/exports/
```

Saved projects, pages, and SliceRecord rows are the live edit/export truth. `assets.zip` and `project.zip/design.pen` are derived artifacts.

下面的 Draft task model 是历史/延后 Go Draft route 记录。只有明确恢复 `/api/draft-preview` 时才作为实现参考。

## Runtime State

Go task 状态由 `services/backend-go/internal/app/task` 定义。

状态：

```text
queued
running
completed
failed
```

阶段：

```text
draft_queued
ocr
m29_physical_evidence
vision_detector
vision_review
draft_assemble
draft_assets
draft_validate
draft_export
draft_completed
draft_failed
draft_panic
```

Task 对外暴露：

```text
taskId
status
stage
progress
message
artifacts
error
warnings
```

内部字段如 `DSLPath`、`OutputDir` 只用于服务端文件定位，不进入公共合同。

## File Payloads

每个 Draft task 的事实 payload 存在 task 目录中。默认根目录由 `DRAFT_SERVER_STORAGE_ROOT` 控制；未配置时使用 Go backend 本地 storage。

典型布局：

```text
source.png
compile/
  ocr.json
  m29/
    m29_physical_evidence.v1.json
  vision/
    ui_detector_candidates.v1.json
    ui_candidate_review.v1.json
    ui_detector_report.md
    ui_detector_overlay.png
    vision_detector_fallback.v1.json
    raw_model_response/
  draft/
    editable_layer_graph.v1.json
    draft_runtime.dsl.v1.json
    draft_validation_report.md
  assets/
    asset_manifest.json
    *.png
  logs/
    task_report.md
```

Vision artifacts 是可选证据。Vision 成功时写入 candidates/report/overlay/raw responses；Vision 失败时写入 `vision_detector_fallback.v1.json` 并把 warning 暴露到 task status。Completed task 必须有 Draft graph、Draft Runtime DSL、validation report 和可解析 assets。

## Historical Draft Product Contracts

历史 Draft 跨模块合同是文件/JSON 合同，不是数据库表：

```text
m29_physical_evidence.v1.json
ui_detector_candidates.v1.json
ui_candidate_review.v1.json
editable_layer_graph.v1.json
draft_runtime.dsl.v1.json
asset_manifest.json
draft_validation_report.md
```

版本化 artifact 名称是合同的一部分。行为或字段不兼容变更必须更新对应 architecture docs、active plan 和测试。

## In-Memory Task Limitation

开发期 `draftserver` 重启后不会恢复历史 task。插件如果正在 poll 一个已丢失 task，应收到 `TASK_NOT_FOUND`，用户重新上传即可。

如果后续需要跨重启恢复，先做单独计划。最低实现应是写入一个 task index JSON，而不是直接引入复杂队列或数据库。

## Historical Python Preview Data

`backend/` 里的 SQLite schema、`tasks/assets/dsl_results/ocr_results/error_logs`、`storage/upload_previews/{taskId}` 等属于历史 Python `/api/upload-preview` preview path。

它们不是当前 Slice Studio 数据模型。除非任务明确针对 Python preview，否则不要以这些表、路径或 stage 名称作为新功能依据。

## Non-Goals

当前阶段不做：

```text
持久任务队列
多租户数据库
任务恢复
远程对象存储
历史任务列表
质量看板数据库
```
