# 088 Go M29 Offline Group Evidence Audit

- 状态: completed
- 创建日期: 2026-05-29
- 完成日期: 2026-05-29
- 所属链路: `services/backend-go` 的 Go M29 VisualTree/Codia-like 结构评测诊断层

## Objective

用现有 `visual_tree.v1.json`、`visual_tree_trace.v1.jsonl` 和 `visual_tree_eval_trace.json` 做离线 join，分析 `matched` vs `extra` group 的可计算特征分布。目标是为下一阶段 permission v2 提供证据，不新增 Go VisualTree runtime artifact，不改变 compiler 输出，不改 score 公式。

## Scope

允许:

- 新增 `services/backend-go/tools/audit_group_evidence.py` 离线分析脚本。
- 新增轻量 Python 单测。
- 脚本读取 eval trace、decision trace、visual tree，并按 Go `nodeId` join。
- 输出 groupKind、parentReason、spatialDepth、childCount、containsText、shortSide、areaRatio、childKinds 等 matched/extra 分布。
- 输出内置候选规则的 backtest: `wouldCollapse`、`extraCollapsed`、`matchedLost`、`precision`、`recallRisk`。

禁止:

- 不新增 `visual_tree_group_evidence.v1.json` 或其他 Go runtime artifact。
- 不修改 Go VisualTree compiler、VisualElement 输出、M29 source ownership、M29.5 replay plan、Renderer 或 plugin。
- 不把 Codia guid、Codia bbox、样本名、文案、固定坐标作为生产规则输入。
- 不在本阶段实现 permission v2；本阶段只做决策证据。

## Inputs

单图:

```bash
python3 services/backend-go/tools/audit_group_evidence.py \
  --tree /tmp/eval_4img/t018/visual_tree.v1.json \
  --trace /tmp/eval_4img/t018/visual_tree_trace.v1.jsonl \
  --eval /tmp/eval_4img/eval_trace/case_001_visual_tree_eval_trace.json
```

四图:

```bash
python3 services/backend-go/tools/audit_group_evidence.py \
  --batch /tmp/eval_4img/manifest.txt \
  --eval-dir /tmp/eval_4img/eval_trace
```

## Acceptance

- 单图和四图模式都能输出 `spatial_group` matched/extra 分布。
- 每个 eval trace 中的 Go container 能 join 到当前 `visual_tree.v1.json` 节点；synthetic group 能尽量 join 到 create event，缺失时列出 count。
- 输出 `parentReason`、`spatialDepth`、`childCount`、`containsText`、`shortSideBin`、`areaRatioBin`、`childKinds` 分布。
- 输出 top extra signatures。
- 输出至少一个候选规则 backtest，默认覆盖当前已上线规则 `projection_no_text_shortSide<=20`，用于验证规则杀的是 extra 还是 matched。
- 只读分析，不改变四图分数和 `/tmp/eval_4img` 生成方式。

## Validation

```bash
python3 -m py_compile services/backend-go/tools/audit_group_evidence.py services/backend-go/tools/audit_group_evidence_test.py
python3 services/backend-go/tools/audit_group_evidence_test.py
bash services/backend-go/tools/eval_4img.sh
python3 services/backend-go/tools/audit_group_evidence.py --batch /tmp/eval_4img/manifest.txt --eval-dir /tmp/eval_4img/eval_trace
git diff --check
git status --short --branch
```

## Completion Notes

已新增 `services/backend-go/tools/audit_group_evidence.py`。该脚本只读现有 artifacts:

```text
visual_tree.v1.json
visual_tree_trace.v1.jsonl
visual_tree_eval_trace.json
```

脚本不会要求 Go compiler 写新的 runtime artifact。它按 Go `nodeId` join 当前树节点、create event 和 eval verdict，然后输出 matched/extra 的分布表与候选规则 backtest。

四图 audit 关键结果:

```text
groupKind=spatial_group
records=190
treeJoinMissing=0
syntheticCreateEventMissing=0
selected=79 matched=41 extra=38 precision=0.519

parentReason:
xycut_y              matched=23 extra=24 precision=0.489
xycut_x              matched=11 extra=11 precision=0.500
neighbor_component   matched=7  extra=3  precision=0.700

containsText:
true                 matched=39 extra=31 precision=0.557
false                matched=2  extra=7  precision=0.222

projection_no_text_shortSide<=20:
wouldCollapse=0 extraCollapsed=0 matchedLost=0

projection_no_text_shortSide<=32:
wouldCollapse=6 extraCollapsed=5 matchedLost=1 rulePrecision=0.833 recallRisk=0.024
```

这说明当前上线的 `shortSide<=20` 退化 spatial group 规则已经把可安全折叠的薄片清空；继续把 spatial 阈值放宽到 `32px` 会开始误伤 matched group。

全量视角还暴露了更干净的下一阶段候选:

```text
layer_no_text_shortSide<=8:
wouldCollapse=6 extraCollapsed=6 matchedLost=0 rulePrecision=1.000 recallRisk=0.000
```

这指向下一阶段不应继续盲目折 `spatial_group`，而应优先审查/处理无文字的 tiny physical Layer/render wrapper。

已执行验证:

```bash
python3 -m py_compile services/backend-go/tools/audit_group_evidence.py services/backend-go/tools/audit_group_evidence_test.py
python3 services/backend-go/tools/audit_group_evidence_test.py
bash services/backend-go/tools/eval_4img.sh
python3 services/backend-go/tools/audit_group_evidence.py --batch /tmp/eval_4img/manifest.txt --eval-dir /tmp/eval_4img/eval_trace
python3 services/backend-go/tools/audit_group_evidence.py --batch /tmp/eval_4img/manifest.txt --eval-dir /tmp/eval_4img/eval_trace --group-kind all
```
