# 106.5 PSD-like Python OCR Product Readiness

- 状态：active
- 创建日期：2026-06-02
- 范围：`services/psdlike-python`

## Summary

本阶段把真实 OCR 能力接进 clean PSD-like Python service，使当前产品路径支持：

```text
PNG-only request
-> OCR artifact
-> PSD-like physical ownership pipeline
-> layer_stack / Draft Runtime DSL / preview / diagnostics
```

第一性原理边界：

```text
PNG pixels = physical truth
OCR = text truth
model_evidence = semantic hint
PSD-like Python = current usable product path
old backend/backend-python = reference only
```

## Scope

包含：

- 在 `services/psdlike-python` 内实现独立 OCR provider/cache。
- API 在未上传 OCR artifact 时自动运行真实 OCR。
- CLI/batch 工具支持本服务自己的 OCR cache。
- Pipeline 只消费 OCR artifact，并合并 OCR diagnostics。
- 记录项目收敛审计，不移动、不删除旧目录。

不包含：

- 不修改 `services/backend-python/tools/psd_like_layer_decomposition_experiment.py`。
- 不从 `services/psdlike-python` import 旧 `backend` 或 `services/backend-python`。
- 不做 106B/106C 模型反哺。
- 不接 Figma plugin。
- 不删除旧目录。

## Implemented Design

OCR 入口放在 service/API/tool 边界，核心 pipeline 不做网络调用：

```text
API / tools
-> uploaded OCR artifact OR OCR cache/provider
-> input.ocr_blocks.v1.json
-> run_pipeline(ocr_path=...)
```

Provider contract:

```text
OCR_PROVIDER=baidu_ppocrv5 | none
```

Default product behavior:

```text
OCR_PROVIDER=baidu_ppocrv5
PSDLIKE_ALLOW_MISSING_OCR=false
```

这意味着 PNG-only 产品路径在缺 token 或 OCR provider 失败时应该失败，而不是静默产出无文字 draft。开发时可以显式开启 `PSDLIKE_ALLOW_MISSING_OCR=true` 或上传 OCR artifact。

## Artifact Contract

任务目录：

```text
services/psdlike-python/storage/tasks/{taskId}/
  input.png
  input.ocr_blocks.v1.json
  input.model_evidence.v1.json
  compile/
    layer_stack.v1.json
    draft_runtime.dsl.v1_0.json
    preview.html
    diagnostics.md
    ownership_report.v1.json
    assets/*.png
```

OCR cache：

```text
services/psdlike-python/storage/ocr_cache/{sha256}.ocr_blocks.v1.json
```

手动上传的 OCR artifact 只保存到 task 目录，不写全局 cache。

## Diagnostics

新增/透传字段：

```text
ocrProvider
ocrPresent
ocrTextCount
ocrCacheHit
ocrElapsedSeconds
ocrError
ocrArtifactPath
ocrRemoteJobId
ocrSubmitSeconds
ocrPollSeconds
ocrPollCount
ocrFilteredLowConfidenceCount
ocrWarningCount
```

## Validation Plan

Static and unit:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
python -m py_compile $(find app tools -name '*.py' | sort)
uv run pytest -q
```

Cached OCR regression:

```bash
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --out /Users/luhui/Downloads/psdlike_1065_cached_ocr_eval_10 \
  --limit 10 \
  --require-ocr
```

Real OCR smoke:

```bash
OCR_PROVIDER=baidu_ppocrv5 uv run python tools/run_one.py \
  --image <real_png> \
  --out /Users/luhui/Downloads/psdlike_1065_real_ocr_smoke \
  --run-ocr \
  --require-ocr
```

API smoke:

```bash
OCR_PROVIDER=baidu_ppocrv5 uv run uvicorn app.main:app --host 127.0.0.1 --port 8010
curl -F "image=@<png>" http://127.0.0.1:8010/api/draft-preview
```

## Current Validation Evidence

Implementation evidence:

```text
python -m py_compile: passed
uv run pytest -q: 15 passed
git diff --check: passed
```

Cached OCR 10-case regression:

```text
output: /Users/luhui/Downloads/psdlike_1065_cached_ocr_eval_10
cases: 10
failed cases: 0
DSL valid: 10/10
ocrPresent: 10/10
ocrProvider: cache
ocrCacheHit: 10/10
missingAssetCount sum: 0
shapeAssetCount sum: 0
fullPageVisibleRaster sum: 0
```

Real OCR smoke:

```text
output: /Users/luhui/Downloads/psdlike_1065_real_ocr_smoke
provider: baidu_ppocrv5
ocrCacheHit: false
ocrElapsedSeconds: 2.06
ocrTextCount: 29
textLayerCount: 27
missingAssetCount: 0
```

Cache validation:

```text
output: /Users/luhui/Downloads/psdlike_1065_real_ocr_smoke_cache
provider: baidu_ppocrv5
ocrCacheHit: true
ocrElapsedSeconds: 0.002
ocrTextCount: 29
textLayerCount: 27
missingAssetCount: 0
```

API smoke:

```text
POST /api/draft-preview with PNG only: completed
taskId: 2c3c4e6d782e488d9ee534bda755a49e
ocrPresent: true
ocrProvider: baidu_ppocrv5
ocrCacheHit: true
ocrTextCount: 29
textLayerCount: 27
missingAssetCount: 0
GET /api/draft-preview/{taskId}/dsl: pure Draft Runtime DSL JSON
```
