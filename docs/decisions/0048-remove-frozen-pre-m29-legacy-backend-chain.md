# ADR: Remove Frozen Pre-M29 Legacy Backend Chain

- 状态：accepted
- 日期：2026-05-20

## Context

M30.2.1 froze the pre-M29 runtime surface behind an environment flag. That made the default backend match the new plugin path, but it still left the old upload chain, debug endpoints, modules, scripts, and tests inside active source.

The project is still pre-launch. There is no real-user compatibility requirement for old tasks or the old `/api/upload` path. Keeping dead runtime source now creates the wrong pressure: future work can accidentally optimize or preserve code that the product no longer consumes.

## Decision

Remove the frozen pre-M29 backend chain from active runtime source.

Delete:

```text
POST /api/upload
M8-M28 legacy debug endpoints
LEGACY_PRE_M29_UPLOAD_ENABLED
legacy pre-M29 app modules
legacy M26-M28 smoke scripts
pure legacy module tests
```

Preserve current shared infrastructure:

```text
OCR
PNG helpers
DSL factory/fallback support used by current code
Database
Storage
Assets route
Health route
M29
M30
Renderer
Figma plugin M30 preview path
```

Use git history, archived plans, old ADRs, and `docs/reference/legacy/` as the archive. Do not move dead source code into another repo directory.

## Consequences

Benefits:

- Active backend source now matches the actual product path.
- `/api/upload` can no longer be accidentally revived or tested as a current contract.
- Tests focus on OCR + M29 + M30 rather than old diagnostic chains.
- Documentation no longer presents deleted runtime behavior as available.

Costs:

- Old pre-M29 task debug APIs are no longer callable.
- Historical local tasks that depended on removed debug endpoints are not compatible with current source.
- Old implementation details must be recovered from git history if needed.

Hard boundaries:

- No database migration in this stage.
- No local `backend/storage/**` cleanup.
- No DSL schema change.
- No Renderer change.
- No M29/M30 algorithm change.
- No fallback masking, M31 web preview, or new recognition rule.
