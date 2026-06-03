# 128 Pencil Backend Makefile Ops

Status: completed

## Summary

Add standard `make` targets for Pencil Python Backend local operation and deployment validation.

The backend now has scripts for preflight, smoke, and HTTP upload/download, but common commands remain long and easy to mistype. The Makefile should provide short, documented entrypoints while keeping scripts as the source of behavior.

## Scope

- Add `check`, `preflight`, `preflight-strict`, `serve`, `smoke`, and `upload-http` targets.
- Keep `install-local`.
- Add configurable variables for `BASE_URL`, `IMAGE`, `OUT`, `PROJECT_NAME`, `MODE`, `PORT`, and `HOST`.
- Update README and deploy runbook to prefer Make targets.

## Non-Goals

- No backend API change.
- No deployment automation over SSH.
- No visual algorithm change.

## Validation

Run:

```bash
cd services/pencil-python-backend
make check
make preflight
make smoke IMAGE=/absolute/path/to/sample.png OUT=/Volumes/WorkDrive/pencil-exports/make-smoke-20260604
make upload-http IMAGE=/absolute/path/to/sample.png OUT=/Volumes/WorkDrive/pencil-exports/make-upload-20260604 PROJECT_NAME="Make Upload Smoke"
```

Acceptance:

- `make check` passes `py_compile` and `pytest`.
- `make preflight` ends with `preflight=ok`.
- `make smoke` validates default `boundarySource=psdlike`.
- `make upload-http` downloads ZIP and reports `badRefs=0 missingRefs=0`.

## Completion Evidence

Commands:

```text
make check
make preflight
make serve
make smoke IMAGE=/Volumes/WorkDrive/pencil-exports/shengxian-batch001-alpha-fallback-fix-20260604/debug/pages/page_0015/source.png OUT=/Volumes/WorkDrive/pencil-exports/make-smoke-20260604
make upload-http IMAGE=/Volumes/WorkDrive/pencil-exports/shengxian-batch001-alpha-fallback-fix-20260604/debug/pages/page_0015/source.png OUT=/Volumes/WorkDrive/pencil-exports/make-upload-20260604 PROJECT_NAME="Make Upload Smoke" MODE=all
```

Results:

```text
make check -> 15 passed, 1 warning
make preflight -> preflight=ok
make smoke:
  queued taskId=pencil_20260603213736_0a815dab81 boundarySource=psdlike
  status=completed boundarySource=psdlike
  clean-editable refs=2 badRefs=0 missingRefs=0
  visual-fidelity refs=3 badRefs=0 missingRefs=0
  visual-ocr refs=3 badRefs=0 missingRefs=0
  ok
make upload-http:
  queued taskId=pencil_20260603213736_b2fcd994b3 boundarySource=psdlike inputCount=1
  completed taskId=pencil_20260603213736_b2fcd994b3 boundarySource=psdlike pageCount=1 modes=clean-editable,visual-fidelity,visual-ocr
  clean-editable refs=2 badRefs=0 missingRefs=0
  visual-fidelity refs=3 badRefs=0 missingRefs=0
  visual-ocr refs=3 badRefs=0 missingRefs=0
  ok
```
