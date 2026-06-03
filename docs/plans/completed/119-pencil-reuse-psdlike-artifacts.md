# 119 Pencil Reuse PSD-like Artifacts

- 状态：active
- 创建日期：2026-06-04
- 负责人：Codex

## Summary

当前正确链路是：

```text
services/psdlike-python = 算法 / ownership 真相源
services/pencil-python-backend = .pen / project.zip 包装层
```

本计划不在 Pencil backend 内继续实现新的 YOLO/M29 ownership 规则。Pencil backend 只需要能复用已经由 PSD-like 批量跑出的 artifacts，从同一份 `layer_stack.v1.json` 生成三种 `.pen` 交付包。

## Problem

直接用 `--boundary-source psdlike` 从 Pencil backend 跑多图项目时，每页会重新调用 PSD-like `run_one.py` 和 OCR。这样会造成：

```text
1. 调试慢。
2. 同一输入在 PSD-like 审计和 Pencil 包装之间不能保证完全复用同一份中间产物。
3. 排查时难以判断问题属于 PSD-like 算法层还是 Pencil adapter/包装层。
```

## Implementation

新增 CLI-only 参数：

```bash
--psdlike-artifacts-root /path/to/psdlike-batch-output
```

当 `boundarySource=psdlike` 或 `boundarySource=hybrid` 时，Pencil backend 会：

```text
1. 读取 artifacts root 下的 input_manifest.v1.json。
2. 用 sourcePath / duplicatePaths / sha256 匹配当前输入图。
3. 复制匹配到的 case_xxx artifact 到当前 project work/page_XXXX/psdlike。
4. 调用现有 psdlike_adapter 生成 Pencil evidence。
5. 继续走原来的 clean-editable / visual-fidelity / visual-ocr packaging。
```

HTTP 上传接口不暴露这个本地路径参数，避免让远程调用者要求服务读取任意服务器目录。

## Validation

已验证的样本：

```text
/Users/luhui/Downloads/PencilBridge_Admin_UI_XcodeDark/01_UI_Pages
```

PSD-like 真实 OCR batch：

```text
/Volumes/WorkDrive/pencil-exports/psdlike-admin-xcodedark-realocr-20260604-full
```

结果：

```text
8/8 completed
failed cases = 0
DSL valid = true for all rows
每页 raster assets 约 18-34
```

单页 Pencil 包装验证：

```text
/Volumes/WorkDrive/pencil-exports/pencil-admin-xcodedark-psdlike-single-20260604
```

对比结论：

```text
Pencil clean-editable / visual-ocr 与 PSD-like draft preview 视觉接近。
visual-fidelity 会把 OCR text 也作为 bitmap crop 保留，因此 asset 数较高，这是该模式语义导致，不是 adapter 坐标错乱。
```

## Acceptance

```text
cd services/pencil-python-backend
python -m py_compile $(find app tests -name '*.py' | sort)
uv run pytest -q
```

真实复用 smoke：

```bash
cd services/pencil-python-backend
uv run python -m app.cli.export_project \
  --manifest /Volumes/WorkDrive/pencil-exports/psdlike-admin-xcodedark-realocr-20260604-full/input_manifest.v1.json \
  --out /Volumes/WorkDrive/pencil-exports/pencil-admin-xcodedark-psdlike-reuse-20260604 \
  --project-name "Admin XcodeDark PSD-like Reuse" \
  --mode all \
  --columns auto \
  --boundary-source psdlike \
  --psdlike-artifacts-root /Volumes/WorkDrive/pencil-exports/psdlike-admin-xcodedark-realocr-20260604-full \
  --include-debug
```

验收信号：

```text
project.zip exists
manifest.json records boundarySource=psdlike
manifest.json records psdlikeArtifactsRoot
clean-editable/design.pen exists
visual-fidelity/design.pen exists
visual-ocr/design.pen exists
debug/pages/page_XXXX/psdlike_debug/layer_stack.v1.json exists
```
