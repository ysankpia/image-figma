# M29 Upload Preview Pipeline No-Behavior Split

- 状态：completed
- 创建日期：2026-05-24
- 完成日期：2026-05-24
- 负责人：未指定

## Goal

把 upload preview pipeline 从单文件拆成职责清楚的 package，降低后续调整主链时误伤 M29 owner/replay/materialization 合同的概率。

本阶段只做无行为变化拆分，不改 API、DSL、storage、stage names、progress values、task messages 或 `UploadPreviewStageTimings` schema。

## Changes

- 新增 `backend/app/upload_preview/` package。
- `routes/upload_preview.py` 改为从 `app.upload_preview` 导入 `run_upload_preview_pipeline`。
- 删除旧 `backend/app/upload_preview_pipeline.py`。
- 拆分模块：
  ```text
  pipeline.py: run_upload_preview_pipeline / run_pipeline
  types.py: UploadPreviewPipelineError / UploadPreviewArtifactPolicy / UploadPreviewProfile
  paths.py: UploadPreviewPaths / pipeline_paths
  timings.py: StageTiming / run_stage / write_stage_timings
  task_state.py: update_task / fail_task / complete_task
  stages.py: OCR and M29/M29.2/M29.3/M29.4/M29.5/materialization wrappers
  assets.py: materialized image asset publish helpers
  ```
- 更新 pipeline failure injection test、current code map 和 completed plan index。

## Acceptance

- `POST /api/upload-preview` 主流程不变。
- `/api/tasks/{taskId}/dsl` 和 `/api/tasks/{taskId}/materialization` 输出不变。
- `storage/upload_previews/{taskId}` layout 不变。
- `stage_timings.json` schema and stage names 不变。
- `backend/app/upload_preview/*.py` 每个文件低于约 350 行。
- 旧 `upload_preview_pipeline.py` 不存在，且无旧 import。

## Validation

阶段回归命令：

```bash
cd backend
uv run pytest tests/test_upload_preview_pipeline.py -q
uv run pytest \
  tests/test_routes_tasks.py \
  tests/test_upload_flow.py \
  tests/test_config_env.py \
  tests/test_m29_plan_materializer.py \
  tests/test_m29_replay_plan.py \
  tests/test_source_ui_physical_graph.py \
  -q
uv run pytest -q
cd ..
pnpm -r run test
pnpm -r run typecheck
pnpm --filter @image-figma/figma-plugin run build
git diff --check
```

静态检查：

```bash
wc -l backend/app/upload_preview/*.py
rg -n "from \\.upload_preview_pipeline|from app\\.upload_preview_pipeline|import app\\.upload_preview_pipeline|upload-m30-preview|m30_upload_pipeline" backend/app backend/tests figma-plugin/src
```
