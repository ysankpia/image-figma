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

把仓库放到：

```text
/opt/pencil-python-backend
```

安装依赖：

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
```

## Smoke

仓库内提供 HTTP smoke 脚本。它会上传一张图片，不传 `boundarySource`，然后验证任务、manifest、ZIP 和 `.pen` asset refs。

```bash
cd /opt/pencil-python-backend/services/pencil-python-backend
make smoke IMAGE=/absolute/path/to/sample.png OUT=/tmp/pencil-http-smoke
```

必须看到：

```text
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
make smoke IMAGE=/absolute/path/to/sample.png OUT=/tmp/pencil-http-smoke
```
