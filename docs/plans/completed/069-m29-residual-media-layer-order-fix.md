# 069 M29 Residual Media Layer Order Fix

- 状态：completed
- 创建日期：2026-05-27
- 完成日期：2026-05-27
- 负责人：Codex

## Goal

Fix the model-first M29 regression where a parent residual media image renders above its promoted foreground claims. The repair must be ownership-driven and must not special-case text, filenames, task ids, fixed coordinates, brands, or theme colors.

## Source Chain

Observed task:

```text
task_89e156fcbbb0
```

Observed source:

```text
/Users/luhui/Downloads/城邦图/修好/ChatGPT Image 2026年5月25日 18_43_05 1.png
```

Facts:

```text
perception_candidate_0002
-> m292_perception_control_0002
-> m295_plan_0004 shape_replay
-> m29_shape_0004
```

The foreground button shape exists and has the correct fill. The broken output comes from `m29_image_0040`, the parent residual media image, rendering above the shape after cleanup.

## Contract

M29.5 remains the only source of visible replay order and cleanup authorization. Materializer remains an executor.

Layer order rule:

```text
If a foreground replay item claims pixels from a parent media/control source object, the parent residual replay must be ordered before the foreground item.
```

Evidence for that dependency can come from:

```text
cleanupTargets[].target == copied_image_asset
sourceEvidence.mediaSourceObjectId
sourceEvidence.parentControlSourceObjectId
sourceEvidence.foregroundClaimId
```

## Scope

Allowed:

- M29.5 plan sorting.
- Targeted M29.5 regression tests.
- Bug and plan documentation.

Forbidden:

- Renderer/Figma/plugin patches.
- Materializer inventing source ownership.
- Sample-specific matching.
- Public API, DSL schema, or protocol changes.

## Validation

Targeted:

```bash
cd backend
uv run pytest tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py -q
```

Sample:

```bash
cd backend
UPLOAD_PREVIEW_RUNTIME_MODE=interactive uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /tmp/m29-residual-layer-order-sample \
  --poll-timeout 300
```

Hygiene:

```bash
git diff --check
git status --short --branch
```

## Completion Evidence

Implemented M29.5 dependency-aware layer ordering. The ordering is driven by copied-image cleanup targets and foreground-claim parent evidence, not by filename, visible text, coordinates, or theme color.

Targeted validation:

```bash
cd backend
uv run pytest tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py -q
# 51 passed

uv run pytest tests/test_perception_source_compiler.py tests/test_m29_perception_fate_trace.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_ownership_conservation.py -q
# 96 passed
```

Real sample validation:

```bash
cd backend
UPLOAD_PREVIEW_RUNTIME_MODE=interactive uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /tmp/m29-residual-layer-order-sample.Ln0uOm \
  --poll-timeout 300
```

Result:

```text
taskId=task_c946c53cb1be
completedTaskCount=1
backendCrashCount=0
missingArtifactCount=0
ownershipConflictCount=0
```

Key artifact order:

```text
m29_image_0036
-> m29_shape_0036
-> m29_text_0012
```
