# 087 Go M29 VisualTree Group Permission Gate

- 状态: completed
- 创建日期: 2026-05-29
- 完成日期: 2026-05-29
- 所属链路: `services/backend-go` 的 Go M29 VisualTree/Codia-like 结构编译与评测诊断层

## Objective

减少 Go VisualTree 中低证据 synthetic containers 对 Codia 结构评测的污染。当前卡点不是继续调 `xycut` 阈值，而是结构容器、辅助渲染容器和伪背景容器被混在同一棵树里递归、计数和评测。

第一阶段只做窄实现:引入 group permission/provenance 字段，并对 `text_background_group` 与低证据 `spatial_group` 做受控折叠实验。不得改变 source ownership、M29.5 replay plan、Renderer 或 Figma plugin。

## Scope

允许:

- 在 VisualTree node meta/VisualElement processing meta 中增加结构权限和证据来源字段。
- 给 synthetic group 创建点标记 `structural` / `auxiliary`、`parentReason`、`evidenceScore`。
- 在 VisualTree 输出前折叠明确低证据的 auxiliary group。
- 在 `compare_trees.py` batch 输出中增加 precision/F1/container ratio 诊断，但不改原 score 公式。

禁止:

- 不把 Codia guid 或 Codia bbox 作为 Go 编译器输入。
- 不按文件名、样本名、品牌、文案、固定坐标或固定 bbox 写规则。
- 不改变 M29 source ownership、relation graph、replay/materializer/Renderer/plugin 合同。
- 不为了降低容器数牺牲四图最低分到不可控状态；任何退化都必须可解释。

## Acceptance

- 四图评测仍通过，目标保持 `min >= 0.800`；如果 precision/ratio 明显改善但 min 轻微下降，必须记录并回滚或停下来做判断。
- 平均 container ratio 明确低于当前约 `1.54`，`extraByGroupKind.text_background_group` 明显下降。
- `contained_foreground_group`、`contained_slice_group`、`vertical_pair_group` 不应被误折叠。
- `visual_tree_trace.v1.jsonl` 能记录折叠事件及原因。
- `compare_trees.py --batch` 继续输出原 score，同时显示 precision/F1/ratio。

## Validation

```bash
cd services/backend-go
go test ./internal/m29/visualtree/... ./cmd/m29trace/...
go test ./...

cd ../..
python3 -m py_compile services/backend-go/tools/compare_trees.py services/backend-go/tools/compare_trees_test.py
python3 services/backend-go/tools/compare_trees_test.py
bash services/backend-go/tools/eval_4img.sh
python3 services/backend-go/tools/compare_trees.py --batch /tmp/eval_4img/manifest.txt --trace-dir /tmp/eval_4img/eval_trace
git diff --check
git status --short --branch
```

## Completion Notes

本阶段实现了窄版 group permission gate:

- `Meta` / `ProcessingMeta` 新增 `groupRole`、`evidenceScore`，并继续保留 `groupKind`、`parentReason`。
- 高证据 `contained_foreground_group`、`contained_slice_group`、`vertical_pair_group` 标记为 `structural`。
- 纯文本 bbox 合成的 `text_background_group` 标记为 `auxiliary`，permission gate 会折叠低证据实例并丢弃对应 synthetic background leaf。
- 对来自 `xycut_x`、`xycut_y`、`neighbor_component` 的退化 `spatial_group`，仅在无文字后代且短边不超过 `20px` 时折叠；这是针对投影切分产生的薄片包装，不是 child-count 删除规则。
- `group_permission_gate` trace 事件记录 collapse reason、input/output nodes、bbox、metrics 和 thresholds。
- `compare_trees.py --batch` 新增 precision、F1、container ratio 输出，eval trace summary 新增 `f1`，score 公式不变。

四图验证结果:

```text
腾讯动漫018  recall=0.829  precision=0.597  F1=0.694  ratio=1.756  score=0.880
腾讯动漫022  recall=0.714  precision=0.487  F1=0.579  ratio=1.393  score=0.800
荔枝011      recall=0.844  precision=0.743  F1=0.790  ratio=1.094  score=0.891
闲鱼         recall=0.714  precision=0.523  F1=0.604  ratio=1.257  score=0.800

avg_score=0.843
min_score=0.800
avg_container_ratio=1.375
```

相对本阶段前的四图 baseline，综合分保持 `avg=0.843 / min=0.800`，Go 容器数从 `77/47/39/48` 降到 `72/39/35/44`。`extraByGroupKind.text_background_group` 从此前观测的总计 `29` 降到 `14`，`spatial_group` extra 从 `44` 降到 `38`。这不是 1:1 完成，只是把最脏的伪背景和退化空间薄片从结构树里剥离出来。

已执行验证:

```bash
cd services/backend-go
go test ./internal/m29/visualtree/... ./cmd/m29trace/...
go test ./...

cd ../..
python3 -m py_compile services/backend-go/tools/compare_trees.py services/backend-go/tools/compare_trees_test.py
python3 services/backend-go/tools/compare_trees_test.py
bash services/backend-go/tools/eval_4img.sh
python3 services/backend-go/tools/compare_trees.py --batch /tmp/eval_4img/manifest.txt --trace-dir /tmp/eval_4img/eval_trace
```
