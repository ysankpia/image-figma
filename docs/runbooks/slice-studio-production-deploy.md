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
Text style service: slice-studio-text-style
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
-> existing jianzhi-postgres container on 127.0.0.1:15432
-> dedicated Postgres database slice_studio
-> /opt/slice-studio/storage/users/{userId}/projects/{projectId}/...

Pencil export text style:

```text
Elysia API
-> SLICE_STUDIO_TEXT_STYLE_PROVIDER=psdlike
-> 127.0.0.1:4120 slice-studio-text-style
-> services/psdlike-text-style FastAPI app
```
```

System services:

```bash
systemctl status slice-studio-text-style slice-studio-api slice-studio-web --no-pager
journalctl -u slice-studio-text-style -n 100 --no-pager
journalctl -u slice-studio-api -n 100 --no-pager
journalctl -u slice-studio-web -n 100 --no-pager
systemctl restart slice-studio-text-style slice-studio-api slice-studio-web
```

Caddy commands:

```bash
docker exec sub2api-caddy caddy validate --config /etc/caddy/Caddyfile
docker exec sub2api-caddy caddy reload --config /etc/caddy/Caddyfile
docker logs --tail 120 sub2api-caddy
```

## Database Fact

Current production uses the already-running `jianzhi-postgres` container, but not the existing `jianzhi` application database. Slice Studio owns a separate database in the same container:

```text
jianzhi-postgres: 127.0.0.1:15432
database: slice_studio
owner/user: jianzhi
```

The `jianzhi` database already contains unrelated production tables such as `public.users` and `public.schema_migrations`, so do not put Slice Studio tables there. Keep Slice Studio in `slice_studio`.

Current app env:

```text
SLICE_STUDIO_DATABASE_PROVIDER=postgres
SLICE_STUDIO_DATABASE_URL=postgres://...@127.0.0.1:15432/slice_studio
```

Local/dev still defaults to SQLite unless those variables are set.

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
SLICE_STUDIO_DATABASE_PROVIDER=postgres
SLICE_STUDIO_TEXT_STYLE_PROVIDER=psdlike
SLICE_STUDIO_TEXT_STYLE_BASE_URL=http://127.0.0.1:4120
```

The env file also contains secrets such as `SLICE_STUDIO_DATABASE_URL`, owner password, download signing secret, OCR token, and AI provider API key. Never print the raw file in logs.

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
ssh racknerd 'systemctl is-active slice-studio-text-style slice-studio-api slice-studio-web'
ssh racknerd 'curl -fsS http://127.0.0.1:4120/health'
ssh racknerd 'curl -fsS http://127.0.0.1:4110/api/health'
ssh racknerd 'curl -fsSI http://127.0.0.1:3010 | sed -n "1,12p"'
curl -fsSI http://image.figma.245162.xyz
curl -fsSI https://image.figma.245162.xyz
curl -fsS https://image.figma.245162.xyz/api/health
```

The 2026-06-19 production smoke after Postgres/PSD-like cutover passed:

```text
PSD-like text style service active
API service active
Web service active
127.0.0.1:4120 /health -> {"ok":true}
127.0.0.1:4110 /api/health -> {"ok":true}
127.0.0.1:3010 -> HTTP 200
source-origin HTTPS with --resolve -> HTTP 200 and /api/health {"ok":true}
server-local real app smoke -> passed against Postgres
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

During cutover, Cloudflare-proxied public HTTPS briefly returned TLS handshake failures while direct source-origin HTTPS with `--resolve image.figma.245162.xyz:443:192.236.242.152` worked. Caddy then completed certificate issuance/propagation and normal public HTTPS recovered. If this recurs, first compare normal DNS vs `--resolve` source-origin access; when source-origin works and Cloudflare fails, investigate Cloudflare SSL/TLS mode, edge certificate status, DNS proxy state, and whether the domain should temporarily be DNS-only while using the Caddy origin certificate.

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

GitHub Actions CD exists at:

```text
.github/workflows/deploy.yml
```

It uses the RackNerd Cloudflare Access TCP bridge, a dedicated deploy SSH key in GitHub Secrets, and `rsync` to upload the checked-out repository to `/opt/slice-studio/app.new`. The server app directory is still not a git clone:

```text
/opt/slice-studio/app has no .git directory
```

Therefore the workflow does not run `git pull` on the server. It uploads a release directory, swaps it into place, runs `pnpm install --frozen-lockfile`, builds Next standalone, ensures the PSD-like venv exists, restarts `slice-studio-text-style`, `slice-studio-api`, and `slice-studio-web`, then checks local service health.

Required repo secrets:

```text
DEPLOY_USER=root
DEPLOY_PATH=/opt/slice-studio/app
DEPLOY_SSH_KEY=<dedicated RackNerd deploy key>
SERVICE_NAME=slice-studio-api
```

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
