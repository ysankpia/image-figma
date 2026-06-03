# 138 Pencil Backend Readiness Endpoint

Status: completed

## Summary

Add a deployment readiness endpoint for Pencil Python Backend and make HTTP smoke paths check it before creating export tasks.

`/api/health` only proves the FastAPI process is alive. It does not prove storage is writable, PSD-like is present, required `m29extract` is usable, runtime imports are installed, or OCR configuration is visible. This stage adds `/api/ready` for those checks and reuses the same readiness checks in `scripts/preflight.py` to prevent drift between CLI and HTTP deployment validation.

## Scope

- Add `app/readiness.py`.
- Add `GET /api/ready`.
- Keep `GET /api/health` as lightweight liveness.
- Make `scripts/preflight.py` reuse readiness checks.
- Make `scripts/http_smoke.py` and `scripts/upload_project.py` check `/api/ready`.
- Document `/api/ready` in API docs, README, deploy runbook, and handoff.
- Add API tests for ready and not-ready states.

## Non-Goals

- No export behavior changes.
- No visual algorithm changes.
- No remote deployment.

## Validation

Run:

```bash
cd services/pencil-python-backend
make check
make verify-bundle \
  BUNDLE_OUT=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-final-20260604 \
  IMAGE=/Volumes/WorkDrive/pencil-exports/shengxian-batch001-alpha-fallback-fix-20260604/debug/pages/page_0015/source.png
```

Acceptance:

- `/api/health` returns `status=ok`.
- `/api/ready` returns `ready=true` when dependencies are present.
- `/api/ready` returns HTTP `503` when PSD-like or required m29 dependencies are missing.
- `make smoke` / `http_smoke.py` prints `ready=ready` before upload.
- Bundle HTTP acceptance still passes with `badRefs=0` and `missingRefs=0`.

## Completion Evidence

Validated on 2026-06-04:

```bash
cd services/pencil-python-backend
make check
```

Result:

```text
25 passed, 2 warnings
```

Deploy bundle verification:

```bash
make verify-bundle \
  BUNDLE_OUT=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-final-20260604 \
  IMAGE=/Volumes/WorkDrive/pencil-exports/shengxian-batch001-alpha-fallback-fix-20260604/debug/pages/page_0015/source.png
```

Relevant result:

```text
archiveSha256=ok 017dffb0f29c5cdff1f28175261d5b9216103987297edf547867bd797bc5d956
m29extractBuild=ok
preflight=ok
server=ready
health=ok
ready=ready
status=completed boundarySource=psdlike
clean-editable refs=2 badRefs=0 missingRefs=0
visual-fidelity refs=3 badRefs=0 missingRefs=0
visual-ocr refs=3 badRefs=0 missingRefs=0
httpAcceptance=ok
deployBundleVerification=ok
```
