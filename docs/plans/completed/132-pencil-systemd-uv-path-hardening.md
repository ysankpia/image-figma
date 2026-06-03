# 132 Pencil systemd uv PATH hardening

Status: completed

## Summary

Harden the Pencil Python Backend systemd template so deployment does not depend on `uv` being installed specifically at `/usr/local/bin/uv`.

The deploy runbook supports a system user named `pencil`. On many servers, the official `uv` installer places the binary under `/home/pencil/.local/bin/uv` when run as that user. The previous service template hardcoded `/usr/local/bin/uv`, which could make a correct source deployment fail before the app starts.

## Scope

- Add an explicit `PATH` to `pencil-python-backend.service`.
- Use `/usr/bin/env uv` for `ExecStartPre` and `ExecStart`.
- Document how to install and verify `uv` for the `pencil` user.

## Non-Goals

- No runtime behavior changes.
- No visual algorithm changes.
- No Figma plugin changes.
- No nginx automation.

## Validation

Run:

```bash
cd services/pencil-python-backend
make check
make bundle BUNDLE_OUT=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-test-20260604
```

Acceptance:

- Python checks still pass.
- Bundle contains the updated service template.
- The service template no longer hardcodes `/usr/local/bin/uv`.

## Completion Evidence

Static checks:

```text
make check
16 passed, 1 warning
```

Bundle build:

```text
make bundle BUNDLE_OUT=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-test-20260604
archive=/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle-test-20260604/pencil-python-backend-deploy.tar.gz bytes=254096
files=102
```

Staged service template:

```text
Environment=PATH=/home/pencil/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStartPre=/usr/bin/env uv run python scripts/preflight.py
ExecStart=/usr/bin/env uv run uvicorn app.main:app --host 127.0.0.1 --port 8100
```

Bundle hygiene:

```text
tar -tzf .../pencil-python-backend-deploy.tar.gz | rg '(^|/)(\.venv|storage|__pycache__|\.pytest_cache|services/backend-go/bin)(/|$)' || true
```

Result: no matches.
