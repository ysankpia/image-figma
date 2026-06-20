# Plan 206: Export/Download Speedup

## Background
Export slow in production — first-time project export (especially multi-page) can take minutes, and re-export after slice edits re-runs OCR/text-reconstruction/remainder from scratch. Profile shows: remote OCR serial per page, repeated sharp raw decodes, per-pixel JS on full-resolution images, pure-JS CRC32 for large zips.

## Approach: Two-phase — evidence caching + parallelism

### Architecture change: split text reconstruction into evidence gathering and layer synthesis
- **Evidence gathering**: OCR + M29 physical evidence + psdlike text styles — depends ONLY on original image + provider config. Cacheable by image content hash.
- **Layer synthesis**: refineWithLocalForeground, classifyTextOwnership, makeTextLayer, harmonize — depends on slices + cached evidence + raw image. Runs in Workers.

### Phase 1: Pure TS quick wins
1. **F**: `shared/zip.ts` CRC32 → `node:zlib.crc32`
2. **G**: `storage.ts` add `readAsync` using `Bun.file().arrayBuffer()`
3. **E**: `exporter.ts` slice cropping `for...of + await` → `Promise.all`
4. **D**: `pencil-exporter.ts` decode original to raw once per page, pass to remainder/text-reconstruction
5. **A**: `server/ocr-cache.ts` — cache OCR/M29/text-style results by original image content hash + provider version
6. **B**: `pencil-exporter.ts` OCR across pages concurrently (limit 3-4 for Baidu rate limiting)

### Phase 2: Bun Workers for CPU-bound per-page work
7. **C**: `server/export-page-worker.ts` — worker script: receives raw buffer (transferable) + cached evidence + slices, returns slice pngs/placements/textLayers/remainder/controlSurfaces
8. **C**: `server/page-worker-pool.ts` — bounded worker pool (concurrency = min(pages, cores-1))

## New files
- `server/ocr-cache.ts` — OCR/evidence cache by image content hash
- `server/export-page-worker.ts` — Bun worker for per-page CPU work
- `server/page-worker-pool.ts` — bounded worker pool manager

## Modified files
- `shared/zip.ts` — CRC32 → node:zlib.crc32
- `server/storage.ts` — add `readAsync`
- `server/exporter.ts` — slice cropping parallel, async reads
- `server/pencil-exporter.ts` — OCR concurrency, raw decode once, worker pool integration
- `server/text-reconstruction.ts` — split evidence/synthesis, accept cached evidence

## Validation
```bash
pnpm run check
pnpm run build
git diff --check
bun scripts/smoke.ts
```
Plus timing comparison on a multi-page project before/after.

## Non-goals
- No new native dependencies (Go, Rust, napi-rs) — Bun Workers path keeps zero-install
- No changes to file download/streaming (already streaming with Bun.file)
- No changes to export cache fingerprint schema (remains slice-aware)
