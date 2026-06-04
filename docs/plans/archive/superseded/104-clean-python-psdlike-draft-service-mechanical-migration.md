# 104 Clean Python PSD-like Draft Service Mechanical Migration

- 状态：active
- 创建日期：2026-06-02
- 负责人：Codex

## Goal

将当前 PSD-like V1 的有效行为产品化到新的 Python 服务：

```text
PNG + OCR artifact
-> PSD-like layer decomposition
-> editable Draft Runtime DSL
-> assets + diagnostics
-> FastAPI preview service
```

旧 V1 单文件是行为 oracle，不导入到新服务运行时，不修改。Go 实验暂停，不参与本阶段。

## Scope

包含：

- 新建/完善 `services/psdlike-python/`。
- 将旧 V1 的函数按职责机械迁移到 `app/core/` 模块。
- 保持 artifact 合同：
  - `layer_stack.v1.json`
  - `draft_runtime.dsl.v1_0.json`
  - `preview.html`
  - `preview_report.md`
  - `draft_preview.png`
  - `reconstructed_preview.png`
  - `overlay.png`
  - `diagnostics.md`
  - `ownership_report.v1.json`
  - `assets/*.png`
- 增加 `run_one.py`、`batch_eval.py`、`compare_oracle.py`。
- 增加 FastAPI 独立服务路径。
- 增加最小单元测试、真实 case smoke、10 张 batch validation。

不包含：

- 不修改 `services/backend-python/tools/psd_like_layer_decomposition_experiment.py`。
- 不修改 `services/psdlike-go/`。
- 不修改 `services/backend-go/`。
- 不接 YOLO、VLM、OpenCV、真实 OCR provider。
- 不做算法阈值调参、不做样本特化、不追 Auto Layout 或组件化。

## Mechanical Migration Rule

本阶段核心规则：

```text
结构可以变，行为不能变。
```

函数体迁移优先保持原样，只允许为模块化调整 import、调用路径、CLI/API 包装和 artifact 校验。任何可见输出变化都必须先通过 oracle 对比定位为迁移错误，而不是顺手改算法。

## Steps

1. 冻结旧 V1 oracle 与当前新服务边界。
2. 机械切分 V1 kernel：
   - `schema.py`
   - `ocr.py`
   - `masks.py`
   - `colors.py`
   - `components.py`
   - `evidence.py`
   - `candidates.py`
   - `surfaces.py`
   - `controls.py`
   - `media_text.py`
   - `ownership.py`
   - `assets.py`
   - `style.py`
   - `layers.py`
   - `dsl.py`
   - `previews.py`
   - `reports.py`
   - `pipeline.py`
3. 补齐服务入口：
   - `tools/run_one.py`
   - `tools/batch_eval.py`
   - `tools/compare_oracle.py`
   - FastAPI routes。
4. 增加最小测试：
   - bbox geometry
   - OCR loading
   - synthetic button pipeline
   - asset / z-order / no full-page visible raster guards。
5. 验证：
   - `py_compile`
   - `pytest`
   - `case_0003` smoke
   - `case_0004` smoke
   - 10 张 batch
   - FastAPI upload/dsl/preview smoke。

## Acceptance

- 旧 V1 oracle 文件未修改。
- Go 目录未修改。
- 新服务不再依赖 `app/core/experiment.py` 大单文件作为主路径。
- `uv run pytest -q` 通过。
- `python -m py_compile app/**/*.py tools/*.py` 通过。
- 两张真实 smoke case 不崩。
- 10 张 batch 不崩，且：
  - `missingAssetCount = 0`
  - `shapeAssetCount = 0`
  - `fullPageVisibleRaster = 0`
  - `DSL JSON exists` for every passed case。
- FastAPI `/api/draft-preview` 能上传 PNG + OCR artifact，并返回 DSL / preview。

## Validation

```bash
cd services/psdlike-python
uv run pytest -q
python -m py_compile $(find app tools -name '*.py' | sort)
uv run python tools/run_one.py --image <png> --ocr <ocr_blocks.v1.json> --out <out_dir>
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --out /Users/luhui/Downloads/psdlike_python_service_eval_10 \
  --limit 10
```

FastAPI smoke：

```bash
cd services/psdlike-python
uv run uvicorn app.main:app --host 127.0.0.1 --port 8010
curl -F "image=@<png>" -F "ocr=@<ocr_blocks.v1.json>" \
  http://127.0.0.1:8010/api/draft-preview
```

Repo checks：

```bash
git diff --check
git status --short --branch
```

## Notes

- `services/psdlike-python/app/core/experiment.py` 若存在，只能视为迁移临时快照，不能作为长期主路径。
- 如果 oracle 对比出现系统性漂移，先修迁移错误，不调算法。
- 后续 Go 迁移应以拆分后的 Python 模块合同为源，而不是旧 3000 行脚本。
