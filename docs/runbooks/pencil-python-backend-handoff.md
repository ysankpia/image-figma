# Pencil Python Backend Handoff

Last full HTTP acceptance evidence baseline:

```text
409ad9c docs: add pencil backend handoff
```

This handoff records the current operational path for Pencil `.pen` / `project.zip` delivery. It intentionally does not cover visual algorithm experiments, YOLO integration, `services/pencil-go`, or Figma plugin changes.

## Current Product Path

```text
images
-> services/psdlike-python boundary source by default
-> services/pencil-python-backend exporter
-> clean-editable / visual-fidelity / visual-ocr
-> project.zip
```

Default behavior:

```text
PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=psdlike
mode=all
includeDebug=true
PENCIL_BACKEND_MAX_WORKERS=1
```

Use `boundarySource=m29` or `hybrid` only for explicit diagnostics or fallback work.

## Local Self-Use

Build `m29extract`:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/backend-go
mkdir -p bin
go build -o bin/m29extract ./cmd/m29extract
```

Install the local command:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/pencil-python-backend
make install-local
```

Export a project:

```bash
pencil-export \
  --input /absolute/path/to/image-or-dir \
  --out /Volumes/WorkDrive/pencil-exports/my-project \
  --project-name "My Project" \
  --mode all \
  --columns auto \
  --include-debug
```

Expected output:

```text
/Volumes/WorkDrive/pencil-exports/my-project/project.zip
/Volumes/WorkDrive/pencil-exports/my-project/manifest.json
/Volumes/WorkDrive/pencil-exports/my-project/clean-editable/design.pen
/Volumes/WorkDrive/pencil-exports/my-project/visual-fidelity/design.pen
/Volumes/WorkDrive/pencil-exports/my-project/visual-ocr/design.pen
```

## Local HTTP Acceptance

Use this before trusting a branch for self-use:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/pencil-python-backend
make acceptance \
  IMAGE=/absolute/path/to/sample.png \
  OUT=/Volumes/WorkDrive/pencil-exports/local-acceptance
```

Passing output must include:

```text
preflight=ok
boundarySource=psdlike
clean-editable badRefs=0 missingRefs=0
visual-fidelity badRefs=0 missingRefs=0
visual-ocr badRefs=0 missingRefs=0
local_acceptance=ok
```

## Deploy Bundle

Build and verify the deploy source bundle:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/pencil-python-backend
make verify-bundle \
  BUNDLE_OUT=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle \
  IMAGE=/absolute/path/to/sample.png
```

The verified bundle to upload is:

```text
/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle/pencil-python-backend-deploy.tar.gz
```

`make verify-bundle IMAGE=...` proves:

```text
archive unpacks cleanly
runtime artifacts are absent from the archive
Pencil backend dependencies install
PSD-like dependencies install
m29extract builds from the bundled Go source
preflight passes against the unpacked tree
temporary HTTP service starts on 127.0.0.1:8110
sample upload completes
downloaded ZIP has badRefs=0 and missingRefs=0 for all modes
```

The current verified local bundle evidence is:

```text
/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-final-20260604/pencil-python-backend-deploy.tar.gz
/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-final-20260604/bundle-manifest.json
/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-final-20260604/release-summary.md
```

Before and after upload, compare the archive hash with `archiveSha256` in `release-summary.md`:

```bash
shasum -a 256 /Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-final-20260604/pencil-python-backend-deploy.tar.gz
```

## Server Deployment

Full deployment steps are in [pencil-python-backend-deploy.md](pencil-python-backend-deploy.md).

Minimum server sequence:

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin pencil
sudo mkdir -p /opt/pencil-python-backend /data/pencil-python-backend /etc/pencil-python-backend
sudo chown -R pencil:pencil /opt/pencil-python-backend /data/pencil-python-backend

sudo tar -xzf /tmp/pencil-python-backend-deploy.tar.gz -C /opt
sudo rsync -a --delete /opt/pencil-python-backend-deploy/ /opt/pencil-python-backend/
sudo chown -R pencil:pencil /opt/pencil-python-backend

sudo -u pencil sh -lc 'command -v uv || curl -LsSf https://astral.sh/uv/install.sh | sh'

cd /opt/pencil-python-backend/services/pencil-python-backend
uv sync

cd /opt/pencil-python-backend/services/psdlike-python
uv sync

cd /opt/pencil-python-backend/services/backend-go
mkdir -p bin
go build -o bin/m29extract ./cmd/m29extract
```

Then configure:

```text
/etc/pencil-python-backend/pencil-python-backend.env
```

Required production values:

```text
PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=psdlike
PENCIL_BACKEND_STORAGE_ROOT=/data/pencil-python-backend
PENCIL_BACKEND_PSDLIKE_ROOT=/opt/pencil-python-backend/services/psdlike-python
PENCIL_BACKEND_M29EXTRACT=/opt/pencil-python-backend/services/backend-go/bin/m29extract
PENCIL_BACKEND_MAX_WORKERS=1
```

For real OCR:

```text
OCR_PROVIDER=baidu_ppocrv5
BAIDU_PADDLE_OCR_TOKEN=...
```

For smoke without OCR:

```text
OCR_PROVIDER=none
```

## Server Smoke

After systemd starts:

```bash
cd /opt/pencil-python-backend/services/pencil-python-backend
make smoke IMAGE=/absolute/path/to/sample.png OUT=/tmp/pencil-http-smoke
```

Passing output must include:

```text
ready=ready
boundarySource=psdlike
status=completed
badRefs=0
missingRefs=0
```

## Do Not Change During Deployment

Do not change these unless deliberately starting a new algorithm stage:

```text
Figma plugin
services/pencil-go
YOLO/M29 visual heuristics
clean-editable OCR ownership rules
asset clustering rules
```
