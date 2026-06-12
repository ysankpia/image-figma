# Pencil Python Backend Handoff

> Historical/reference handoff. 当前默认产品主线是仓库根目录的 Slice Studio。只有明确维护旧 `archive/legacy-code/services/pencil-python-backend` 时才使用本文。

Last full HTTP acceptance evidence baseline:

```text
5a59327 test: add assisted slice workspace acceptance
```

This handoff records the current operational path for Pencil `.pen` /
`project.zip` / `selected-assets.zip` delivery. It intentionally does not cover
visual algorithm experiments, YOLO as final owner, `services/pencil-go`, Go
Draft, Codia, or Figma plugin changes.

## Current Product Path

```text
images
-> services/pencil-python-backend
-> candidates.v1.json
-> HTML Canvas assisted slice workspace
-> user-confirmed manual_slices.v1.json
-> export-preview
-> project.zip + selected-assets.zip
```

Default behavior:

```text
PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=psdlike
includeDebug=true
PENCIL_BACKEND_MAX_WORKERS=1
manual_slices.v1.json is final delivery truth
review_state.v1.json is workbench state only
```

PSD-like, M29, OCR, foreground audit, and model evidence only create candidates
or debug data. Use `boundarySource=m29` or `hybrid` only for explicit diagnostics
or fallback work.

## Local Workspace Self-Use

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

Start the service:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/pencil-python-backend
PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=psdlike \
OCR_PROVIDER=none \
uv run uvicorn app.main:app --host 127.0.0.1 --port 8100
```

Open:

```text
http://127.0.0.1:8100/api/pencil/slice-projects/workspace
```

Expected workflow:

```text
create project
-> open review
-> select candidates, box-select candidates, or draw slices
-> manage selected assets across pages
-> save manual_slices.v1.json
-> generate export preview
-> export
-> download project.zip and selected-assets.zip
```

Daily-use notes:

```text
manual_slices.v1.json stays the only delivery truth source
review_state.v1.json stores rejected candidates, filters, and last active page
selected assets panel is project-wide by default and can jump across pages
batch rename changes displayName; stable exported filenames stay page-namespaced
after export, refreshing review still shows project.zip and selected-assets.zip links
cloned projects keep review/manual state but remove old export output
```

## Assisted Slice Acceptance

Use this before trusting a branch for current product self-use:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/pencil-python-backend
make slice-acceptance \
  IMAGE=/absolute/path/to/image-or-dir \
  OUT=/Volumes/WorkDrive/pencil-exports/slice-acceptance
```

Passing output must include:

```text
sliceWorkspaceAcceptance=ok
projectCreated=true
candidateCount>0
manualSliceSaved=true
reviewStateSaved=true
exportPreviewGenerated=true
projectZipExists=true
selectedAssetsZipExists=true
selectedAssetCount == selectedPngCount
badRefs=0
missingRefs=0
```

The script writes:

```text
acceptance_report.md
acceptance_report.json
```

## Automatic Pencil Export

The older automatic export path is still available for batch diagnostics. It is
not the current product judge.

Export a project with the local CLI:

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

## Automatic HTTP Acceptance

Use this only when validating the older automatic `/api/pencil/projects` path:

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
sample upload completes through the automatic project route
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
make server-smoke IMAGE=/absolute/path/to/sample.png OUT=/tmp/pencil-server-smoke
```

Passing output must include:

```text
health=ok
ready=ready
boundarySource=psdlike
status=completed
badRefs=0
missingRefs=0
serverSmoke=ok
```

Current assisted slice acceptance should still be run separately against a live
instance with `make slice-acceptance BASE_URL=... IMAGE=... OUT=...` when
validating the workspace path.

## Do Not Change During Deployment

Do not change these unless deliberately starting a new algorithm stage:

```text
Figma plugin
services/pencil-go
Go Draft runtime
Codia routes
YOLO/M29 visual heuristics as final ownership judges
clean-editable OCR ownership rules outside candidate generation
asset clustering rules outside candidate generation
```
