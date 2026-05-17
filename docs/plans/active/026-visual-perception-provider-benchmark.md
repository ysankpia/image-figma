# M26 Visual Perception Provider Benchmark Harness

- 状态：completed
- 创建日期：2026-05-18
- 负责人：Codex

## Summary

M26 停止继续扩张 M25 式 region probe，新增 visual perception provider benchmark harness。它把当前规则结果、可选 OpenCV、可选 SAM2 和可选 UIED 外部 adapter 放进统一合同里比较，用同一套速度、候选数量、blocked 数量、误检代理指标和 overlay 判断下一阶段到底该走哪条感知路线。

M26 是 benchmark，不是 production replacement。它默认关闭，不改变 DSL，不改变 Figma 可见输出，不裁新 icon asset，不把 OpenCV/SAM2/UIED 输出当 DSL 权威，不做 Codia 式全量拆层，不默认下载模型，也不把 torch/sam2/opencv-python 写进主生产依赖。

## Key Changes

- 新增 `backend/app/perception_benchmark.py`。
- 新增存储 `backend/storage/perception_benchmarks/{taskId}.json`。
- 新增 debug overlay：`backend/storage/assets/{taskId}/debug/perception_overlay_rules.png`、`perception_overlay_opencv.png`、`perception_overlay_sam2.png`、`perception_overlay_uied.png`。
- 新增只读接口 `GET /api/tasks/{taskId}/perception-benchmark`。
- 新增 SQLite 表 `perception_benchmark_results`。
- 新增 asset role：`asset_perception_overlay_rules`、`asset_perception_overlay_opencv`、`asset_perception_overlay_sam2`、`asset_perception_overlay_uied`。
- 新增 smoke 脚本 `backend/scripts/run_m26_perception_smoke.py`。

配置默认值：

```bash
PERCEPTION_BENCHMARK_ENABLED=false
PERCEPTION_BENCHMARK_PROVIDERS=current_rules,opencv
PERCEPTION_BENCHMARK_MAX_CANDIDATES_PER_PROVIDER=300
PERCEPTION_BENCHMARK_OVERLAY_ENABLED=true
PERCEPTION_OPENCV_ENABLED=false
PERCEPTION_OPENCV_IMPORT_NAME=cv2
PERCEPTION_SAM2_ENABLED=false
PERCEPTION_SAM2_MODEL_CFG=
PERCEPTION_SAM2_CHECKPOINT=
PERCEPTION_SAM2_DEVICE=auto
PERCEPTION_SAM2_MAX_IMAGE_EDGE=1280
PERCEPTION_SAM2_MAX_MASKS=300
PERCEPTION_UIED_ENABLED=false
PERCEPTION_UIED_COMMAND=
```

## Contract

`PerceptionBenchmarkDocument v0.1` 包含：

- `providers`：每个 provider 的 status、available、elapsedMs、candidateCount、blockedCount、误检代理指标、candidates、blocked、overlay、warnings 和 error。
- `comparison`：providerScores、recommendedProvider 和推荐原因。
- `meta`：providerCount、totalCandidateCount、totalBlockedCount、elapsedMs。
- `warnings`：provider unavailable、依赖缺失、overlay 写入失败等非致命问题。

允许 provider：

```text
current_rules
opencv
sam2
uied
```

允许 provider status：

```text
completed
failed
skipped
unavailable
```

允许 candidate kind：

```text
icon_candidate
text_like
component_candidate
image_candidate
card_candidate
button_candidate
nav_candidate
unknown_visual
```

M26 不追加 DSL meta。原因是 benchmark 是评估层，不是上传质量阶段；把实验数据塞进 DSL 会污染 Renderer 合同。

## Provider Behavior

- `current_rules_provider`：读取 M20/M22/M25 已有候选并转成统一 perception candidates。它是 baseline，不重新跑复杂规则。
- `opencv_provider`：只有 `PERCEPTION_OPENCV_ENABLED=true` 且 `PERCEPTION_OPENCV_IMPORT_NAME` 可 import 时运行。M26 v0.1 使用轻量 connected-component 风格的像素候选生成输出 bbox 和 overlay，不裁图、不改 DSL、不进入 M25/M27。
- `sam2_provider`：只有 `PERCEPTION_SAM2_ENABLED=true`、checkpoint 存在且 `torch`/`sam2` 可 import 时才会尝试。M26 v0.1 已接通 optional automatic mask generation，按 `PERCEPTION_SAM2_MAX_IMAGE_EDGE` 缩放推理并把 bbox 映射回原图；缺模型或依赖时写 `unavailable`，不让上传失败。
- `uied_provider`：只支持 `PERCEPTION_UIED_COMMAND` 外部命令 adapter。命令从 stdin 读 PNG bytes，stdout 输出 JSON candidates；命令缺失或失败时 provider failed/unavailable，不影响整个 document。

质量代理指标包括：

- textStrokeFalsePositiveCount
- borderFalsePositiveCount
- illustrationFalsePositiveCount
- bedMapFalsePositiveCount
- statusBarFalsePositiveCount
- duplicateExistingIconCount
- bottomNavLikelyHitCount
- buttonArrowLikelyHitCount
- cardTileLikelyHitCount
- roomStatusLikelyHitCount

这些指标不是人工真值，只用于横向比较 provider。

## Failure Behavior

- `PERCEPTION_BENCHMARK_ENABLED=false`：正常 upload 不生成 result，`/perception-benchmark` 返回 `PERCEPTION_BENCHMARK_NOT_FOUND`。
- provider 依赖缺失：provider status 为 `unavailable`，document 仍 completed。
- 单个 provider exception：provider status 为 `failed`，document 仍 completed。
- 全部 provider failed/unavailable：document 仍保存可追踪结果；实现不阻断 upload。
- overlay 写入失败：provider completed，但 overlay 为 null，warnings 记录。
- document validation failed：保存 failed document，写 `error_logs(stage=perception_benchmark)`，不影响 DSL。

## Test Evidence

- 新增 `backend/tests/test_perception_benchmark.py`。
- 覆盖默认关闭不生成 result，DSL 不出现 M26 meta。
- 覆盖显式开启生成 report、current_rules overlay asset 和 SQLite summary。
- 覆盖 `/perception-benchmark` missing task、missing result、missing file。
- 覆盖 current_rules provider 把 M25 candidates 转成统一合同。
- 覆盖 OpenCV disabled/dependency missing 进入 unavailable。
- 覆盖 SAM2 checkpoint missing 进入 unavailable。
- 覆盖 UIED mock command JSON 转成 unified candidates。

已跑：

```bash
cd backend
uv run pytest tests/test_perception_benchmark.py -q
uv run pytest tests/test_upload_flow.py tests/test_icon_business_candidate.py tests/test_icon_placement_plan.py tests/test_perception_benchmark.py -q
```

七张学生端 smoke 脚本：

```bash
cd backend
uv run python scripts/run_m26_perception_smoke.py --providers current_rules,opencv
```

默认输出：

```text
backend/storage/m26_perception_smoke/m26_perception_summary.json
backend/storage/m26_perception_smoke/m26_perception_summary.md
```

已保留的单图实测证据：

```text
backend/storage/m26_perception_smoke_one_opencv_restored_20260518_012631/
opencv: 124 candidates, 59 blocked, 277ms

backend/storage/m26_perception_smoke_one_sam2_tiny_20260518_014305/
sam2: 21 candidates, 10 blocked, 9268ms

backend/storage/m26_perception_smoke_one_uied_stdoutfix_20260518_015742/
uied: 75 candidates, 35 blocked, 724ms
```

结论：

- OpenCV 恢复到第一版高召回后速度很好，但噪声和 blocked 仍多，适合作为快速 baseline 或召回源。
- SAM2 tiny 速度接近可接受离线阈值，候选更干净，更适合 M27 做 visual candidate filtering harness。
- UIED 结果数量可用，但旧项目 adapter/兼容成本高、误检也不少，不值得 vendoring，只保留外部 adapter。

## Next

M27 不应继续盲目堆 region rules。基于当前 smoke，M27 应做 SAM2 visual candidate filtering harness：用 SAM2 产生更干净的 mask/bbox proposals，再用现有 text/cover/candidate_text/exclusion/role 规则过滤；OpenCV 保留为快速 baseline 或召回对照，UIED 只保留外部 adapter。
