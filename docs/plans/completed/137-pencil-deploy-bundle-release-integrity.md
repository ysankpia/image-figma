# 137 Pencil Deploy Bundle Release Integrity

Status: completed

## Summary

Add release integrity metadata to Pencil Python Backend deploy bundles.

The deploy bundle can already be unpacked and validated through HTTP acceptance. This stage adds archive SHA-256 metadata and a short release summary so a server operator can verify that the uploaded tarball is exactly the same bundle that passed local validation.

## Scope

- Add `archiveSha256` to `bundle-manifest.json`.
- Generate `release-summary.md` beside the archive.
- Make `verify_deploy_bundle.py` compare the archive hash against `bundle-manifest.json` when present.
- Document hash verification in README, deploy runbook, and handoff.
- Add tests for matching and mismatched archive hashes.

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

Acceptance:

- `bundle-manifest.json` contains `archiveSha256`.
- `release-summary.md` contains `archiveSha256`.
- `verify-bundle` prints `archiveSha256=ok`.
- HTTP bundle acceptance still reports `badRefs=0` and `missingRefs=0` for all modes.

## Completion Evidence

Static checks:

```text
make check
21 passed, 1 warning
```

Final bundle verification:

```text
make verify-bundle BUNDLE_OUT=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-final-20260604 IMAGE=/Volumes/WorkDrive/pencil-exports/shengxian-batch001-alpha-fallback-fix-20260604/debug/pages/page_0015/source.png
```

Result:

```text
archive=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-final-20260604/pencil-python-backend-deploy.tar.gz bytes=259129
archiveSha256=c0e1901aebc36d156b9c14a2832c25af8dcb72123c426dd27271a5d8066e9410
manifest=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-final-20260604/bundle-manifest.json
summary=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-final-20260604/release-summary.md
files=105
archiveSha256=ok c0e1901aebc36d156b9c14a2832c25af8dcb72123c426dd27271a5d8066e9410
tree=ok
m29extractBuild=ok
preflight=ok
server=ready
queued taskId=pencil_20260603222345_5d861625f0 boundarySource=psdlike
status=completed boundarySource=psdlike
manifest boundarySource=psdlike pageCount=1 modes=clean-editable,visual-fidelity,visual-ocr
clean-editable refs=2 badRefs=0 missingRefs=0
visual-fidelity refs=3 badRefs=0 missingRefs=0
visual-ocr refs=3 badRefs=0 missingRefs=0
httpAcceptance=ok
deployBundleVerification=ok
```

