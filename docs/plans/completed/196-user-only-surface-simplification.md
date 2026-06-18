# Plan 196: User-Only Surface Simplification

## Status
Completed on 2026-06-18.

## Objective
Simplify Slice Studio back to a user-only product surface. Keep the user workflow:

```text
home
-> login/register
-> owned projects
-> review workbench
-> save slices
-> AI-assisted boxes
-> assets.zip / project.zip / design.pen export
```

Remove the non-user side chain: admin console, billing page, payment provider code, quota consumption, entitlements, usage events, payment orders, XPay webhook handling, and manual operations repair.

## Scope

Keep:

- `/`, `/login`, `/register`, `/projects`, `/projects/:projectId/review`, `/settings`
- email/password sessions
- project ownership through `projects.user_id`
- user-scoped local storage keys and signed downloads
- projects, pages, slices, AI boxes, asset export, Pencil project export

Remove from the current mainline:

- `/admin`, `/billing`
- `/api/me`, `/api/admin/*`, `/api/billing/*`
- XPay provider integration
- billing, entitlement, quota, usage, order, and admin repair code
- active schema dependence on `plans`, `entitlements`, `usage_events`, `payment_orders`, and `payment_events`

Do not delete local project data, original images, saved slices, users, sessions, or storage files.

## Implementation Notes

- Do not revert mixed commits; remove the feature surfaces directly.
- Keep upload file-size and batch-size limits as technical safety limits.
- AI and export must no longer decrement counters or block on entitlement status.
- New databases should not create billing/payment/entitlement tables.
- Existing local databases should drop obsolete billing/payment/entitlement tables through a compatibility migration.
- The settings page remains, but becomes a minimal account page with email, nickname, status, and sign out.

## Validation

Required:

```bash
pnpm run check
pnpm run build
bun run smoke
bun run smoke:db-migrations
git diff --check
git status --short --branch
```

Targeted static check:

```bash
rg -n "api/admin|api/billing|/admin|/billing|xpay|XPay|consumeAiCall|consumeExport" app components server shared scripts tests package.json .env.example
rg -n "payment_orders|payment_events|entitlements|usage_events" app components server shared scripts tests package.json .env.example
```

Expected result:

- first command: no matches;
- second command: matches only in `server/db-migrations.ts` and `scripts/db-migration-smoke.ts`, because the compatibility migration must name the obsolete tables it drops.

Runtime expectations:

- `/projects` still requires login.
- Login/register still work.
- Project creation, upload, slice save, AI boxes, asset export, full project export, and page export still work.
- `/billing`, `/admin`, `/api/billing/plans`, and `/api/admin/overview` no longer exist.
