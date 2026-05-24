# M29.4 Stable Design Cluster No-Behavior Split

- 状态：active
- 创建日期：2026-05-24
- 负责人：未指定

## Goal

把 `backend/app/stable_design_cluster.py` 拆成同名 package，降低 M29.4 weak structural evidence 层的维护压力。本阶段只做 no-behavior split：不改 cluster candidate、motif classification、score、dedupe、report schema、artifact path 或 upload pipeline stage。

## Scope

包含：

- `backend/app/stable_design_cluster.py` -> `backend/app/stable_design_cluster/`
- `docs/engineering/current-mainline-code-map.md`

不包含：

- M29.4 cluster 算法或阈值调整。
- M29.5 replay plan 或 materializer 行为。
- API、DSL、storage、stage timing 或 artifact filename 修改。
- 测试语义重写。

## Target Split

```text
backend/app/stable_design_cluster/__init__.py
backend/app/stable_design_cluster/types.py
backend/app/stable_design_cluster/pipeline.py
backend/app/stable_design_cluster/normalization.py
backend/app/stable_design_cluster/candidates.py
backend/app/stable_design_cluster/clusters.py
backend/app/stable_design_cluster/motifs.py
backend/app/stable_design_cluster/scoring.py
backend/app/stable_design_cluster/report.py
backend/app/stable_design_cluster/validation.py
backend/app/stable_design_cluster/geometry.py
```

Public imports must remain compatible, especially:

```python
from app.stable_design_cluster import extract_m294_stable_design_cluster_report
```

## Validation

```bash
cd backend
uv run pytest tests/test_stable_design_cluster.py -q
uv run pytest \
  tests/test_stable_design_cluster.py \
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

- `backend/app/stable_design_cluster.py` 不存在，或只作为极短 compat wrapper；优先不保留。
- New modules have clear responsibility and stay below about 350 LoC.
- M29.4 focused tests and backend regression pass.
- No behavior, schema, threshold, storage, API, or artifact path changes.

## Phase Log

- 2026-05-24: Split `backend/app/stable_design_cluster.py` into `backend/app/stable_design_cluster/` with public import compatibility preserved. Focused regression passed: `cd backend && uv run pytest tests/test_stable_design_cluster.py -q`.
