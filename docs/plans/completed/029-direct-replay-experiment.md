# M29 Direct Replay Experiment

- 状态：completed
- 创建日期：2026-05-22
- 负责人：未指定

## Goal

在隔离分支 `experiment/m29-direct-replay` 上验证一条更短的 PNG -> DSL 路径：直接把 M29 visual primitive graph 和 OCR text boxes 回放成扁平 DSL，判断它能否先产出高保真、可编辑、可拖动的 Figma draft。

这个实验不推翻当前 M30/M37/M38/M39 主线。它只回答一个问题：结构恢复前，是否应该先把 M29 的强像素拆分能力变成一个可用的 flat replay 输出。

## Scope

包含：

- 新增 branch-only 的 `m29_direct_replay` 模块和 CLI。
- 支持读取 source PNG、M29 `nodes.json`、OCR `ocr.json`，也支持没有现成 M29 时临时运行 M29。
- 输出 `m29_direct_replay_dsl.json` 和 `m29_direct_replay_report.json`。
- OCR text 优先于重叠的 M29 raster symbol/image/shape。
- M29 image/symbol/simple shape 以 DSL visible node 回放，并让 fallback 对已回放 bbox 让位。
- 用测试和两张样图验证输出质量和节点数量。

不包含：

- 不接入默认上传 pipeline。
- 不替换 M30/M37/M38/M39。
- 不做 Auto Layout、Figma Component/Instance 或代码生成。
- 不把模型、UIC 或 Figma MCP 输出当内部真值源。
- 不为黑条、搜索框、轮播图写单点规则。

## Steps

1. 新增 ADR，记录这是旁路验证，不是主线替换。
2. 新增 `backend/app/m29_direct_replay.py`，实现 PNG/M29/OCR 到 DSL/report 的纯函数。
3. 新增 `backend/scripts/run_m29_direct_replay_experiment.py`，支持裸图、现成 M29、现成 OCR 三种输入。
4. 新增 `backend/tests/test_m29_direct_replay.py`，覆盖 OCR 优先、asset replay、fallback 去重、blocked 跳过和节点预算。
5. 跑当前上传任务和两张样图，对比 M30/M38 baseline 与 M29 direct replay 的 text/image/symbol/visible node 数量和重影风险。

## Acceptance

- `m29_direct_replay_dsl.json` 保持 DSL v0.1 形状，可由现有 Renderer 消费。
- OCR text 能成为 editable text node，且高重叠 M29 raster primitive 不重复物化。
- M29 image/symbol 能成为独立 image layer。
- fallback 对 replayed bbox 让位，避免显著双层重影。
- blocked/unknown 不直接物化，report 能说明跳过原因。
- visible node 数量受预算保护，不生成不可操作的图层爆炸。

## Validation

```bash
cd backend
uv run pytest tests/test_m29_direct_replay.py -q

uv run python scripts/run_m29_direct_replay_experiment.py \
  --input "/Users/luhui/Library/Application Support/PixPin/Temp/PixPin_2026-05-21_18-58-59.png" \
  --output-dir storage/m29_direct_replay_pixpin_185859 \
  --overwrite

uv run python scripts/run_m29_direct_replay_experiment.py \
  --input "../docs/prototypes/figma-mcp-uploaded-page/assets/figma-reference.png" \
  --output-dir storage/m29_direct_replay_figma_reference \
  --overwrite
```

有效对比还应使用现有上传任务的 OCR/M29：

```bash
cd backend
uv run python scripts/run_m29_direct_replay_experiment.py \
  --input storage/uploads/task_0ce422b55706/original.png \
  --m29-json storage/m30_1_uploads/task_0ce422b55706/m29/nodes.json \
  --ocr-json storage/m30_1_uploads/task_0ce422b55706/ocr/ocr.json \
  --output-dir storage/m29_direct_replay_task_0ce422b55706 \
  --overwrite
```

## Notes

- 没有 OCR 的裸 M29 输出会把文字当 raster evidence；这种输出只能验证 pixel splitting，不能验证 editable text。
- 如果实验效果好，下一阶段再加实验 env 开关接上传链路；如果效果差，回到 M39.1.1/M39.2 主线。
