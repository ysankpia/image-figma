# M29.5 Replay Plan No-Behavior Split

- 状态：active
- 创建日期：2026-05-24
- 负责人：未指定

## Goal

把 `backend/app/m29_replay_plan.py` 拆成同名 package。本阶段只做 no-behavior split：不改 replay action mapping、priority、dedupe、cleanup authorization、node budget、report schema、artifact path 或 upload pipeline stage。

## Scope

包含：

- `backend/app/m29_replay_plan.py` -> `backend/app/m29_replay_plan/`
- `docs/engineering/current-mainline-code-map.md`

不包含：

- M29.2 ownership、M29.3 relation、M29.4 cluster 行为修改。
- materializer、Renderer、plugin 行为修改。
- API、DSL、storage、stage timing 或 artifact filename 修改。
- 测试语义重写。

## Target Split

```text
backend/app/m29_replay_plan/__init__.py
backend/app/m29_replay_plan/types.py
backend/app/m29_replay_plan/pipeline.py
backend/app/m29_replay_plan/normalization.py
backend/app/m29_replay_plan/lookups.py
backend/app/m29_replay_plan/decisions.py
backend/app/m29_replay_plan/cleanup.py
backend/app/m29_replay_plan/budget.py
backend/app/m29_replay_plan/report.py
backend/app/m29_replay_plan/validation.py
backend/app/m29_replay_plan/utils.py
```

Public imports must remain compatible:

```python
from app.m29_replay_plan import build_m295_replay_plan
```

## Validation

```bash
cd backend
uv run pytest tests/test_m29_replay_plan.py -q
uv run pytest \
  tests/test_m29_replay_plan.py \
  tests/test_m29_plan_materializer.py \
  tests/test_upload_preview_pipeline.py \
  -q
uv run pytest -q
cd ..
git diff --check
git status --short --branch
```

## Acceptance

- `backend/app/m29_replay_plan.py` 不存在，或只作为极短 compat wrapper；优先不保留。
- New modules have clear responsibility and stay below about 350 LoC.
- M29.5 focused tests and backend regression pass.
- Cleanup targets remain authorized only by replay plan logic.
- No behavior, schema, threshold, storage, API, or artifact path changes.

## Phase Log

- 2026-05-24: Split `backend/app/m29_replay_plan.py` into `backend/app/m29_replay_plan/` with public import compatibility preserved. Focused regression passed: `cd backend && uv run pytest tests/test_m29_replay_plan.py -q`.
