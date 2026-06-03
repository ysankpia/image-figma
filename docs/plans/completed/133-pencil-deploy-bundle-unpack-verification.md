# 133 Pencil Deploy Bundle Unpack Verification

Status: completed

## Summary

Add a deploy bundle verification step that proves the generated Pencil Python Backend source bundle can be unpacked and used like a server deployment input.

The previous bundle step proved the archive was clean and contained the right source slice. This stage adds a repeatable verification command that extracts the bundle to a temporary directory, validates the tree, installs Python dependencies, builds `m29extract`, and runs Pencil backend preflight against the unpacked tree.

## Scope

- Add `scripts/verify_deploy_bundle.py`.
- Add `make verify-bundle`.
- Add tests for deploy bundle tree hygiene verification.
- Document `make verify-bundle` in README and deploy runbook.

## Non-Goals

- No visual algorithm changes.
- No runtime export behavior changes.
- No Figma plugin changes.
- No remote server mutation.

## Validation

Run:

```bash
cd services/pencil-python-backend
make check
make verify-bundle BUNDLE_OUT=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-verify-20260604
```

Acceptance:

- `make check` passes.
- `make verify-bundle` rebuilds the bundle.
- Verification extracts the archive to a temporary directory.
- Verification rejects runtime artifacts in the extracted tree.
- Verification runs `uv sync` for Pencil backend and PSD-like service.
- Verification builds `services/backend-go/bin/m29extract`.
- Verification runs `scripts/preflight.py --require-m29` against the unpacked tree with explicit `PENCIL_BACKEND_*` paths.

## Completion Evidence

Static checks:

```text
make check
18 passed, 1 warning
```

Deploy bundle unpack verification:

```text
make verify-bundle BUNDLE_OUT=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-verify-20260604
staging=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-verify-20260604/pencil-python-backend-deploy
archive=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-verify-20260604/pencil-python-backend-deploy.tar.gz bytes=254442
manifest=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-verify-20260604/bundle-manifest.json
files=102
tree=ok
m29extractBuild=ok
preflight=ok
deployBundleVerification=ok
```
