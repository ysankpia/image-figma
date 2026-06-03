# Pencil Python Backend

独立的 `M29 -> Pencil .pen` 项目导出服务。这个服务用于快速交付：

```text
1..N images
-> local m29extract executable
-> Python Pencil exporter
-> clean-editable / visual-fidelity / visual-ocr
-> project.zip
```

`services/pencil-go` 不作为当前产品交付路径。这里复用已验证的 Python exporter 行为，`m29extract` 只作为本地可执行文件提供物理证据。

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
pencil-export \
  --input /path/to/image-or-dir \
  --out /Volumes/WorkDrive/pencil-exports/project-a \
  --project-name "Project A" \
  --mode all \
  --columns auto \
  --include-debug
```

输出：

```text
project.zip
manifest.json
clean-editable/design.pen
visual-fidelity/design.pen
visual-ocr/design.pen
debug/report.md
```

三种模式的产品语义：

```text
clean-editable   清理可编辑版：启用 OCR TextLayer、文字 knockout、组件级 crop 去重。
visual-fidelity  纯视觉保真版：不显示 OCR TextLayer，不 knockout，文字保留在 bitmap crop 里。
visual-ocr       视觉友好 OCR 版：启用 OCR TextLayer，普通文字 bitmap crop 不再可见，并对重叠底图 crop 做文字 knockout，避免叠字。
```

## HTTP Server

```bash
cd services/pencil-python-backend
PENCIL_BACKEND_M29EXTRACT=../backend-go/bin/m29extract \
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
```

## Environment

```text
PENCIL_BACKEND_ADDR=127.0.0.1:8100
PENCIL_BACKEND_STORAGE_ROOT=./storage
PENCIL_BACKEND_M29EXTRACT=../backend-go/bin/m29extract
PENCIL_BACKEND_MAX_FILES=20
PENCIL_BACKEND_MAX_UPLOAD_BYTES=10485760
PENCIL_BACKEND_MAX_WORKERS=1
OCR_PROVIDER=baidu_ppocrv5 | none | fake
BAIDU_PADDLE_OCR_TOKEN=...
```

## Deploy Notes

这个服务不在本机跑大模型。常驻进程主要是 FastAPI/uvicorn；单次导出会启动本地 `m29extract` 并用 Pillow/numpy 处理图片 crop 和文字 knockout。内存峰值跟图片尺寸、单项目图片数、并发任务数相关。

推荐首发部署：

```text
Python 3.12 + uv
local m29extract executable
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
