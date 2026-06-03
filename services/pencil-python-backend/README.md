# Pencil Python Backend

独立的 `M29 -> Pencil .pen` 项目导出服务。这个服务用于快速交付：

```text
1..N images
-> boundary source: m29extract, PSD-like, or PSD-like + M29 hybrid fallback
-> Python Pencil exporter
-> clean-editable / visual-fidelity / visual-ocr
-> project.zip
```

`services/pencil-go` 不作为当前产品交付路径。这里复用已验证的 Python exporter 行为。默认 `boundarySource=psdlike`，走 PSD-like 粗粒度对象边界以降低资产碎片；`boundarySource=m29` 仍可显式使用旧链路；`boundarySource=hybrid` 以 PSD-like 为主，只用 M29 补 PSD-like 低覆盖的局部对象，不会把原始 M29 primitive 全量倒进输出。

## Local CLI

先准备 `m29extract`：

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/backend-go
mkdir -p bin
go build -o bin/m29extract ./cmd/m29extract
```

安装本地命令：

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/pencil-python-backend
make install-local
command -v pencil-export
pencil-export --help
```

运行导出：

```bash
PENCIL_BACKEND_M29EXTRACT=../backend-go/bin/m29extract \
PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=psdlike \
pencil-export \
  --input /path/to/image-or-dir \
  --out /Volumes/WorkDrive/pencil-exports/project-a \
  --project-name "Project A" \
  --mode all \
  --columns auto \
  --boundary-source psdlike \
  --include-debug
```

如果已经先用 `services/psdlike-python/tools/batch_eval.py` 跑过一批图，可以复用该批 artifacts，避免 Pencil 包装阶段再次 OCR / decomposition：

```bash
pencil-export \
  --manifest /Volumes/WorkDrive/pencil-exports/psdlike-batch/input_manifest.v1.json \
  --out /Volumes/WorkDrive/pencil-exports/project-a \
  --project-name "Project A" \
  --mode all \
  --columns auto \
  --boundary-source psdlike \
  --psdlike-artifacts-root /Volumes/WorkDrive/pencil-exports/psdlike-batch \
  --include-debug
```

`--psdlike-artifacts-root` 是本地 CLI/离线审计入口。HTTP 上传接口不接收这个服务器本地路径参数。

输出：

```text
project.zip
manifest.json
clean-editable/design.pen
clean-editable/assets/visible/page_0001/clean-editable__page_0001__*.png
visual-fidelity/design.pen
visual-fidelity/assets/visible/page_0001/visual-fidelity__page_0001__*.png
visual-ocr/design.pen
visual-ocr/assets/visible/page_0001/visual-ocr__page_0001__*.png
debug/report.md
```

多页、多模式项目的可见图片资产 basename 必须全局唯一。生成端会把单页资产名改写成
`visual-ocr__page_0001__psd_raster_0011.png` 这种形式，避免后续 Pencil/Figma 导入器按文件名兜底匹配时跨页、跨 mode 撞名。

项目级 `design.pen` 写出前会做合同校验：可见 image fill 必须是包内 `./assets/visible/...` 相对路径并带
`enabled: true`；禁止引用 `source.png`、raw crops、masks、debug 目录、绝对路径或 `../`；editable shape
stroke 使用 Pencil 原生对象格式 `{"align":"inside","thickness":1,"fill":"#..."}`，不再写旧的 `strokeWidth`。

三种模式的产品语义：

```text
clean-editable   清理可编辑版：普通 UI OCR 生成 TextLayer 并 knockout；媒体/促销/视觉文字保留为 raster，组件级 crop 去重。
visual-fidelity  纯视觉保真版：不显示 OCR TextLayer，不 knockout，文字保留在 bitmap crop 里。
visual-ocr       视觉友好 OCR 版：普通 UI OCR 生成 TextLayer 并 knockout；媒体/促销/视觉文字保留为 raster，避免海报/商品图文字被擦。
```

## HTTP Server

```bash
cd services/pencil-python-backend
PENCIL_BACKEND_M29EXTRACT=../backend-go/bin/m29extract \
PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=psdlike \
OCR_PROVIDER=baidu_ppocrv5 \
uv run uvicorn app.main:app --host 127.0.0.1 --port 8100
```

Endpoints：

```text
GET  /api/health
POST /api/pencil/projects
GET  /api/pencil/projects/{taskId}
GET  /api/pencil/projects/{taskId}/manifest
GET  /api/pencil/projects/{taskId}/download.zip
```

`POST /api/pencil/projects` 使用 `multipart/form-data`：

```text
files[]       1..20 images
projectName   optional
mode          all | clean-editable | visual-fidelity | visual-ocr
columns       auto | integer
includeDebug  true | false
ocrProvider   optional
boundarySource m29 | psdlike | hybrid
```

`boundarySource` 可选值：

```text
m29      旧链路，高召回但 asset 可能偏碎。
psdlike  PSD-like 粗粒度边界，asset 更少，适合干净交付。
hybrid   PSD-like 主边界 + M29 低覆盖局部对象兜底，适合 PSD-like 漏小对象时使用。
```

如果请求不传 `boundarySource`，服务使用 `PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE`；默认值是 `psdlike`。

HTTP smoke：

```bash
uv run python scripts/preflight.py
uv run python scripts/http_smoke.py \
  --base-url http://127.0.0.1:8100 \
  --image /absolute/path/to/sample.png \
  --out /Volumes/WorkDrive/pencil-exports/http-smoke
```

## Environment

```text
PENCIL_BACKEND_ADDR=127.0.0.1:8100
PENCIL_BACKEND_STORAGE_ROOT=./storage
PENCIL_BACKEND_M29EXTRACT=../backend-go/bin/m29extract
PENCIL_BACKEND_PSDLIKE_ROOT=../psdlike-python
PENCIL_BACKEND_PSDLIKE_TILE_SIZE=8
PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=psdlike
PENCIL_BACKEND_MAX_FILES=20
PENCIL_BACKEND_MAX_UPLOAD_BYTES=10485760
PENCIL_BACKEND_MAX_WORKERS=1
OCR_PROVIDER=baidu_ppocrv5 | none | fake
BAIDU_PADDLE_OCR_TOKEN=...
```

## Deploy Notes

这个服务不在本机跑大模型。常驻进程主要是 FastAPI/uvicorn；单次导出会启动本地 `m29extract` 或 PSD-like Python 子进程，并用 Pillow/numpy 处理图片 crop 和文字 knockout。内存峰值跟图片尺寸、单项目图片数、并发任务数相关。

推荐首发部署：

```text
Python 3.12 + uv
local m29extract executable
local PSD-like Python service directory when using boundarySource=psdlike or hybrid
uvicorn bound to 127.0.0.1:8100
systemd service
nginx reverse proxy if exposing HTTP
PENCIL_BACKEND_MAX_WORKERS=1
```

资源建议：

```text
1 GB RAM: 能试跑小图，但不建议稳定使用。
2 GB RAM: 个人自用、单 worker、10 MB upload limit 的合理起点。
4 GB RAM: 更稳，适合一次项目多图或偶发并发。
```

服务器部署细节见 [../../docs/runbooks/pencil-python-backend-deploy.md](../../docs/runbooks/pencil-python-backend-deploy.md)。模板文件在 [deploy/](deploy/)。
