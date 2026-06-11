# Slice Studio Local Docker Runbook

This runbook is for local self-use. It does not publish Slice Studio to a public server.

## Goal

Run Slice Studio from Docker with one local browser URL:

```text
http://127.0.0.1:51230/projects
```

The container runs:

```text
host URL on 127.0.0.1:51230
Next web on 3010 inside the container
Elysia API on 4110 inside the container
same-origin /api proxy from Next to the API
persistent storage mounted from apps/slice-studio/storage
```

## Start

```bash
cd apps/slice-studio
docker compose -f docker-compose.local.yml up -d --build
```

Open:

```text
http://127.0.0.1:51230/projects
```

Health check:

```bash
curl http://127.0.0.1:51230/api/health
```

Expected:

```json
{"ok":true}
```

## Stop And Restart

```bash
cd apps/slice-studio
docker compose -f docker-compose.local.yml stop
docker compose -f docker-compose.local.yml start
```

Restart after code or env changes:

```bash
cd apps/slice-studio
docker compose -f docker-compose.local.yml up -d --build
```

Logs:

```bash
cd apps/slice-studio
docker compose -f docker-compose.local.yml logs -f --tail=200
```

## Storage

Container storage is mounted to:

```text
apps/slice-studio/storage
```

Important files:

```text
apps/slice-studio/storage/app.sqlite
apps/slice-studio/storage/projects/
```

Do not delete this directory unless you intend to delete local projects.

## Environment

The compose file loads:

```text
apps/slice-studio/.env.local
```

This file is intentionally untracked. Put OCR and AI keys there.

For Docker local deployment, web requests use same-origin `/api`, so `NEXT_PUBLIC_SLICE_STUDIO_API_URL` is intentionally overridden to an empty value by `docker-compose.local.yml`. The API still listens inside the container on port `4110`.

## Backup

Create a timestamped backup:

```bash
cd apps/slice-studio
mkdir -p ../../backups/slice-studio
tar -czf "../../backups/slice-studio/slice-studio-storage-$(date +%Y%m%d-%H%M%S).tar.gz" storage
```

Restore into a stopped container:

```bash
cd apps/slice-studio
docker compose -f docker-compose.local.yml stop
rm -rf storage
tar -xzf /path/to/slice-studio-storage-YYYYMMDD-HHMMSS.tar.gz
docker compose -f docker-compose.local.yml start
```

## Server Migration Later

For a future server deployment, migrate these two things:

```text
git revision
apps/slice-studio/storage
```

A server deployment must add access control first. Do not expose this app publicly without auth, IP allowlist, VPN, Cloudflare Access, or equivalent protection.

## Validation

Minimum validation after starting Docker:

```bash
curl http://127.0.0.1:51230/api/health
curl -I http://127.0.0.1:51230/projects
```

Manual validation:

1. Open `/projects`.
2. Create a project.
3. Upload several images.
4. Draw or AI-generate slices.
5. Save, refresh, and confirm slices persist.
6. Export `assets.zip`.
7. Export `project.zip`.
