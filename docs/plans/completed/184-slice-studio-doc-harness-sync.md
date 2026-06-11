# 184 Slice Studio Documentation Harness Sync

Status: completed

## Summary

Bring repository documentation back in line with the current working product: `apps/slice-studio`.

The goal is not to delete old code. The goal is to make the repo readable again: current work should start from Slice Studio, while older Pencil Python, Pencil Asset, Pencil Handoff Studio, Draft, Renderer, plugin, M29, PSD-like, and Codia material is classified as reference, fallback, deferred, or legacy research.

## Input normalization

- User-provided input: request to make the current project deliverable, update stale docs, and archive/classify old code.
- Truth sources: current code in `apps/slice-studio`, Slice Studio completed plans `159`-`183`, current repository state, and user confirmation that the current local result is usable.
- Evidence sources: root `README.md`, `AGENTS.md`, `docs/index.md`, product docs, current code map, legacy inventory, env vars, validation docs, and old plans.
- Missing inputs: none blocking documentation sync.
- Final output: updated harness docs and active progress ledger.

## Scope

- Add current direction contract and `PROGRESS.md`.
- Update root and docs navigation to identify Slice Studio as the default product mainline.
- Update product, architecture, validation, env, code-map, and legacy inventory docs.
- Classify old code in docs; do not move or delete source directories.
- Preserve pre-existing uncommitted Slice Studio AI prompt code changes.

## Non-goals

- No source-code cleanup.
- No physical archive/move of legacy directories.
- No deployment work.
- No AI prompt behavior changes.
- No old service removal.

## Affected layers

- Source input: repository docs and current code facts.
- Intermediate data: product direction, code map, legacy inventory, env var reference.
- Decision point: default runtime authority for future work.
- Output surface: docs and progress ledger.
- Validation surface: doc sanity, Slice Studio checks, git status.

## Validation

- `git diff --check`
- targeted stale-mainline grep
- `bun run check` from `apps/slice-studio` when current code state allows
- `git status --short --branch`

## Completed

- Added `PROGRESS.md` and `docs/product/direction-contract.md`.
- Re-routed README, AGENTS, docs index, roadmap, product docs, architecture docs, validation, env vars, runbooks, code map, and legacy inventory to Slice Studio as the default product mainline.
- Kept old Pencil Python, Go Draft, Renderer, plugin, PSD-like, Codia, and M29 research code in place but classified them as reference/fallback/deferred/legacy.
- Integrated the Slice Studio AI prompt strategy reference into docs navigation.
- Preserved pre-existing Slice Studio AI prompt code/test changes as unrelated dirty work.

## Validation Results

- `git diff --check` passed.
- Targeted stale-mainline grep passed for current docs; remaining matches are negations, historical/reference runbooks, archived plans, or old completed-plan evidence.
- `pnpm --dir apps/slice-studio run check` passed: typecheck passed, Vitest 8 files / 52 tests passed.
- `pnpm --dir apps/slice-studio run build` passed: Next.js production build completed successfully.

## Progress checkpoints

- `PROGRESS.md` updated at start and closeout.
- Plan moved to `docs/plans/completed/` after validation.

## Learning backflow

Document the key lesson in repo docs: old research code can remain valuable without retaining product authority.
