# 130 Pencil Local Acceptance Port Guard

Status: completed

## Summary

Harden `scripts/local_acceptance.py` against false positives when the target port is already occupied.

The current runner starts uvicorn and then polls `/api/health`. If another process is already listening on the same port, the new uvicorn process exits but `/api/health` may still succeed against the old process. That can make acceptance validate the wrong server.

## Scope

- Make `wait_for_health` observe the spawned server process.
- Fail if the spawned process exits before health becomes ready.
- Preserve successful acceptance behavior.
- Document this guard in the completion evidence.

## Non-Goals

- No port auto-selection.
- No killing existing processes.
- No systemd or nginx changes.

## Validation

Run:

```bash
cd services/pencil-python-backend
make check
make acceptance IMAGE=/absolute/path/to/sample.png OUT=/Volumes/WorkDrive/pencil-exports/local-acceptance-port-guard-20260604
```

Acceptance:

- Existing success path remains green.
- The readiness check is tied to the spawned uvicorn process, not only any listener on the port.

## Completion Evidence

Validation:

```text
make check
15 passed, 1 warning
```

Acceptance:

```text
make acceptance IMAGE=/Volumes/WorkDrive/pencil-exports/shengxian-batch001-alpha-fallback-fix-20260604/debug/pages/page_0015/source.png OUT=/Volumes/WorkDrive/pencil-exports/local-acceptance-port-guard-20260604 PROJECT_NAME="Local Acceptance Port Guard"
```

Result:

```text
preflight=ok
server=ready
http_smoke:
  queued taskId=pencil_20260603214414_b56f12aa56 boundarySource=psdlike
  status=completed boundarySource=psdlike
  clean-editable refs=2 badRefs=0 missingRefs=0
  visual-fidelity refs=3 badRefs=0 missingRefs=0
  visual-ocr refs=3 badRefs=0 missingRefs=0
  ok
upload_project:
  queued taskId=pencil_20260603214415_cfbc029463 boundarySource=psdlike inputCount=1
  completed taskId=pencil_20260603214415_cfbc029463 boundarySource=psdlike pageCount=1 modes=clean-editable,visual-fidelity,visual-ocr
  clean-editable refs=2 badRefs=0 missingRefs=0
  visual-fidelity refs=3 badRefs=0 missingRefs=0
  visual-ocr refs=3 badRefs=0 missingRefs=0
  ok
local_acceptance=ok
```
