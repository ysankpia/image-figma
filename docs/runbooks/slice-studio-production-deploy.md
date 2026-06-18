# Slice Studio Production Deploy Runbook

Last verified: 2026-06-19

## Current Production Surface

```text
Domain: https://image.figma.245162.xyz
Server: racknerd / 192.236.242.152
App path: /opt/slice-studio/app
Storage path: /opt/slice-studio/storage
Env file: /opt/slice-studio/env/slice-studio.env
API service: slice-studio-api
Web service: slice-studio-web
Reverse proxy: existing Docker Caddy container sub2api-caddy
Caddyfile: /opt/caddy/Caddyfile
```

The production route is native runtime plus `systemd`, behind the existing Caddy reverse proxy. It is not a Docker app deployment and not an nginx/certbot deployment.

## Runtime Shape

```text
Browser
-> Caddy HTTPS :443
-> 127.0.0.1:3010 Next standalone server
-> same-origin /api rewrite
-> 127.0.0.1:4110 Elysia API
-> /opt/slice-studio/storage/app.sqlite
-> /opt/slice-studio/storage/users/{userId}/projects/{projectId}/...
```

System services:

```bash
systemctl status slice-studio-api slice-studio-web --no-pager
journalctl -u slice-studio-api -n 100 --no-pager
journalctl -u slice-studio-web -n 100 --no-pager
systemctl restart slice-studio-api slice-studio-web
```

Caddy commands:

```bash
docker exec sub2api-caddy caddy validate --config /etc/caddy/Caddyfile
docker exec sub2api-caddy caddy reload --config /etc/caddy/Caddyfile
docker logs --tail 120 sub2api-caddy
```

## Database Fact

Current Slice Studio code uses SQLite through `bun:sqlite`:

```text
server/db.ts -> bun:sqlite
server/config.ts -> SLICE_STUDIO_STORAGE_ROOT/app.sqlite
```

There is no Postgres adapter, no `DATABASE_URL` path, and no ORM abstraction in the current mainline. Therefore the existing PGSQL service on the server cannot be used by configuration alone.

Do not create a new PGSQL database for the current code. If Postgres becomes required, that is a code migration task:

```text
add DB abstraction or Postgres adapter
port migrations to Postgres SQL
update query call sites
select the existing PGSQL database/user to reuse
migrate SQLite data if needed
run real smoke before cutover
```

## Environment

Production env lives at:

```text
/opt/slice-studio/env/slice-studio.env
```

It is permissioned `600` and must not be printed into logs or committed. Current important runtime settings:

```text
NODE_ENV=production
SLICE_STUDIO_LOAD_LOCAL_ENV=false
SLICE_STUDIO_API_HOST=127.0.0.1
SLICE_STUDIO_API_PORT=4110
SLICE_STUDIO_API_URL=http://127.0.0.1:4110
SLICE_STUDIO_PUBLIC_API_URL=https://image.figma.245162.xyz
SLICE_STUDIO_ALLOWED_ORIGIN=https://image.figma.245162.xyz,http://127.0.0.1:3010
SLICE_STUDIO_STORAGE_ROOT=/opt/slice-studio/storage
SLICE_STUDIO_AUTH_SECURE_COOKIES=true
```

Text-style measurement currently runs in fallback mode on the server because the production host does not have the PSD-like Python service/`uv` path installed. The site remains usable; editable text export uses the TypeScript fallback estimator.

## Manual Deploy Procedure

The first production deploy used archive upload because the private GitHub repo could not be cloned from the server without credentials.

From the local repository root:

```bash
pnpm run check
pnpm run build
git diff --check
git archive --format=tar HEAD | ssh racknerd 'set -euo pipefail; rm -rf /opt/slice-studio/app.new; mkdir -p /opt/slice-studio/app.new; tar -xf - -C /opt/slice-studio/app.new; rm -rf /opt/slice-studio/app.old; if [ -d /opt/slice-studio/app ]; then mv /opt/slice-studio/app /opt/slice-studio/app.old; fi; mv /opt/slice-studio/app.new /opt/slice-studio/app'
ssh racknerd 'cd /opt/slice-studio/app && corepack enable && corepack prepare pnpm@10.33.2 --activate && pnpm install --frozen-lockfile && pnpm run build && systemctl restart slice-studio-api slice-studio-web'
```

The production services are already installed; do not recreate them unless the service contract changes.

## Validation

Inside-out validation commands:

```bash
ssh racknerd 'systemctl is-active slice-studio-api slice-studio-web'
ssh racknerd 'curl -fsS http://127.0.0.1:4110/api/health'
ssh racknerd 'curl -fsSI http://127.0.0.1:3010 | sed -n "1,12p"'
curl -fsSI http://image.figma.245162.xyz
curl -fsSI https://image.figma.245162.xyz
curl -fsS https://image.figma.245162.xyz/api/health
```

The 2026-06-19 production smoke passed:

```text
API service active
Web service active
127.0.0.1:4110 /api/health -> {"ok":true}
127.0.0.1:3010 -> HTTP 200
http://image.figma.245162.xyz -> HTTP 308 to HTTPS
https://image.figma.245162.xyz -> HTTP 200
https://image.figma.245162.xyz/api/health -> {"ok":true}
```

Real app smoke also passed on the server:

```text
sign in as bootstrap owner
create temporary project
upload PNG page
save one slice
export assets.zip
export project.zip / design.pen
delete temporary project
```

## HTTPS

Caddy owns ports 80 and 443 through Docker container `sub2api-caddy` using `network_mode: host`.

The Caddy site block is:

```caddy
image.figma.245162.xyz {
    encode zstd gzip
    reverse_proxy 127.0.0.1:3010
}
```

Caddy obtained a Let's Encrypt certificate for `image.figma.245162.xyz` on 2026-06-18 UTC. Certificate renewal is handled by Caddy using its persistent Docker volumes:

```text
sub2api_caddy_data
sub2api_caddy_config
```

Do not install nginx or certbot for this site unless the reverse-proxy strategy is intentionally changed.

## Current CD Status

There is no active GitHub Actions CD workflow in this repository.

The server deploy directory is not a git clone:

```text
/opt/slice-studio/app has no .git directory
```

Therefore a `git pull && systemctl restart` workflow will not work today. The next CD step must choose one of these explicit routes:

1. Archive/rsync upload from GitHub Actions to `/opt/slice-studio/app`, then install/build/restart.
2. Configure a server deploy key or token, turn `/opt/slice-studio/app` into a private repo checkout, then use a `git pull` workflow.

Do not copy a personal SSH private key into GitHub Secrets without explicit operator approval. Prefer a dedicated deploy key.

## Production Gaps

These are not blockers for the current deployed user-side product, but they are real remaining operations work:

```text
GitHub Actions CD workflow
server backup/restore for /opt/slice-studio/storage and /opt/slice-studio/env
PSD-like text-style service installation if production-quality text measurement is required
Postgres migration only if SQLite is no longer acceptable
object storage backend only if local disk storage is no longer acceptable
monitoring/alerting beyond systemd and Caddy logs
```

Billing, admin, payment, entitlement, usage counters, quota gates, and XPay are not current runtime work after plan 196.
