# Image-to-Figma Roadmap

Status: active
Last updated: 2026-06-12

## Current phase

Slice Studio local delivery hardening.

The current product goal is narrow:

```text
1..N UI screenshots/design images
-> Slice Studio
-> user-confirmed or AI-assisted slice boxes
-> assets.zip
-> project.zip / design.pen
```

## Now

- Keep `apps/slice-studio` as the default product surface.
- Keep saved Slice Studio slices as the export truth source.
- Use AI only as a batch drawing helper.
- Use OCR only for editable text content.
- Use TypeScript M29 physical evidence only for tighter OCR text bbox placement.
- Keep old services and historical Draft/Renderer/plugin code as reference or deferred work.

## Next

- Finish documentation alignment after the Slice Studio product pivot.
- Keep validating AI slice prompts on real multi-page projects, with recall favored over a perfectly clean asset list.
- Add or refine Slice Studio features only through the current save/export contracts.
- Prepare deployment only after local docs, env vars, and validation are aligned.

## Later

- Deployment runbook for Slice Studio.
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

- When to deploy Slice Studio and which hosting/runtime shape to use.
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
cloud sync/auth/billing/team features
```
