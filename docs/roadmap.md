# Image-to-Figma Roadmap

Status: active
Last updated: 2026-06-13

## Current phase

Slice Studio multi-user production launch planning.

The completed local product goal remains:

```text
1..N UI screenshots/design images
-> Slice Studio
-> user-confirmed or AI-assisted slice boxes
-> assets.zip
-> project.zip / design.pen
```

The next product goal is broader:

```text
anonymous visitor
-> landing page
-> login/register
-> authenticated Slice Studio workspace
-> owned projects/pages/slices/exports
-> entitlement-gated AI/export/storage
-> provider-neutral payment/subscription or manual grant
-> production deployment with backup/restore
```

## Now

- Keep `apps/slice-studio` as the default product surface.
- Keep saved Slice Studio slices as the export truth source.
- Use AI only as a batch drawing helper.
- Use OCR only for editable text content.
- Use TypeScript M29 physical evidence only for tighter OCR text bbox placement.
- Keep old services and historical Draft/Renderer/plugin code as reference or deferred work.
- Completed [plans/completed/190-slice-studio-prelaunch-codebase-hardening.md](plans/completed/190-slice-studio-prelaunch-codebase-hardening.md): protected current storage, clarified repo mainline, hardened OpenRouter/OpenAI-compatible provider support, and kept smoke validation repeatable.
- Execute [plans/active/189-slice-studio-multi-user-production-launch.md](plans/active/189-slice-studio-multi-user-production-launch.md) as the active production-readiness contract.
- Treat payment provider selection as undecided; implement entitlement, usage, and verified webhook boundaries before binding to any provider.
- Treat AI provider replacement as an OpenAI-compatible provider concern; OpenRouter can be evaluated without changing Slice Studio's core workflow contract.

## Next

- Update product docs and direction contract for the public multi-user phase.
- Add landing, login/register, account/billing, and authenticated app-shell surfaces.
- Add auth/session protection to all project, source, preview, AI, and export APIs.
- Add project ownership and migration of existing local projects to an owner account.
- Add production database and object storage strategy.
- Add entitlement/usage gates before expensive AI/export/storage work.
- Add provider-neutral payment/subscription integration after entitlement boundaries exist.
- Add deployment, backup/restore, and production smoke runbooks.

## Later

- Team/workspace collaboration after the individual-user product is stable.
- Optional cleaner/full-recall AI slice modes if real samples require them.
- Better repeated-AI-run behavior if duplicate management becomes the main bottleneck.
- Optional physical cleanup or repository split for old research code after a separate plan identifies safe moves.

## Milestones

- `159`: Slice Studio formalized as the local product surface.
- `176`: Slice Studio added Pencil `project.zip` export.
- `177`-`181`: OCR and TypeScript M29 physical evidence added for editable text handoff.
- `182`: AI rect slice assist added.
- `183`: AI tile merge and progress overlay added.
- `184`: repository docs realigned to Slice Studio as the current mainline.

## Open questions

- Which auth/session implementation to use for the first production cut.
- Which production database and object storage provider to use.
- Which payment provider can legally and practically support the operator account structure.
- Whether the first paid access path should be a real provider checkout or manual grant backed by the same entitlement table.
- Whether OpenRouter or another OpenAI-compatible provider should replace the current AI provider first.
- Whether old Python Pencil services should remain in this repo permanently or move to an archive branch/repository.
- Whether the next AI slice improvement should be prompt-only, consensus mode, or replaceable AI-generated slice sets.
- How much Pencil/Figma handoff validation should be automated before each release.

## Non-goals for the next phase

Do not restart these as default product work without a new active plan:

```text
official Codia JSON clone
Go Draft as default delivery route
Python upload-preview as default delivery route
semantic UI control tree as product contract
Auto Layout/component reconstruction
Figma plugin runtime revival
YOLO/M29/OCR/AI as final visible ownership judge
team collaboration
```
