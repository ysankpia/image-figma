# 131 Pencil Backend Deploy Bundle

Status: completed

## Summary

Add a deterministic deploy bundle builder for the current Pencil Python Backend product path.

The current service can run locally and has preflight, smoke, HTTP upload, and local acceptance scripts. The missing operational piece is a clean source bundle for server transfer. Copying the working tree directly is unsafe because this repository contains local virtual environments, caches, storage, generated artifacts, ignored binaries, and unrelated experimental output.

## Scope

- Add a `services/pencil-python-backend/scripts/build_deploy_bundle.py` script.
- Package only git-tracked source files needed for the current deployment route:
  - `services/pencil-python-backend`
  - `services/psdlike-python`
  - minimal `services/backend-go` source needed to build `cmd/m29extract`
  - relevant Pencil backend deploy/API/env documentation
- Exclude `.venv`, caches, storage, logs, local build output, and generated experiment artifacts by construction.
- Add a `make bundle` entrypoint.
- Document bundle creation and server unpack flow.

## Non-Goals

- No visual algorithm changes.
- No Figma plugin changes.
- No YOLO/M29 heuristic work.
- No `services/pencil-go` product path changes.
- No packaging of local ignored binaries such as `services/backend-go/bin/m29extract`; the server should build `m29extract` from source or receive a binary through an explicit separate ops step.

## Acceptance

- `make bundle OUT=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-test` creates:
  - a staging directory
  - a `.tar.gz` archive
  - a `bundle-manifest.json`
- The bundle manifest records included file count, archive path, and required server build steps.
- The archive does not include `.venv`, `storage`, `__pycache__`, `.pytest_cache`, or `services/backend-go/bin`.
- The staged minimal Go backend can build `m29extract` with:

```bash
cd staging/services/backend-go
go build -o bin/m29extract ./cmd/m29extract
```

- Static checks still pass:

```bash
cd services/pencil-python-backend
make check
```

## Completion Evidence

Bundle build:

```text
make bundle BUNDLE_OUT=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-test-20260604
staging=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-test-20260604/pencil-python-backend-deploy
archive=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-test-20260604/pencil-python-backend-deploy.tar.gz bytes=251736
manifest=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-test-20260604/bundle-manifest.json
files=100
```

Bundle hygiene:

```text
tar -tzf .../pencil-python-backend-deploy.tar.gz | rg '(^|/)(\.venv|storage|__pycache__|\.pytest_cache|services/backend-go/bin)(/|$)' || true
```

Result: no matches.

Minimal Go build inside staging:

```text
cd /Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-test-20260604/pencil-python-backend-deploy/services/backend-go
go build -o bin/m29extract ./cmd/m29extract
./bin/m29extract
```

Result: binary built and printed usage.

Static checks:

```text
make check
16 passed, 1 warning
```
