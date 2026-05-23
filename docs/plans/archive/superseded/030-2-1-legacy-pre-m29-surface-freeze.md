# M30.2.1 Legacy Pre-M29 Surface Freeze

- 状态：superseded-by-m30.2.2
- 创建日期：2026-05-20
- 负责人：Codex

## Goal

M30.2.1 froze the old pre-M29 upload and diagnostic API surface so it no longer shaped the default product runtime.

The target product path was:

```text
Figma plugin
-> POST /api/upload-m30-preview
-> OCR + M29 + M30
-> GET /api/tasks/{taskId}/dsl
-> Renderer
```

## Result

This stage introduced an opt-in legacy runtime boundary and created the archive inventory for the physical removal stage.

M30.2.2 has since removed that opt-in recovery path from active source. The environment flag and legacy routes described by the original M30.2.1 plan are no longer current runtime behavior.

## Historical Acceptance

- Default `/api/upload` returned 404.
- Default legacy task debug endpoints returned 404.
- `/api/upload-m30-preview` still completed and returned M30 DSL.
- `/api/tasks/{taskId}/m30-materialization` still returned report and stage timings.
- M1-M28 plans were no longer in `docs/plans/active/`.

## Superseded By

See:

- [030-2-2-remove-frozen-pre-m29-legacy-backend-chain.md](030-2-2-remove-frozen-pre-m29-legacy-backend-chain.md)
- [../../completed/030-2-2-remove-frozen-pre-m29-legacy-backend-chain.md](../../completed/030-2-2-remove-frozen-pre-m29-legacy-backend-chain.md)
- [../../../decisions/0048-remove-frozen-pre-m29-legacy-backend-chain.md](../../../decisions/0048-remove-frozen-pre-m29-legacy-backend-chain.md)
