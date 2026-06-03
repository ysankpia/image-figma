# 136 Pencil Handoff In Deploy Bundle

Status: completed

## Summary

Include the Pencil Python Backend handoff runbook inside the deploy source bundle.

The handoff document was added after deploy bundle packaging, so the bundle whitelist needed one final update. Without it, the uploaded server package would contain the service and deploy runbook but miss the concise operator handoff.

## Scope

- Add `docs/runbooks/pencil-python-backend-handoff.md` to the deploy bundle file whitelist.
- Update the bundle selection regression test.
- Rebuild and verify the final bundle with HTTP acceptance.
- Update the handoff's verified bundle evidence path.

## Non-Goals

- No runtime export changes.
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

Completion evidence:

```text
make check
19 passed, 1 warning

archive=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-final-20260604/pencil-python-backend-deploy.tar.gz bytes=257987
files=105
bundle manifest contains docs/runbooks/pencil-python-backend-handoff.md = True
tree=ok
m29extractBuild=ok
preflight=ok
server=ready
queued taskId=pencil_20260603221609_48d6e3e091 boundarySource=psdlike
status=completed boundarySource=psdlike
manifest boundarySource=psdlike pageCount=1 modes=clean-editable,visual-fidelity,visual-ocr
clean-editable refs=2 badRefs=0 missingRefs=0
visual-fidelity refs=3 badRefs=0 missingRefs=0
visual-ocr refs=3 badRefs=0 missingRefs=0
httpAcceptance=ok
deployBundleVerification=ok
```
