# 086 Go M29 Normalized Tree Identity Contract

- 状态: completed
- 创建日期: 2026-05-29
- 所属链路: `services/backend-go` 的 Codia/Go VisualTree 评测诊断层

## Objective

让 `compare_trees.py` 解析出来的 Codia 和 Go normalized tree 节点都具备稳定身份字段。目标是避免 eval trace / `m29trace` 只能靠 `index`、重复 `name` 或近似 `bbox` 串联对象。

## Scope

允许:

- 在 `compare_trees.py` 的 normalized node 中保留 `id`、`sourceId`、`path`、`parentId`。
- 在 eval trace 的 Go container、Codia container、`bestGo`、`bestCodia` 中输出身份字段。
- 让 `m29trace -eval` 展示 Go path 和 best Codia node/path/parent。

禁止:

- 改 `visual_tree.v1.json` 或 `visual_tree_trace.v1.jsonl`。
- 让 Go VisualTree 编译器读取 Codia `guid`。
- 改评分公式、IoU 阈值或 batch stdout 分数格式。

## Acceptance

- Codia normalized node 使用 `guid.sessionID/localID` 生成 `codia:{sessionID}:{localID}`。
- Go normalized node 使用原 Go node id 生成 `go:{nodeId}`。
- eval trace 仍保留旧 `goContainers[*].nodeId = sgroup_*` 兼容字段。
- `m29trace -node sgroup_0030 -eval ...` 能显示 `bestCodiaNodeId: codia:1:130` 和 `bestCodiaPath: /0/3/4/2`。
- 四图评测分数保持 `avg=0.843`、`min=0.800`。

## Validation

```bash
python3 -m py_compile services/backend-go/tools/compare_trees.py
python3 services/backend-go/tools/compare_trees_test.py
cd services/backend-go
go test ./cmd/m29trace/...
go test ./internal/m29/visualtree/... ./cmd/m29trace/...
cd ../..
bash services/backend-go/tools/eval_4img.sh
git diff --check
git status --short --branch
```

## Completion Evidence

完成内容:

- Codia normalized node 保留 `codia:{sessionID}:{localID}`、`sourceId`、`path`、`parentId`。
- Go normalized node 保留 `go:{nodeId}`、原始 `sourceId`、`path`、`parentId`。
- eval trace 的 Go/Codia containers 和 best-match 对象输出身份字段。
- `m29trace -eval` 显示 Go path 和 best Codia node/path/parent。

验证结果:

```text
python3 -m py_compile services/backend-go/tools/compare_trees.py services/backend-go/tools/compare_trees_test.py  PASS
python3 services/backend-go/tools/compare_trees_test.py  PASS
go test ./cmd/m29trace/...  PASS
go test ./internal/m29/visualtree/... ./cmd/m29trace/...  PASS
go test ./...  PASS
bash services/backend-go/tools/eval_4img.sh
  avg=0.843
  min=0.800
git diff --check  PASS
```

查询验证:

```text
m29trace -node sgroup_0030
  bestCodiaNodeId: codia:1:130
  bestCodiaPath: /0/3/4/2
```
