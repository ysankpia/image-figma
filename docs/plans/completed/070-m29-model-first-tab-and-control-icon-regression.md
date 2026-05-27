# 070 M29 Model-First Tab And Control Icon Regression

- 状态：completed
- 创建日期：2026-05-27
- 负责人：Codex

## Goal

修复 model-first interactive 主链中两个同源可见回归：

1. C-stage controlled structure groups 被写入 DSL root，导致底部 tab/icon/text 被绑定成额外可见组。
2. media 内 action row 的小 icon 已被模型提出候选，但在 perception source compiler 中因过窄的 ownership evidence 被拒绝，无法进入 M29.5 replay。

## Scope

包含：

- `backend/app/plan_materializer/structure.py` 的 controlled structure 输出边界。
- `backend/app/perception_source_compiler/` 的控件内部小 icon ownership 判断。
- 相关单元测试、bug 记录和验证证据。

不包含：

- Renderer、Figma plugin、public DSL schema、API protocol。
- OCR 文本纠错。
- 文件名、路径、任务 id、坐标、文案、主题色或单截图特化。
- 恢复旧 M29.6 -> transparent -> evidence -> promotion loop。

## Steps

1. 将 controlled structure materialization 改回 report-only/diagnostic-only，不再改变 DSL root children。
2. 为 perception source compiler 增加通用 small child icon gate：候选必须被已编译 control parent 包含，模型分数过最低阈值，面积小，文字重叠低或只擦到少量文本边缘，才可进入 `raster_icon / icon_replay`。
3. 增加回归测试：结构组不能把 tab 生成额外可见 group；低分小 icon 可在已接受控件内部进入 source ownership，但 text-sized candidate 仍拒绝。
4. 用最新真实 artifact 或单图复跑验证 `task_95a6381580e9` 类问题。

## Acceptance

- Interactive DSL 中不再出现 `m29_controlled_structure_group` 可见节点。
- C-stage 报告仍存在，作为诊断证据，不创建 visible owner。
- Action row 中已由模型提出的小 icon 候选能通过 parent control evidence 进入 M29.2/M29.5/materializer。
- 底部 tab 的父 media、text、icon 仍由 M29.5 replay 控制，不被额外结构组绑定成一条。
- Materializer 仍只消费 M29.5 replay/cleanup plan，不发明 owner。

## Validation

```bash
cd backend
uv run pytest tests/test_perception_source_compiler.py tests/test_m29_plan_materializer.py -q
uv run pytest tests/test_m29_perception_fate_trace.py tests/test_m29_replay_plan.py -q
git diff --check
```

真实样本复跑：

```bash
cd backend
UPLOAD_PREVIEW_RUNTIME_MODE=interactive uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir <single-sample-dir> \
  --poll-timeout 300
```

实际验证：

```bash
cd backend
uv run pytest tests/test_perception_source_compiler.py tests/test_m29_plan_materializer.py tests/test_m29_perception_fate_trace.py tests/test_m29_replay_plan.py -q
# 73 passed

git diff --check
# pass

UPLOAD_PREVIEW_RUNTIME_MODE=interactive uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /tmp/m29-070-retest2.UBmzF9 \
  --poll-timeout 300
# completedTaskCount=1, backendCrashCount=0, ownershipConflictCount=0
```

真实复跑产物：

```text
taskId=task_a63cb7885ae6
compiledSourceObjectCount=23
compiledRasterIconCount=8
plannedIconReplayCount=25
materializedVisibleNodeCount=139
controlledStructureMaterializationChanged=false
```

Artifact inspection:

```text
DSL root has no m29_controlled_structure_group nodes.
Action row icons materialized as m29_symbol_0052..m29_symbol_0055.
The four icons trace through perception_candidate_*:vertical_label_icon -> M29.2 raster_icon -> M29.5 icon_replay -> materializer.
```

## Notes

第一性原理判断：结构证据不是可见 owner；小 icon 候选不是单靠模型分数进入 source，而是靠 parent control containment、低 text overlap、低修复成本和 M29.5 replay 闭环进入 source ownership。
