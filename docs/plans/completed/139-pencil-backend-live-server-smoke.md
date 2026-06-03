# 139 Pencil Backend Live Server Smoke

Status: completed

## Summary

Add a dedicated live-server smoke command for Pencil Python Backend deployments.

`make acceptance` starts a temporary local server. `make verify-bundle IMAGE=...` unpacks and starts a temporary bundle server. Those are good pre-upload gates, but they do not prove the already-running systemd instance is usable after deployment. This stage adds `scripts/server_smoke.py` and `make server-smoke` for the live instance.

## Scope

- Add `scripts/server_smoke.py`.
- Add `make server-smoke`.
- Keep `make smoke` as the lower-level HTTP export smoke.
- Update README, API smoke contract, deploy runbook, and handoff runbook.
- Include the new script in deploy bundle selection coverage.

## Non-Goals

- No export behavior changes.
- No visual algorithm changes.
- No systemd unit behavior changes.
- No remote deployment execution.

## Validation

Run:

```bash
cd services/pencil-python-backend
make check
make acceptance \
  IMAGE=/Volumes/WorkDrive/pencil-exports/shengxian-batch001-alpha-fallback-fix-20260604/debug/pages/page_0015/source.png \
  OUT=/Volumes/WorkDrive/pencil-exports/server-smoke-local-acceptance-20260604
make server-smoke \
  IMAGE=/Volumes/WorkDrive/pencil-exports/shengxian-batch001-alpha-fallback-fix-20260604/debug/pages/page_0015/source.png \
  OUT=/Volumes/WorkDrive/pencil-exports/server-smoke-live-20260604
make verify-bundle \
  BUNDLE_OUT=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-final-20260604 \
  IMAGE=/Volumes/WorkDrive/pencil-exports/shengxian-batch001-alpha-fallback-fix-20260604/debug/pages/page_0015/source.png
```

Acceptance:

- `make check` passes.
- `make acceptance` passes with `local_acceptance=ok`.
- `make server-smoke` prints `health=ok`, `ready=ready`, and `serverSmoke=ok`.
- `make verify-bundle IMAGE=...` still passes with all mode refs `badRefs=0` and `missingRefs=0`.

## Completion Evidence

Validated on 2026-06-04:

```text
make check
25 passed, 2 warnings
```

Local acceptance:

```text
make acceptance IMAGE=/Volumes/WorkDrive/pencil-exports/shengxian-batch001-alpha-fallback-fix-20260604/debug/pages/page_0015/source.png OUT=/Volumes/WorkDrive/pencil-exports/server-smoke-local-acceptance-20260604
preflight=ok
health=ok
ready=ready
clean-editable refs=2 badRefs=0 missingRefs=0
visual-fidelity refs=3 badRefs=0 missingRefs=0
visual-ocr refs=3 badRefs=0 missingRefs=0
local_acceptance=ok
```

Live server smoke against a running local uvicorn instance:

```text
make server-smoke IMAGE=/Volumes/WorkDrive/pencil-exports/shengxian-batch001-alpha-fallback-fix-20260604/debug/pages/page_0015/source.png OUT=/Volumes/WorkDrive/pencil-exports/server-smoke-live-20260604
health=ok
ready=ready
readyCheck.defaultBoundarySource=ok psdlike
readyCheck.ocr=ok none
clean-editable refs=2 badRefs=0 missingRefs=0
visual-fidelity refs=3 badRefs=0 missingRefs=0
visual-ocr refs=3 badRefs=0 missingRefs=0
serverSmoke=ok
```

Deploy bundle verification before commit:

```text
archiveSha256=ok f61829ea483f8b80c6e937bfc1bfb4fd7b5b3f56bfb8ac02baacc34e364cdd89
m29extractBuild=ok
preflight=ok
server=ready
health=ok
ready=ready
clean-editable refs=2 badRefs=0 missingRefs=0
visual-fidelity refs=3 badRefs=0 missingRefs=0
visual-ocr refs=3 badRefs=0 missingRefs=0
httpAcceptance=ok
deployBundleVerification=ok
```
