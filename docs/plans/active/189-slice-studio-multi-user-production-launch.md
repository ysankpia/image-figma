# Plan 189: Slice Studio Multi-User Production Launch

## Status
Active.

## Objective
Turn Slice Studio from a local/private UI slicing tool into a formal multi-user web product that can accept real users, protect uploaded design material, meter expensive AI work, and support paid access through a replaceable payment provider.

This plan is not a warning to avoid the work. The work is in scope. The point is to make the production contract explicit so Codex can implement quickly without mixing local-tool assumptions into a public product.

## Implementation progress

2026-06-17 Stage 1 foundation is in progress:

- Landing, login/register, protected `/projects`, protected `/projects/:projectId/review`, `/settings`, `/billing`, and `/admin` surfaces now exist.
- Elysia has custom email/password session auth, bootstrap local admin, user ownership on projects, and auth guards for project APIs, source images, previews, AI boxes, assets/project downloads, and page-scoped project downloads.
- SQLite now has `users`, `sessions`, `usage_events`, `plans`, `entitlements`, `payment_orders`, and `payment_events`; existing unowned local projects are claimed by the bootstrap owner at API startup.
- Browser API calls now normally use same-origin `/api` through the Next rewrite so the session cookie remains first-party; direct `SLICE_STUDIO_API_URL` remains for scripts and server-side checks.
- AI and export routes now consume entitlement counters and write `usage_events`; `POST /api/billing/orders` creates a provider-neutral pending XPay order skeleton without granting entitlement.
- Minimal XPay / 易支付 checkout and webhook fulfillment now exists: configured XPay env vars produce a checkout URL, verified success callbacks write `payment_events`, mark the local order paid, and grant entitlement from the local plan table. Forged callbacks are recorded but do not grant entitlement.
- Remaining 189 work: payment reconciliation/refund/cancel/admin repair, richer admin operations, production DB/storage adapter, legal/help pages, backup/restore/deploy runbooks, and final real-flow validation.

## Concrete analysis

### Concrete object
The concrete object is the repository-root Slice Studio app: a Next.js + React workbench backed by an Elysia API, Bun SQLite, and local filesystem storage.

### Known facts
- Current product flow is:

  ```text
  1..N UI screenshots/design images
  -> Slice Studio project workspace
  -> saved SliceRecord boxes
  -> assets.zip
  -> project.zip / design.pen
  ```

- Current backend routes are open project APIs under `/api/projects/*`.
- Current persistence is local SQLite at `SLICE_STUDIO_STORAGE_ROOT/app.sqlite`.
- Current uploaded originals and export ZIPs are stored under `SLICE_STUDIO_STORAGE_ROOT/projects/{projectId}/...`.
- Current API has CORS origin configuration but no user session, route auth, project ownership, quota, billing entitlement, or admin boundary.
- Current AI slice boxes already use an OpenAI-compatible provider configuration family: `SLICE_STUDIO_AI_SLICE_BASE_URL`, `SLICE_STUDIO_AI_SLICE_API_KEY`, `SLICE_STUDIO_AI_SLICE_MODEL`, and `SLICE_STUDIO_AI_SLICE_WIRE_API`.
- Current product docs mark auth, billing, cloud sync, team collaboration, and formal SaaS multi-tenancy as non-goals for the local delivery phase. This plan intentionally changes the next phase.
- CodeGraph audit on 2026-06-17 confirmed the current reachable Next app routes are only:

  ```text
  /
  /projects
  /projects/:projectId/review
  ```

  `app/page.tsx` redirects `/` to `/projects`, so the current app has no public landing page.
- CodeGraph audit on 2026-06-17 confirmed the current Elysia API is an unauthenticated local API for project CRUD, page upload/replace/order/delete/source, AI boxes, slice save, slice preview, assets export, full project export, and page-scoped project export.
- CodeGraph audit on 2026-06-17 confirmed the current SQLite schema only has `projects`, `pages`, and `slices`. There are no current mainline `users`, `sessions`, `auth_accounts`, `usage_events`, `plans`, `subscriptions`, `payment_orders`, `payment_events`, `redeem_codes`, `redemptions`, admin, or audit tables.
- CodeGraph audit on 2026-06-17 confirmed `/Users/luhui/pencil.2.figma` is useful as a reference for payment, quota, and admin concepts, not as code to copy directly. Its `p2f` surface has a public product home, admin login, and admin shell with dashboard, support query, user/auth management, card inventory, and system settings. Its broader app also has user payment, subscriptions, profile, orders, payment result, admin payment dashboard, payment plans, payment orders, EasyPay provider, `payment_orders`, and `subscription_plans`.
- External payment review on 2026-06-17 found `https://x.yhhrun.cn/doc/epay_submit` is an XPay / 易支付 / 码支付 style provider. It is acceptable for the first launch as a provider adapter if Slice Studio remains the source of truth for orders, entitlements, usage, and webhook verification.

### Current missing product surfaces

The current app should be treated as missing all production SaaS pages except the core authenticated workbench candidate.

User-facing pages still missing:

- Public landing page at `/`: product positioning, target users, workflow proof, output artifacts, pricing entry, privacy/support FAQ, and CTA.
- Pricing/SaaS page: free/trial/paid plan display tied to real entitlement limits.
- Login/register pages: session creation, registration, password/provider login, logout, and auth error states.
- Authenticated app shell: navigation for projects, usage, billing, settings, help, and logout.
- Owned project list: current `/projects` behavior plus user ownership, quotas, and usage state.
- Protected Review Workbench: current `/projects/:projectId/review` behind auth and owner checks.
- Account settings page: profile, email, password or provider bindings, language, logout, data deletion/export request entry.
- Usage/credits page: current plan, remaining credits, AI/export/upload/storage usage, limits, reset/expiry time.
- Billing/orders page: payment records, order status, paid/failed/processing state, entitlement effect, support reference.
- Checkout page: creates a server-side payment order and routes to provider.
- Payment return/result page: displays order state only; it must not grant entitlement.
- Redeem-code page if XPay starts with external purchase/card-code fulfillment.
- Help/support page: upload/export usage, Pencil/Figma handoff instructions, common failures, contact path.
- Legal pages: terms, privacy policy, refund/payment policy.

Admin/operator pages still missing:

- Admin login and role boundary.
- Admin dashboard: users, projects, page uploads, AI calls, exports, payment/orders, failures.
- User management: list/search users, suspend/unsuspend, inspect usage, manually grant/revoke entitlement.
- Project management: inspect project metadata and export failures by owner.
- Plan/entitlement management: configure plans, limits, free quota, manual grants.
- Payment order management: order list, provider ids, status, amount, user, retry/repair path.
- Payment event/webhook log: raw callback payloads, signature result, idempotency and failure reason.
- Redeem-code/card inventory management for the first XPay/manual fulfillment path.
- AI provider settings: OpenRouter/OpenAI-compatible base URL, model, key presence, timeout/concurrency.
- System settings: site copy, support contact, CORS/domain, upload limits, feature flags.
- Audit log: destructive actions, admin grants, payment repairs, entitlement changes.

### Current missing backend product capabilities

Missing backend capabilities:

- Authentication and session model.
- User/project ownership on every project-scoped route.
- Authorization middleware for source image, preview, assets.zip, project.zip, and page project.zip downloads.
- Entitlement model and server-side gates.
- Usage events for AI calls, uploads, exports, storage, and manual grants.
- Plan model and limit dimensions.
- Payment order model independent of any provider.
- Verified payment webhook handler and raw event log.
- Idempotent entitlement fulfillment.
- Redeem-code fulfillment path for early external purchase/card-code operation.
- Admin role and admin-only API boundary.
- Audit events for destructive or financial operations.
- Production database migration path.
- Production storage adapter and authenticated/signed file access.
- Backup/restore and deployment operations.

The critical point is that payment is downstream of entitlement. A payment page without server-side entitlement checks does not make the app safe or monetizable.

### Unverified assumptions
- The first public launch can start as individual-user SaaS, not team workspace SaaS.
- Payment provider is not fixed. Stripe may be unsuitable because there is no overseas company structure yet.
- A provider with webhook-based payment or subscription status can be chosen later, as long as the internal entitlement contract does not depend on a specific vendor.
- The first deployed database should probably be Postgres, but the exact provider is still open.
- Object storage can be S3/R2/Supabase-compatible as long as storage ownership and signed access are explicit.

### Main contradiction
The main contradiction is not UI polish. It is that current Slice Studio is a trusted local tool, while the intended product is an untrusted multi-user service handling private uploaded screenshots and expensive AI calls.

So the first production move is not payment UI. It is identity, ownership, entitlement, storage, and deployment boundaries. Payment without those checks is just a button. It does not create a product.

### Judgment strength
Strong. The current code and docs directly show no auth, no ownership, local SQLite/filesystem storage, and open project APIs. Those facts control the launch plan.

## Final product contract

### Public product surface
The formal product needs these user-facing surfaces:

- Landing page: explains the product, target user, main workflow, output artifacts, pricing entry, and CTA.
- Login/register page: email login or provider login, with clear session state.
- App shell: authenticated project list and workbench.
- Review Workbench: current Slice Studio page, protected by project ownership.
- Billing/account page: current plan, usage, subscription/payment status, upgrade/renew/cancel entry points.
- Settings page: account email, logout, data deletion request/export request entry points.
- Legal pages: privacy policy, terms, refund/payment policy, contact/support.

### Product promise
Users can upload UI screenshots or design images, use manual or AI-assisted slicing, adjust slices, and export usable frontend assets plus a Pencil/Figma handoff package.

### Production truth source
For a public product, the truth source becomes:

```text
authenticated user
-> owned projects
-> owned pages and source images
-> owned slices
-> owned exports
-> metered AI/export/storage usage
-> entitlement-gated access
```

Saved slices remain the export truth. AI boxes, OCR, and M29 remain evidence/candidates only.

## Architecture target

### Recommended runtime shape

```text
Browser
-> HTTPS domain
-> web app
-> authenticated API
-> Postgres metadata
-> object storage for originals/exports
-> AI/OCR providers through server-side keys
-> payment provider webhooks
```

Do not expose the API as an unauthenticated public project API.

### Database target
Move from local-only SQLite assumptions to a production database contract.

Minimum tables:

```text
users
sessions or auth_accounts
projects
pages
slices
exports
usage_events
plans
subscriptions
payment_customers
payment_events
api_audit_events
```

Minimum ownership columns:

```text
projects.user_id
pages.project_id
slices.project_id
exports.project_id
usage_events.user_id
usage_events.project_id
subscriptions.user_id
```

Every project-scoped query must include owner authorization. Do not rely on unguessable `projectId`.

### Storage target
Replace repo-local storage assumptions with a storage abstraction.

Required storage classes:

```text
original images
slice previews
assets.zip
project.zip
design.pen package files
temporary AI/OCR intermediates
```

Required storage behavior:

- keys include user/project ownership, not only raw project id;
- downloads require auth or short-lived signed URLs;
- uploaded file MIME and decoded image metadata must be validated;
- no absolute local paths appear in exported package metadata;
- deleted projects remove or tombstone associated storage;
- backups cover both database metadata and object storage.

### AI provider target
Make AI provider replacement a first-class contract.

The implementation should support OpenAI-compatible providers without changing UI logic:

```text
SLICE_STUDIO_AI_SLICE_PROVIDER=openai_compatible
SLICE_STUDIO_AI_SLICE_BASE_URL=https://openrouter.ai/api/v1
SLICE_STUDIO_AI_SLICE_API_KEY=...
SLICE_STUDIO_AI_SLICE_MODEL=...
SLICE_STUDIO_AI_SLICE_WIRE_API=chat_completions | responses
```

Provider requirements:

- request/response logging must redact keys and uploaded image payloads;
- provider errors must record status, provider name, model, request id if available, and retry state;
- user-visible errors must not expose secrets;
- provider timeout/retry/concurrency settings must be configurable;
- AI calls must create `usage_events` before or after execution so cost and abuse are visible;
- entitlement checks happen before AI calls start.

OpenRouter can be one concrete provider option, but the internal contract must not be tied to OpenRouter.

## Payment and subscription contract

Payment provider is intentionally undecided.

The internal product contract should be provider-neutral:

```text
checkout session
-> provider payment/subscription event
-> verified webhook
-> payment_events row
-> subscriptions row update
-> entitlement recalculation
-> gated product action
```

Required internal states:

```text
free
trial
active
past_due
paused
canceled
expired
refunded
manual_grant
```

Required entitlement checks:

- create project;
- upload page;
- AI current page;
- AI all pages;
- export assets;
- export project;
- storage quota;
- project count;
- page count per project;
- batch concurrency.

Do not implement payment UI before entitlement guards exist. The provider can change; the entitlement contract must stay.

Payment provider selection criteria:

- can legally serve the account/company structure available at launch;
- supports webhook signature verification;
- supports one-time payment or subscription state;
- supports refunds or dispute visibility;
- provides stable payment/customer ids;
- has acceptable settlement path for the operator;
- can be tested in sandbox without real money;
- does not require client-side trust for subscription activation.

Candidate provider categories:

- domestic payment provider if the launch target and entity are domestic;
- payment aggregator that supports the operator's account structure;
- Stripe-like provider if an eligible company/account exists later;
- manual invite/manual grant for the first closed paid beta if payment integration is not legally ready.

Manual grant is acceptable for early paid pilots only if the app still uses the same entitlement table and logs who granted access.

## Implementation phases

### Phase 1: Product contract and navigation shell
Deliverables:

- Update direction contract from local-only delivery to public multi-user product target.
- Update product requirements, user flows, non-goals, acceptance criteria, env vars, and validation docs.
- Add landing page route.
- Add login/register route.
- Add authenticated app shell route group.
- Keep current workbench functionality behind the app shell.

Acceptance:

- anonymous user sees landing/login;
- authenticated user sees project list;
- unauthenticated user cannot access project list, review page, source image, previews, or exports.

### Phase 2: Auth and session boundary
Deliverables:

- Add user identity model.
- Add session management.
- Add route-level auth guard for every API route except health, landing, auth callback, and payment webhook.
- Add logout.
- Add seed/admin bootstrap path for the first operator account.
- Add CSRF/session hardening appropriate to chosen auth mechanism.

Acceptance:

- every project API rejects anonymous requests;
- login persists across refresh;
- logout invalidates access;
- API tests prove anonymous project list/detail/upload/export/delete are blocked.

### Phase 3: Project ownership and data model
Deliverables:

- Add `user_id` ownership to projects.
- Scope project list/detail/update/delete by user.
- Scope pages, source images, slices, previews, exports, and AI calls through project ownership.
- Add migration path for existing local projects into one owner account.
- Add owner-safe delete behavior.

Acceptance:

- user A cannot list, open, download, mutate, or delete user B project by guessing ids;
- migration imports existing local projects to the selected owner;
- old local projects are not orphaned.

### Phase 4: Production database
Deliverables:

- Choose Postgres-compatible production database.
- Add schema migrations instead of ad hoc SQLite table creation.
- Add typed repository functions or query layer where ownership is enforced.
- Add backup/restore runbook.
- Add deployment env vars for database URL and migration execution.

Acceptance:

- fresh deploy can migrate an empty database;
- existing local project sample can migrate;
- backup and restore are tested on a staging copy;
- test suite can run against a disposable database.

### Phase 5: Object storage and file access
Deliverables:

- Add storage adapter interface for local dev and production object storage.
- Move originals and exports behind storage adapter.
- Add signed or authenticated download path.
- Add storage key convention by user/project.
- Add cleanup job or explicit cleanup routine for deleted projects/exports.

Acceptance:

- exported packages still contain package-local paths;
- source/preview/export endpoints reject unauthorized users;
- deleting a project removes or tombstones its storage files;
- local dev can still use filesystem adapter.

### Phase 6: Entitlements, quotas, and usage metering
Deliverables:

- Define plan limits.
- Add `usage_events`.
- Add entitlement check module.
- Gate project creation, upload, AI, export, and storage.
- Add rate limits and abuse limits.
- Add account/billing page usage summary.

Initial limit dimensions:

```text
projects per user
pages per project
single upload size
batch upload size
storage bytes
AI calls per day/month
AI batch pages per run
AI batch concurrency
exports per day/month
```

Acceptance:

- over-limit actions fail with explicit user-facing errors;
- AI cost-producing routes cannot run without entitlement;
- admin/operator can inspect recent usage events.

### Phase 7: Payment provider integration
Deliverables:

- Pick provider based on available legal/account structure.
- Add checkout/start-payment endpoint.
- Add verified webhook endpoint.
- Store raw payment event metadata safely.
- Map payment events to provider-neutral subscription states.
- Add billing/account UI.
- Add cancellation/renewal/manual grant behavior.

Acceptance:

- sandbox/test payment activates entitlement only through verified webhook;
- forged webhook does not activate entitlement;
- canceled/expired/past-due state removes paid-only entitlements;
- provider outage does not delete user projects.

### Phase 8: Landing page and conversion path
Deliverables:

- Landing page with clear product positioning.
- Workflow section: upload screenshots, AI/manual slicing, export assets/Pencil package.
- Output proof section with sample assets/project package screenshots.
- Pricing entry that routes to login/register and billing.
- FAQ covering privacy, uploaded screenshots, AI usage, supported outputs, and cancellation.
- Contact/support link.

Acceptance:

- anonymous visitor can understand the product without entering the app;
- CTA routes to auth;
- pricing copy does not promise unsupported team/collaboration features;
- landing page does not expose private project APIs.

### Phase 9: Security and privacy hardening
Deliverables:

- CORS allowlist for production domains.
- Request body and upload size limits.
- MIME and decoded-image validation.
- Secret management and no `.env.local` production dependency.
- Error response sanitization.
- Security headers.
- Audit log for destructive actions.
- Data deletion/export request path.
- Privacy policy and terms.

Acceptance:

- no API key appears in browser bundle or logs;
- upload rejects non-image or oversized files;
- destructive actions are logged with user id and project id;
- delete/export data flow is documented.

### Phase 10: Deployment and operations
Deliverables:

- Production deployment target and runbook.
- Process manager/service config.
- HTTPS and reverse proxy.
- Health checks.
- App/API log locations.
- Backup schedule.
- Restore drill.
- Staging environment.
- Release checklist.
- Rollback checklist.

Acceptance:

- production health endpoint passes;
- staging and production env are separated;
- deploy can be repeated from clean checkout;
- rollback path is documented and tested once.

### Phase 11: Production validation
Deliverables:

- Full user-view smoke script.
- Browser smoke for landing -> login -> project -> upload -> AI -> export.
- API tests for auth, ownership, quota, payment webhook verification.
- Artifact validation for `assets.zip` and `project.zip/design.pen`.
- Cost-control validation for AI failure/retry/concurrency.

Acceptance:

```text
anonymous cannot access app data
registered user can complete the core workflow
wrong user cannot access project data
over-quota user is blocked before expensive work
paid/active entitlement unlocks paid actions
expired/canceled entitlement blocks paid actions
exports remain valid artifacts
backup/restore preserves project data
```

## One-day execution ordering

If the work starts tomorrow and Codex is used aggressively, execute in this order:

1. Auth/session and route protection.
2. Project ownership migration.
3. Entitlement/usage skeleton with free/manual-grant plan.
4. AI provider replacement support, including OpenRouter-compatible configuration if chosen.
5. Landing/login/account shell.
6. Production storage/database decision and minimal implementation.
7. Payment provider adapter contract, but only wire a real provider if account/legal constraints are already solved.
8. Deployment runbook and staging smoke.

This ordering lets the app become safe before it becomes monetized.

## Explicit non-goals for this plan

- Do not rework AI prompt strategy unless provider migration requires request/response format adaptation.
- Do not rewrite Review Workbench UX unless required by auth/account shell integration.
- Do not revive legacy Pencil Python, Go Draft, old Figma plugin, or Codia-like runtime as the production surface.
- Do not build team collaboration in the first production launch unless product scope changes.
- Do not hardcode a payment provider into core product logic.
- Do not make payment success a client-side state.

## Documentation updates required during implementation

- `docs/product/direction-contract.md`: update final artifact and non-goals when the first production phase lands.
- `docs/product/requirements.md`: add auth, ownership, quota, billing, deployment requirements.
- `docs/product/user-flows.md`: add anonymous, signup/login, billing, account, and data deletion flows.
- `docs/product/acceptance-criteria.md`: add production SaaS acceptance.
- `docs/product/non-goals.md`: remove production SaaS/auth/billing from local-only non-goals once implemented.
- `docs/architecture/api-contracts.md`: document auth-required routes and ownership checks.
- `docs/engineering/validation.md`: add auth/payment/ownership/deployment validation gates.
- `docs/reference/env-vars.md`: add auth, database, storage, payment, provider, and deployment env vars.
- `docs/runbooks/`: add production deploy, backup/restore, and incident runbooks.

## Validation plan

Baseline checks:

```bash
pnpm run check
pnpm run build
git diff --check
git status --short --branch
```

Production feature checks:

```text
anonymous API access blocked
login/register works
logout works
user A cannot access user B project
existing local project migration works
upload respects size/type limits
AI calls require entitlement and create usage events
exports require ownership and preserve package contract
payment webhook signature is verified
forged webhook is rejected
subscription status gates paid features
backup/restore preserves database and storage
landing -> auth -> app user journey works
```

Artifact checks:

```text
assets.zip manifest matches files
project.zip contains design.pen and package-local assets
Pencil can open design.pen
no exported package leaks local absolute paths
```

## Completion criteria

This plan is complete only when:

- public anonymous access is limited to landing/auth/legal/health routes;
- authenticated users have isolated project data;
- expensive AI/export/storage paths are entitlement-gated;
- payment/subscription or manual-grant entitlement is provider-neutral and server-verified;
- production database and storage are configured outside the repo;
- deployment, backup, restore, and rollback are documented and smoke-tested;
- a real user can complete landing -> signup/login -> project -> upload -> AI/manual slice -> export.
