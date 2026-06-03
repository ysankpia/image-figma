# 129 Pencil Backend Local Acceptance

Status: completed

## Summary

Add a one-command local acceptance runner for `services/pencil-python-backend`.

Current validation requires separate terminal steps: preflight, start server, smoke, upload. The acceptance runner should start a temporary server, run both HTTP validations, and shut the server down reliably.

## Scope

- Add `scripts/local_acceptance.py`.
- Add `make acceptance`.
- Reuse `scripts/preflight.py`, `scripts/http_smoke.py`, and `scripts/upload_project.py`.
- Use default `boundarySource=psdlike`.
- Update README and deploy runbook.

## Non-Goals

- No remote SSH deployment.
- No nginx/systemd mutation.
- No visual algorithm changes.

## Validation

Run:

```bash
cd services/pencil-python-backend
make acceptance IMAGE=/absolute/path/to/sample.png OUT=/Volumes/WorkDrive/pencil-exports/local-acceptance-20260604
```

Acceptance:

- Preflight passes.
- Temporary server starts.
- `http_smoke.py` completes with `boundarySource=psdlike`.
- `upload_project.py` completes with `boundarySource=psdlike`.
- Server shuts down.

## Completion Evidence

Static check:

```text
make check
15 passed, 1 warning
```

Acceptance:

```text
make acceptance IMAGE=/Volumes/WorkDrive/pencil-exports/shengxian-batch001-alpha-fallback-fix-20260604/debug/pages/page_0015/source.png OUT=/Volumes/WorkDrive/pencil-exports/local-acceptance-20260604 PROJECT_NAME="Local Acceptance Smoke"
```

Result:

```text
preflight=ok
server=ready
http_smoke:
  queued taskId=pencil_20260603214104_16e53a917a boundarySource=psdlike
  status=completed boundarySource=psdlike
  clean-editable refs=2 badRefs=0 missingRefs=0
  visual-fidelity refs=3 badRefs=0 missingRefs=0
  visual-ocr refs=3 badRefs=0 missingRefs=0
  ok
upload_project:
  queued taskId=pencil_20260603214105_0a88d05abc boundarySource=psdlike inputCount=1
  completed taskId=pencil_20260603214105_0a88d05abc boundarySource=psdlike pageCount=1 modes=clean-editable,visual-fidelity,visual-ocr
  clean-editable refs=2 badRefs=0 missingRefs=0
  visual-fidelity refs=3 badRefs=0 missingRefs=0
  visual-ocr refs=3 badRefs=0 missingRefs=0
  ok
local_acceptance=ok
```
