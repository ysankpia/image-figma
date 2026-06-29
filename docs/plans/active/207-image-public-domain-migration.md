# Image Public Domain Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Move the public Slice Studio deployment from `image.figma.245162.xyz` to `image.245162.xyz` so Cloudflare Universal SSL covers the browser entrypoint again.

**Architecture:** Keep the origin app unchanged. Change the public hostname at the edge, on the origin proxy, and in the production docs/env contract. Keep the old hostname only as a temporary transition alias if needed, then verify the new first-level subdomain works over public HTTPS end-to-end.

**Tech Stack:** Cloudflare DNS/proxy, Caddy, Next.js standalone, Elysia API, Bun, shell/ssh.

---

### Task 1: Update repo docs and runtime references

**Files:**
- Modify: `docs/runbooks/slice-studio-production-deploy.md`
- Modify: `docs/reference/slice-studio-runtime.md`
- Modify: `PROGRESS.md`

- [ ] **Step 1: Replace the public production domain**

Change every current-production reference from `https://image.figma.245162.xyz` to `https://image.245162.xyz`, including validation commands and the Caddy site block example.

- [ ] **Step 2: Re-run a domain search**

Run: `rg -n "image\\.figma\\.245162\\.xyz" docs/reference/slice-studio-runtime.md docs/runbooks/slice-studio-production-deploy.md PROGRESS.md`
Expected: no matches in the current-production sections.

### Task 2: Cut over the origin host and production env

**Files:**
- Modify: `/opt/caddy/Caddyfile`
- Modify: `/opt/slice-studio/env/slice-studio.env`
- Modify: Cloudflare DNS record for `image.245162.xyz`

- [ ] **Step 1: Update the origin proxy host**

Change the Caddy site block to serve `image.245162.xyz` and keep `image.figma.245162.xyz` only if you want a temporary overlap window.

- [ ] **Step 2: Update production env to the new public origin**

Set `SLICE_STUDIO_PUBLIC_API_URL=https://image.245162.xyz` and `SLICE_STUDIO_ALLOWED_ORIGIN=https://image.245162.xyz,http://127.0.0.1:3010` on the production host.

- [ ] **Step 3: Create or switch the Cloudflare record**

Point `image.245162.xyz` at `192.236.242.152` and keep it proxied if you want Cloudflare in front again.

### Task 3: Verify HTTPS and remove stale references

**Files:**
- Verify: `docs/runbooks/slice-studio-production-deploy.md`
- Verify: `/opt/caddy/Caddyfile`

- [ ] **Step 1: Reload Caddy and check origin TLS**

Run on the server:

```bash
docker exec sub2api-caddy caddy validate --config /etc/caddy/Caddyfile
docker exec sub2api-caddy caddy reload --config /etc/caddy/Caddyfile
curl -vkI --resolve image.245162.xyz:443:192.236.242.152 https://image.245162.xyz
```

- [ ] **Step 2: Check public HTTPS**

Run:

```bash
curl -fsSI https://image.245162.xyz
curl -fsS https://image.245162.xyz/api/health
```

- [ ] **Step 3: Sweep for stale production-domain references**

Run:

```bash
rg -n "image\\.figma\\.245162\\.xyz" .
```

Expected: only intentional historical references remain, or none if the migration is fully complete.

### Self-Review

- Spec coverage: docs, origin proxy, env, DNS, and verification all have explicit tasks.
- Placeholder scan: no TBD/TODO steps.
- Type consistency: the new public host is `image.245162.xyz` everywhere in the current-production path.
