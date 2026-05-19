# M17 DSL Component Annotation And Layer Naming Harness

- 状态：active
- 创建日期：2026-05-17
- 负责人：Codex

## Summary

M17 在 M16 `component-structures` 后新增 component annotation 合同层，把 M16 component/group 结构安全挂回 DSL element 的 `meta` 和 `name`，让后端报告、DSL、Figma layer tree 之间形成可追踪索引。

M17 不切图，不做图标、圆形、三角形、五角星、复杂图形或组件视觉重建，不删除 fallback，不创建 Figma Component/Instance，不创建真实 Figma group，不做 Auto Layout，不改插件 UI/Main，不改变 Figma 可见输出。

## Key Changes

- 新增 `ComponentAnnotationDocument v0.1`。
- 新增持久化目录 `backend/storage/component_annotations/{taskId}.json`。
- 新增只读接口 `GET /api/tasks/{taskId}/component-annotations`。
- 新增 SQLite 表 `component_annotation_results`。
- 新增配置：
  - `COMPONENT_ANNOTATION_ENABLED=true`
  - `COMPONENT_ANNOTATION_LAYER_NAMING=true`
  - `COMPONENT_ANNOTATION_MIN_CONFIDENCE=0.70`
- 上传链路在 M16 component structure 后执行 M17 annotation。
- DSL 只修改已有 element 的 `name` 和 `meta`，并追加 M17 meta 统计。

## Behavior

M17 只做确定性 ID join，不按中文文案、不按单张图绝对坐标、不靠 bbox 二次猜测：

```text
M16 component.bindingIds
-> M15 binding.id
-> binding.ocrBlockId
-> DSL elements:
   visible_text_{ocrBlockId}
   cover_{ocrBlockId}
   text_{safe_id(ocrBlockId)}
```

可注解元素：

- `visible_text_replacement`
- `text_replacement_cover`
- hidden `candidate_text`
- fallback region 作为 fallback context

M17 只允许修改：

```text
name
meta
```

M17 不允许修改：

```text
type
role
layout
style
content
children
source/imageFill
visible
asset
```

fallback region 只标记 `annotationRole=fallback_context`，不绑定业务 `componentId`。`original_ref` 只可命名为 `Original Reference`，不绑定业务 component。

## API And Storage

`GET /api/tasks/{taskId}/component-annotations`：

- task 不存在 -> `TASK_NOT_FOUND`
- result 不存在或文件缺失 -> `COMPONENT_ANNOTATION_NOT_FOUND`
- completed -> 返回 `annotations`、`groupHints`、`unannotatedElementIds`、`unresolvedComponentIds`、`warnings`、`meta`
- failed/skipped -> 返回 `success: true`，并带 `status`、`warnings`、`meta`、`error`

新增错误码：

```text
COMPONENT_ANNOTATION_NOT_FOUND
COMPONENT_ANNOTATION_FAILED
COMPONENT_ANNOTATION_VALIDATION_FAILED
```

新增 DSL meta：

```text
m17_component_annotation
componentAnnotationCount
componentAnnotatedElementCount
componentUnannotatedElementCount
componentGroupHintCount
```

## Failure Strategy

- `COMPONENT_ANNOTATION_ENABLED=false` 时不生成 result，不改 DSL。
- M17 failed/skipped 不影响 upload completed。
- validation failed 保存 failed document，写 `error_logs`，`/dsl` 回退 M16 输出。
- M17 不返回未校验 DSL。

## Test Plan

必须通过：

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
```

覆盖点：

- 默认上传生成 component annotation report 和 DSL M17 meta。
- `COMPONENT_ANNOTATION_ENABLED=false` 不生成 report，DSL 保持 M16 输出。
- `/component-annotations` 覆盖 completed、TASK_NOT_FOUND、COMPONENT_ANNOTATION_NOT_FOUND。
- visible text、cover、hidden candidate text 通过同一 `ocrBlockId` 绑定到同一 component。
- fallback region 只标 fallback context，不绑定业务 component。
- group hints 覆盖 legend group、bottom nav group、shortcut grid、page structure。
- M17 不新增可见 DSL 节点，不改 layout/style/content/visible/source/imageFill。
- renderer 已尊重 DSL element `name`，M17 layer naming 不需要改插件协议。

## Assumptions

- M17 默认开启，因为只改 DSL annotation/name，不改变可见输出。
- M17 的 layer naming 使用已有 DSL `name` 字段和 renderer 行为。
- M17 不切图，PNG Tools crop 能力留给 M18+。
- M18 再考虑 local asset slicing；M19 再考虑 partial fallback replacement；M20 再考虑 componentization/grouping/layout experiment。
