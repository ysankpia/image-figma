# 134 Pencil Deploy Bundle HTTP Acceptance

Status: completed

## Summary

Extend deploy bundle verification from unpack/preflight to optional real HTTP export acceptance.

The bundle already proves it can unpack, install dependencies, build `m29extract`, and pass preflight. This stage adds an `IMAGE=...` path for `make verify-bundle` so the unpacked bundle starts its own temporary Pencil backend, uploads a sample image, downloads the project ZIP, and checks `.pen` visible asset references.

## Scope

- Add `--acceptance-image` support to `scripts/verify_deploy_bundle.py`.
- Start the unpacked backend on an isolated default port.
- Fail early if the selected port is already occupied.
- Run existing `scripts/http_smoke.py` against the unpacked service.
- Update Makefile, README, and deploy runbook.
- Add a regression test for occupied port detection.

## Non-Goals

- No visual algorithm changes.
- No export contract changes.
- No Figma plugin changes.
- No remote server mutation.

## Validation

Run:

```bash
cd services/pencil-python-backend
make check
make verify-bundle \
  BUNDLE_OUT=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-http-20260604 \
  IMAGE=/Volumes/WorkDrive/pencil-exports/shengxian-batch001-alpha-fallback-fix-20260604/debug/pages/page_0015/source.png
```

Acceptance:

- `make check` passes.
- Bundle verification rebuilds and unpacks the archive.
- The unpacked service starts on its own port and is not confused with an existing server.
- HTTP smoke reports `boundarySource=psdlike`.
- The downloaded ZIP contains all requested mode `.pen` files.
- `.pen` visible image refs report `badRefs=0` and `missingRefs=0`.

## Completion Evidence

Static checks:

```text
make check
19 passed, 1 warning
```

Bundle HTTP acceptance:

```text
make verify-bundle \
  BUNDLE_OUT=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-http-20260604 \
  IMAGE=/Volumes/WorkDrive/pencil-exports/shengxian-batch001-alpha-fallback-fix-20260604/debug/pages/page_0015/source.png
```

Result:

```text
archive=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-http-20260604/pencil-python-backend-deploy.tar.gz bytes=257127
files=104
tree=ok
m29extractBuild=ok
preflight=ok
server=ready
queued taskId=pencil_20260603221045_d8a54247e7 boundarySource=psdlike
status=completed boundarySource=psdlike
manifest boundarySource=psdlike pageCount=1 modes=clean-editable,visual-fidelity,visual-ocr
clean-editable refs=2 badRefs=0 missingRefs=0
visual-fidelity refs=3 badRefs=0 missingRefs=0
visual-ocr refs=3 badRefs=0 missingRefs=0
httpAcceptance=ok
deployBundleVerification=ok
```

Port cleanup:

```text
lsof -nP -iTCP:8110 -sTCP:LISTEN || true
```

Result: no listener.
