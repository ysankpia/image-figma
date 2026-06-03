# Pencil Python Backend 部署 Runbook

这个服务是当前 Pencil `.pen` / `project.zip` 交付入口。它不替代 Go Draft runtime，也不需要 Figma 插件改动。

HTTP 调用方合同见 [../reference/pencil-python-backend-api.md](../reference/pencil-python-backend-api.md)。

生产默认链路：

```text
HTTP upload
-> boundarySource=psdlike
-> services/psdlike-python
-> Pencil Python exporter
-> clean-editable / visual-fidelity / visual-ocr
-> project.zip
```

`m29` 和 `hybrid` 仍可显式指定，但默认入口必须保持 `psdlike`，否则前端不传 `boundarySource` 时会回到碎资产链路。

## 资源判断

常驻进程是 FastAPI/uvicorn，不常驻加载大模型。导出任务会按项目启动 PSD-like Python 子进程，并用 Pillow/numpy 处理图片和 ZIP。内存峰值主要取决于图片尺寸、项目页数、OCR provider、并发 worker。

建议：

```text
个人自用：2 GB RAM 起，PENCIL_BACKEND_MAX_WORKERS=1
更稳部署：4 GB RAM，仍建议先保持单 worker
低内存机器：降低 PENCIL_BACKEND_MAX_FILES 和 PENCIL_BACKEND_MAX_UPLOAD_BYTES
```

## 服务器目录

推荐布局：

```text
/opt/pencil-python-backend/              repo checkout
/data/pencil-python-backend/             task storage
/etc/pencil-python-backend/              env file
```

## 安装

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin pencil
sudo mkdir -p /opt/pencil-python-backend /data/pencil-python-backend /etc/pencil-python-backend
sudo chown -R pencil:pencil /opt/pencil-python-backend /data/pencil-python-backend
```

把代码放到服务器有两种方式。

方式 A：服务器直接 checkout 完整仓库：

```text
/opt/pencil-python-backend
```

方式 B：本机生成最小部署源码包，再上传服务器：

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/pencil-python-backend
make bundle BUNDLE_OUT=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle
make verify-bundle BUNDLE_OUT=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle
```

`make verify-bundle` 会重新构建 bundle，在临时目录解包，检查源码树不含 runtime artifact，安装两个 Python
服务依赖，编译 `m29extract`，并运行 Pencil backend preflight。它通过后再上传。

如果要在上传前验证解包后的 HTTP 导出链路，传入一张样图：

```bash
make verify-bundle \
  BUNDLE_OUT=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle \
  IMAGE=/absolute/path/to/sample.png
```

这会在临时解包目录里启动服务、上传样图、下载 ZIP，并检查三种模式 `.pen` 的可见 asset refs。

记录本机 bundle hash：

```bash
cat /Volumes/WorkDrive/pencil-exports/pencil-backend-bundle/release-summary.md
shasum -a 256 /Volumes/WorkDrive/pencil-exports/pencil-backend-bundle/pencil-python-backend-deploy.tar.gz
```

上传：

```bash
scp /Volumes/WorkDrive/pencil-exports/pencil-backend-bundle/pencil-python-backend-deploy.tar.gz \
  root@SERVER:/tmp/
```

上传后在服务器核对 hash：

```bash
cd /tmp
sha256sum pencil-python-backend-deploy.tar.gz
```

输出必须和本机 `release-summary.md` / `bundle-manifest.json` 里的 `archiveSha256` 一致。

解包：

```bash
sudo tar -xzf /tmp/pencil-python-backend-deploy.tar.gz -C /opt
sudo rsync -a --delete /opt/pencil-python-backend-deploy/ /opt/pencil-python-backend/
sudo chown -R pencil:pencil /opt/pencil-python-backend
```

这个 bundle 只包含当前 Pencil 交付链路需要的 git-tracked 源码：

```text
services/pencil-python-backend
services/psdlike-python
services/backend-go/cmd/m29extract
services/backend-go/internal/m29
docs/reference/pencil-python-backend-api.md
docs/reference/env-vars.md
docs/runbooks/pencil-python-backend-deploy.md
```

它不会包含 `.venv`、storage、cache、debug 输出、实验产物或本机忽略的
`services/backend-go/bin/m29extract`。因此服务器上仍需要安装依赖并编译 `m29extract`。

安装运行时工具，并确认 `pencil` 用户能找到 `uv`：

```bash
sudo -u pencil sh -lc 'command -v uv || curl -LsSf https://astral.sh/uv/install.sh | sh'
sudo -u pencil sh -lc 'command -v uv && uv --version'
```

systemd 模板会设置：

```text
PATH=/home/pencil/.local/bin:/usr/local/bin:/usr/bin:/bin
```

所以 `uv` 可以装在 `pencil` 用户的 home 目录，也可以装在 `/usr/local/bin`。

安装 Python 依赖：

```bash
cd /opt/pencil-python-backend/services/pencil-python-backend
uv sync

cd /opt/pencil-python-backend/services/psdlike-python
uv sync
```

构建 `m29extract`，保留给显式 `boundarySource=m29` 和 `hybrid`：

```bash
cd /opt/pencil-python-backend/services/backend-go
mkdir -p bin
go build -o bin/m29extract ./cmd/m29extract
```

## 环境变量

复制模板：

```bash
sudo cp /opt/pencil-python-backend/services/pencil-python-backend/deploy/pencil-python-backend.env.example \
  /etc/pencil-python-backend/pencil-python-backend.env
sudo chmod 600 /etc/pencil-python-backend/pencil-python-backend.env
```

必须确认：

```text
PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=psdlike
PENCIL_BACKEND_STORAGE_ROOT=/data/pencil-python-backend
PENCIL_BACKEND_PSDLIKE_ROOT=/opt/pencil-python-backend/services/psdlike-python
PENCIL_BACKEND_M29EXTRACT=/opt/pencil-python-backend/services/backend-go/bin/m29extract
PENCIL_BACKEND_MAX_WORKERS=1
```

真实 OCR 时配置：

```text
OCR_PROVIDER=baidu_ppocrv5
BAIDU_PADDLE_OCR_TOKEN=...
```

本地自用或无 OCR smoke 可用：

```text
OCR_PROVIDER=none
```

## systemd

复制 service：

```bash
sudo cp /opt/pencil-python-backend/services/pencil-python-backend/deploy/pencil-python-backend.service \
  /etc/systemd/system/pencil-python-backend.service
sudo systemctl daemon-reload
sudo systemctl enable --now pencil-python-backend
```

检查：

```bash
cd /opt/pencil-python-backend/services/pencil-python-backend
sudo -u pencil env $(grep -v '^#' /etc/pencil-python-backend/pencil-python-backend.env | xargs) \
  uv run python scripts/preflight.py --require-m29
systemctl status pencil-python-backend --no-pager
curl -sS http://127.0.0.1:8100/api/health
curl -sS http://127.0.0.1:8100/api/ready
```

## Smoke

仓库内提供 HTTP smoke 脚本。它会上传一张图片，不传 `boundarySource`，然后验证任务、manifest、ZIP 和 `.pen` asset refs。

```bash
cd /opt/pencil-python-backend/services/pencil-python-backend
make smoke IMAGE=/absolute/path/to/sample.png OUT=/tmp/pencil-http-smoke
```

必须看到：

```text
ready=ready
boundarySource=psdlike
status=completed
badRefs=0
missingRefs=0
```

For actual non-frontend upload/download automation, use:

```bash
make upload-http \
  IMAGE=/absolute/path/to/screens \
  OUT=/tmp/pencil-http-project \
  PROJECT_NAME="HTTP Project" \
  MODE=all
```

## nginx

如果要对外暴露，建议 nginx 只反代内网 uvicorn：

```nginx
location /api/pencil/ {
    proxy_pass http://127.0.0.1:8100/api/pencil/;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
    client_max_body_size 20m;
}
```

不要让 uvicorn 直接监听公网。上传大小要和 `PENCIL_BACKEND_MAX_UPLOAD_BYTES` 对齐。

## 运维检查

任务状态和产物在：

```text
$PENCIL_BACKEND_STORAGE_ROOT/tasks/{taskId}/
```

常见失败归属：

```text
PSD-like runner not found      -> PENCIL_BACKEND_PSDLIKE_ROOT 配错
m29extract executable missing  -> 只影响 m29/hybrid；构建 services/backend-go/bin/m29extract
OCR token missing              -> OCR_PROVIDER=baidu_ppocrv5 但 token 为空
task is not completed          -> 前端过早下载 ZIP，应先轮询 completed
badRefs / missingRefs          -> backend export contract bug，不能在 Figma 插件里掩盖
```

升级后固定验证：

```bash
cd /opt/pencil-python-backend/services/pencil-python-backend
make check
make preflight-strict
make acceptance IMAGE=/absolute/path/to/sample.png OUT=/tmp/pencil-local-acceptance
```

`make acceptance` 会临时启动本地服务，依次执行 preflight、HTTP smoke 和 upload/download 验证，然后关闭服务。服务已经由 systemd 启动时，继续用 `make smoke` 验证运行中的实例。
