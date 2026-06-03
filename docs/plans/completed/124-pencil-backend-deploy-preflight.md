# 124 Pencil Backend Deploy Preflight

Status: completed

## Summary

Add a deterministic preflight command for `services/pencil-python-backend` deployments.

The service now has a deploy runbook and HTTP smoke, but server misconfiguration can still show up late during upload/export. Preflight should fail before the service is started when required paths, storage permissions, default boundary source, or Python dependencies are wrong.

## Scope

- Add `scripts/preflight.py`.
- Reuse `app.config.get_settings()` instead of duplicating env parsing.
- Check storage root creation/write/delete.
- Check PSD-like runner path when default or supported boundary source requires it.
- Check `m29extract` path and executability when `m29` or `hybrid` may be used.
- Check import availability for runtime packages.
- Document the command in README and deploy runbook.

## Non-Goals

- No network calls.
- No OCR provider token validation beyond reporting obvious empty token when OCR provider is `baidu_ppocrv5`.
- No sample image export; that remains `scripts/http_smoke.py`.
- No visual algorithm changes.

## Validation

Run:

```bash
cd services/pencil-python-backend
uv run python -m py_compile $(find app tests scripts -name '*.py' | sort)
uv run pytest -q
uv run python scripts/preflight.py
```

Acceptance:

- Preflight prints settings and ends with `preflight=ok`.
- Failure messages name the exact missing path or bad setting.

## Completion Evidence

Static checks:

```text
uv run python -m py_compile $(find app tests scripts -name '*.py' | sort)
uv run pytest -q
15 passed, 1 warning
```

Preflight:

```text
uv run python scripts/preflight.py
```

Result:

```text
addr=127.0.0.1:8100
storageRoot=/Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/pencil-python-backend/storage
defaultBoundarySource=psdlike
psdlikeRoot=/Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
m29extract=/Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/backend-go/bin/m29extract
maxFiles=20
maxUploadBytes=10485760
maxWorkers=1
ocrProvider=baidu_ppocrv5
runtimeImports=ok fastapi,uvicorn,multipart,PIL,numpy,pydantic,requests
storageRoot=ok /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/pencil-python-backend/storage
psdlikeRunner=ok /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python/tools/run_one.py
defaultBoundarySource=ok psdlike
m29extract=ok /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/backend-go/bin/m29extract
ocr=ok baidu_ppocrv5 token=set
preflight=ok
```
