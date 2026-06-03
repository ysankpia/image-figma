# 115 Pencil Go Backend Formalization

## Summary

把已验证的 M29 -> Pencil `.pen` Python 原型正规化为独立 Go 服务 `services/pencil-go`。新服务内置复制后的 Go M29 evidence pipeline，支持单图和多图项目导出，并输出三种交付模式的 project ZIP。

## Scope

- 新增独立 Go module `services/pencil-go`。
- 不改 Draft runtime、Figma plugin、renderer、psdlike-python。
- Python exporter 保留为 prototype/reference，不作为部署依赖。
- 不使用 case id、文件名、品牌、文案、固定坐标、固定 bbox、固定屏幕尺寸规则。

## Contract

CLI:

```bash
cd services/pencil-go
go run ./cmd/pencilexport \
  --input ./screens \
  --out ./out/project-a \
  --project-name "Project A" \
  --mode all \
  --columns auto \
  --include-debug
```

HTTP:

```text
POST /api/pencil/projects
GET  /api/pencil/projects/{taskId}
GET  /api/pencil/projects/{taskId}/manifest
GET  /api/pencil/projects/{taskId}/download.zip
```

Output:

```text
project.zip
  manifest.json
  clean-editable/design.pen
  clean-editable/assets/visible/page_0001/*.png
  visual-fidelity/design.pen
  visual-fidelity/assets/visible/page_0001/*.png
  visual-ocr/design.pen
  visual-ocr/assets/visible/page_0001/*.png
  debug/pages/page_0001/m29_physical_evidence.v1.json
  debug/pages/page_0001/crops/*
  debug/pages/page_0001/masks/*
  debug/report.md
```

Modes:

```text
clean-editable: crop dedupe + text knockout + visible OCR TextLayer
visual-fidelity: crop-only visual handoff, no visible OCR TextLayer, no knockout
visual-ocr: visual-fidelity bitmap layers + visible OCR TextLayer, no knockout
```

## Current Evidence

Implemented:

```text
services/pencil-go/cmd/pencilexport
services/pencil-go/cmd/pencilserver
services/pencil-go/internal/m29
services/pencil-go/internal/pencil
services/pencil-go/internal/project
services/pencil-go/internal/server
services/pencil-go/internal/storage
```

Validation:

```bash
cd services/pencil-go
go test ./...
```

Single-image CLI smoke:

```bash
go run ./cmd/pencilexport \
  --input "/Users/luhui/Downloads/测试/525测试/ChatGPT Image 2026年5月23日 17_48_23.png" \
  --out /tmp/pencil_go_single \
  --project-name "Pencil Go Single" \
  --mode all \
  --columns auto \
  --include-debug=false \
  --ocr-provider none
```

Observed:

```text
pageCount = 1
modes = clean-editable, visual-fidelity, visual-ocr
zipPath = /tmp/pencil_go_single/project.zip
forbidden refs = false for all modes
asset URLs start with ./assets/visible/
```

Multi-image CLI smoke:

```bash
go run ./cmd/pencilexport \
  --input "/Users/luhui/Downloads/测试/525测试/ChatGPT Image 2026年5月23日 17_37_14.png" \
  --input "/Users/luhui/Downloads/测试/525测试/ChatGPT Image 2026年5月23日 17_48_23.png" \
  --input "/Users/luhui/Downloads/测试/525测试/ChatGPT Image 2026年5月23日 17_39_56.png" \
  --out /tmp/pencil_go_multi \
  --project-name "Pencil Go Multi" \
  --mode all \
  --columns auto \
  --include-debug=false \
  --ocr-provider none
```

Observed:

```text
pageCount = 3
each mode design.pen has 3 frames
node ids are globally unique
asset paths are page-namespaced
project.zip contains all three mode .pen files
```

HTTP smoke:

```bash
PENCIL_SERVER_ADDR=127.0.0.1:18100 \
PENCIL_SERVER_STORAGE_ROOT=/tmp/pencil_go_server_storage \
OCR_PROVIDER=none \
go run ./cmd/pencilserver
```

Observed:

```text
GET /api/health: ok
POST /api/pencil/projects with 1 PNG: completed, pageCount=1, download.zip available
POST /api/pencil/projects with 3 PNGs: completed, pageCount=3, download.zip available
```

## Remaining Work

- Run with real OCR provider to validate visible OCR text counts and color behavior in Go service.
- Export representative `.pen` files through Pencil CLI for visual screenshots.
- Add deployment runbook/systemd/nginx details before production deployment.
