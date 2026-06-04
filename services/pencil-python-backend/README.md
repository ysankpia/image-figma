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
GET  /api/ready
POST /api/pencil/projects
GET  /api/pencil/projects/{taskId}
GET  /api/pencil/projects/{taskId}/manifest
GET  /api/pencil/projects/{taskId}/download.zip

GET  /api/pencil/slice-projects/new
POST /api/pencil/slice-projects
GET  /api/pencil/slice-projects/{projectId}
GET  /api/pencil/slice-projects/{projectId}/review
GET  /api/pencil/slice-projects/{projectId}/candidates
GET  /api/pencil/slice-projects/{projectId}/manual-slices
PUT  /api/pencil/slice-projects/{projectId}/manual-slices
POST /api/pencil/slice-projects/{projectId}/export
GET  /api/pencil/slice-projects/{projectId}/download.zip
```

调用方合同见 [../../docs/reference/pencil-python-backend-api.md](../../docs/reference/pencil-python-backend-api.md)。

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

Assisted slice review 是另一条同步产品路径，用于全自动切图不稳定的复杂页面：

```text
1..N images
-> candidates.v1.json
-> HTML Canvas Review
-> manual_slices.v1.json
-> project.zip + selected-assets.zip
```

`manual_slices.v1.json` 是最终真相源。PSD-like、M29、OCR 和 foreground audit 只生成候选框；用户在 review 页面点选、画框、拖动、缩放、删除、命名并保存后，服务才允许导出。

浏览器入口：

```text
http://127.0.0.1:8100/api/pencil/slice-projects/new
```

这个页面支持上传 1..N 张图、填写 `projectName`、选择 `boundarySource`、打开/关闭 `includeDebug`，创建成功后会自动跳转到 review workbench。

Review workbench 支持：

```text
pan / zoom / fit / 100%
候选 kind/source/confidence/opacity 过滤
双击候选加入 selected slices
手动画框
拖动和 8 点缩放
自动保存 manual_slices.v1.json
Undo / Redo
左侧 page 缩略图、candidate 数、selected 数、保存状态
右侧 selected slice 缩略图预览
Delete 删除
方向键微调
Cmd/Ctrl+S 保存
Cmd/Ctrl+Z 撤销
Cmd/Ctrl+Shift+Z 重做
Cmd/Ctrl+D 复制
Alt/Option+左右键切页
导出并下载 project.zip
```

自动保存使用短 debounce；导出前会等待 pending autosave，所以用户不需要记住先按保存。保存状态会显示为 `dirty`、`autosaving...`、`saved` 或失败信息。

CLI 或脚本也可以直接创建项目：

```bash
curl -F "files[]=@/absolute/path/to/screen.png" \
  -F "projectName=Slice Review" \
  -F "includeDebug=true" \
  http://127.0.0.1:8100/api/pencil/slice-projects
```

返回 `reviewUrl` 后在浏览器打开：

```text
http://127.0.0.1:8100/api/pencil/slice-projects/{projectId}/review
```

如果保存后的 `manual_slices.v1.json` 没有任何 selected slice，导出会返回：

```text
409 no selected slices to export
```

导出 ZIP 包含：

```text
project.zip
  manifest.json
  manual_slices.v1.json
  selected-assets.zip
  resource-kit/manifest.json
  clean-editable/design.pen
  visual-fidelity/design.pen
  visual-ocr/design.pen
  debug/pages/page_0001/...
```

HTTP smoke：

```bash
make preflight
make smoke \
  IMAGE=/absolute/path/to/sample.png \
  OUT=/Volumes/WorkDrive/pencil-exports/http-smoke
```

`/api/health` 只证明进程活着；`make smoke` 会额外检查 `/api/ready`，确认 storage、PSD-like runner、
`m29extract` 需求和 runtime imports 可用后才上传图片。

验证已经运行中的本机或服务器实例：

```bash
make server-smoke \
  BASE_URL=http://127.0.0.1:8100 \
  IMAGE=/absolute/path/to/sample.png \
  OUT=/Volumes/WorkDrive/pencil-exports/server-smoke
```

`server-smoke` 不启动服务。它只检查 live `/api/health`、`/api/ready`，再调用 HTTP 导出 smoke。

HTTP caller CLI:

```bash
make upload-http \
  IMAGE=/absolute/path/to/screens \
  OUT=/Volumes/WorkDrive/pencil-exports/http-project \
  PROJECT_NAME="HTTP Project" \
  MODE=all
```

One-command local acceptance:

```bash
make acceptance \
  IMAGE=/absolute/path/to/sample.png \
  OUT=/Volumes/WorkDrive/pencil-exports/local-acceptance
```

Assisted slice workspace acceptance:

```bash
make slice-acceptance \
  IMAGE=/absolute/path/to/image-or-dir \
  OUT=/Volumes/WorkDrive/pencil-exports/slice-acceptance
```

This verifies `/api/pencil/slice-projects`: project creation, candidates, `manual_slices.v1.json`,
`review_state.v1.json`, export preview, `project.zip`, `selected-assets.zip`, selected asset counts,
and `.pen` visible image refs. It writes `acceptance_report.md` and `acceptance_report.json` under `OUT`.

## Deploy Bundle

生成干净的服务器源码包：

```bash
cd services/pencil-python-backend
make bundle BUNDLE_OUT=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle
```

上传服务器前做解包验证：

```bash
make verify-bundle BUNDLE_OUT=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle
```

`verify-bundle` 会重新构建 bundle，在临时目录解包，确认源码树不含 runtime artifact，安装两个 Python
服务依赖，编译 `m29extract`，并运行 Pencil backend preflight。它验证的是部署包落地后的可运行性，不只是
tar 文件存在。

如果要同时验证解包后的 HTTP 导出链路，传入一张样图：

```bash
make verify-bundle \
  BUNDLE_OUT=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle \
  IMAGE=/absolute/path/to/sample.png
```

这会在解包目录里临时启动 Pencil backend，上传样图，下载 ZIP，并检查三种模式 `.pen` 的可见 asset refs。

输出：

```text
/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle/
  pencil-python-backend-deploy/
  pencil-python-backend-deploy.tar.gz
  bundle-manifest.json
  release-summary.md
```

`bundle-manifest.json` 和 `release-summary.md` 会记录 `archiveSha256`。上传服务器后用
`sha256sum pencil-python-backend-deploy.tar.gz` 或
`shasum -a 256 pencil-python-backend-deploy.tar.gz` 核对 hash，必须和 `archiveSha256` 一致。

bundle 只包含当前部署链路需要的 git-tracked 源码和文档：

```text
services/pencil-python-backend
services/psdlike-python
services/backend-go/cmd/m29extract
services/backend-go/internal/m29
docs/reference/pencil-python-backend-api.md
docs/reference/env-vars.md
docs/runbooks/pencil-python-backend-deploy.md
```

它不会打包 `.venv`、storage、cache、debug 输出、实验产物或本地忽略的
`services/backend-go/bin/m29extract`。服务器解包后仍需要运行 `uv sync` 并编译
`m29extract`。完整部署步骤见 [../../docs/runbooks/pencil-python-backend-deploy.md](../../docs/runbooks/pencil-python-backend-deploy.md)。

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
