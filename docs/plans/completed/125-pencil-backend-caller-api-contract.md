# 125 Pencil Backend Caller API Contract

Status: completed

## Summary

Document the caller-facing contract for `services/pencil-python-backend` so frontend or CLI consumers use the verified product path correctly.

The service now has deployment templates, preflight, and HTTP smoke. The remaining integration risk is caller misuse: downloading before completion, forcing `m29`, missing multipart field names, or treating task-level failure as an HTTP failure.

## Scope

- Add a dedicated API contract document for Pencil Python Backend.
- Clarify default `boundarySource=psdlike`.
- Clarify async task lifecycle and polling.
- Clarify manifest/download readiness.
- Clarify errors and caller behavior.
- Link the contract from docs index, env docs, runbook, and service README.

## Non-Goals

- No API shape changes.
- No error-envelope normalization in this stage.
- No frontend implementation.
- No visual algorithm changes.

## Validation

Run:

```bash
cd services/pencil-python-backend
uv run python -m py_compile $(find app tests scripts -name '*.py' | sort)
uv run pytest -q
uv run python scripts/preflight.py
```

Also verify the contract matches the route implementation in `app/routes/projects.py`.

## Completion Evidence

Added caller contract:

```text
docs/reference/pencil-python-backend-api.md
```

Linked from:

```text
docs/index.md
docs/reference/env-vars.md
docs/runbooks/pencil-python-backend-deploy.md
services/pencil-python-backend/README.md
```

Validation:

```text
uv run python -m py_compile $(find app tests scripts -name '*.py' | sort)
uv run pytest -q
15 passed, 1 warning
uv run python scripts/preflight.py
preflight=ok
```

Route/contract alignment checked against:

```text
services/pencil-python-backend/app/routes/projects.py
```
