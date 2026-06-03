# 116 Pencil Python Backend Productization

## Summary

把已验证的 Python `M29 -> Pencil .pen` exporter 产品化为独立 Python 后端。服务接收单图或多图，调用本地 `m29extract` 可执行文件生成 M29 evidence，再输出包含三种交付模式的 Pencil project ZIP。

## Contract

```text
1..N images
-> local m29extract executable
-> Python single-page Pencil exporter
-> project-level .pen merge
-> project.zip
```

HTTP:

```text
GET  /api/health
POST /api/pencil/projects
GET  /api/pencil/projects/{taskId}
GET  /api/pencil/projects/{taskId}/manifest
GET  /api/pencil/projects/{taskId}/download.zip
```

CLI:

```bash
cd services/pencil-python-backend
uv run python -m app.cli.export_project --input ./screens --out ./out --mode all
```

Output:

```text
  project.zip
    manifest.json
    clean-editable/design.pen
    clean-editable/assets/visible/page_0001/clean-editable__page_0001__*.png
    visual-fidelity/design.pen
    visual-fidelity/assets/visible/page_0001/visual-fidelity__page_0001__*.png
    visual-ocr/design.pen
    visual-ocr/assets/visible/page_0001/visual-ocr__page_0001__*.png
    debug/pages/page_0001/*
    debug/report.md
```

Project-level visible asset filenames are mode- and page-namespaced, not only directories.
This keeps every image basename unique across a multi-page, multi-mode project package, which is required
for importers that fall back from relative paths to filename lookup.

Mode semantics:

```text
clean-editable:
  cleaned editable handoff; OCR TextLayer owns normal text pixels, overlapping crops are text-knockout cleaned, component crop dedupe is enabled.

visual-fidelity:
  crop-only visual fallback; no visible OCR TextLayer and no text knockout, so original text stays in bitmap crops.

visual-ocr:
  visual-friendly OCR handoff; OCR TextLayer owns normal text pixels, ordinary text_region bitmap crops are not visible, and overlapping bitmap crops are text-knockout cleaned to prevent doubled text.
```

## Current Status

Implemented:

```text
services/pencil-python-backend
```

Key boundaries:

```text
services/pencil-go is superseded as a product route.
Go m29extract is used only as a local evidence executable.
Python exporter remains the delivery truth source for Pencil visual output.
```

Validation to run:

```bash
cd services/pencil-python-backend
uv run python -m py_compile $(find app tests -name '*.py' | sort)
uv run pytest -q
```
