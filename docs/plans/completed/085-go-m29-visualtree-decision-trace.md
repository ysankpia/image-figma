# 085 Go M29 VisualTree Decision Trace

- 状态: completed
- 创建日期: 2026-05-29
- 所属链路: `services/backend-go` 的 M29 VisualTree 编译层

## Objective

给 `m29visualtree` 建立 report-only 决策追踪链路。目标不是普通 stdout 日志,而是让每个 synthetic group 都能追到创建原因、输入节点、父节点、bbox、阈值、metrics 和后续 Codia eval verdict。

## Scope

允许:

- 新增 `visual_tree_trace.v1.jsonl` 和 `visual_tree_trace_report.md`。
- 新增只读 `cmd/m29trace` 查询工具。
- 扩展 `compare_trees.py` 的可选诊断输出,保持现有评分公式和默认 stdout 不变。
- 修复 `eval_4img.sh` 的输出目录准备问题,并让它额外生成 eval trace。

禁止:

- 改 `visual_tree.v1.json` / `visual_element.v1.json` 行为。
- 调整 `xycut` 阈值、分组规则或容器折叠策略。
- 引入语义节点类型、样本名、坐标、文案、品牌或主题特化规则。
- 扩展到 Python FastAPI 主链、Renderer 或 Figma plugin。

## Acceptance

- 每个 `Meta.Synthetic=true` 且有 ID 的节点都有对应 create trace event。
- trace event 覆盖 containment、physical background、background split、contained pair/slice、vertical pair、text background、xycut、neighbor components、cluster wrap/flatten、skip xycut 和 absorb straggler。
- `m29trace -node` 能解释指定节点的 create event; 传入 eval trace 时能显示 match/extra 和 best Codia IoU。
- 四图评测分数保持当前 baseline: avg `0.843`, min `0.800`。

## Validation

```bash
cd services/backend-go
go test ./internal/m29/visualtree/... ./cmd/m29trace/...
go test ./...

cd ../..
bash services/backend-go/tools/eval_4img.sh
python3 services/backend-go/tools/compare_trees.py --batch /tmp/eval_4img/manifest.txt --trace-dir /tmp/eval_4img/eval_trace
git diff --check
git status --short --branch
```

## Completion Evidence

完成内容:

- `m29visualtree` 新增 `visual_tree_trace.v1.jsonl` 和 `visual_tree_trace_report.md`。
- trace 覆盖 token filtering、containment、physical background、background split、contained pair/slice、vertical pair、text background、XY-cut、neighbor components、cluster wrap/flatten、skip xycut 和 straggler absorb。
- 新增只读 CLI `cmd/m29trace`，支持 `-summary`、`-node` 和叠加 eval trace。
- `compare_trees.py` 保持原 stdout 和 score 公式不变，新增 `--trace-dir` 输出 `case_###_visual_tree_eval_trace.json`。
- `eval_4img.sh` 现在准备 `masks/crops` 目录，并默认生成 eval trace artifact。

验证结果:

```text
go test ./internal/m29/visualtree/... ./cmd/m29trace/...  PASS
go test ./...                                            PASS
python3 -m py_compile services/backend-go/tools/compare_trees.py  PASS
bash services/backend-go/tools/eval_4img.sh
  avg=0.843
  min=0.800
```

四图行为保持不变，trace report 中 synthetic orphan 列表为空；`m29trace` 已用 t018 的 extra `sgroup_0009` 验证能显示创建原因、metrics/thresholds、eval verdict 和 best Codia IoU。
