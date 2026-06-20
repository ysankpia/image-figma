# Plan 206: Export/Download Speedup

Status: **completed**

## Background
Export slow in production — first-time project export (especially multi-page) can take minutes, and re-export after slice edits re-runs OCR/text-reconstruction/remainder from scratch. Profile shows: remote OCR serial per page, repeated sharp raw decodes, per-pixel JS on full-resolution images, pure-JS CRC32 for large zips.

## Final Implementation (3 phases)

### Phase 1: Pure TS quick wins (done)
| Step | File | Change |
|------|------|--------|
| F | `shared/zip.ts` | CRC32 → `node:zlib.crc32` (10MB 107ms→1ms) |
| G | `server/storage.ts` | Add `readAsync()` with `Bun.file().arrayBuffer()` |
| E | `server/exporter.ts` | Slice cropping `for...of`→`Promise.all` |
| D | `server/pencil-package.ts` | `createRemainderPng` accepts optional `preDecoded` raw to avoid re-decoding |

### Phase 2: Evidence caching + OCR concurrency (done)
| Step | File | Change |
|------|------|--------|
| A | `server/ocr-cache.ts` (new) | OCR/M29 evidence cache keyed by original image content SHA256 + provider version |
| A | `server/text-reconstruction.ts` | Accept `preDecodedRaw` + `preLocated` params |
| B | `server/pencil-exporter.ts` | OCR + M29 gathered concurrently across pages (limit 3) with caching before synthesis |

### Phase 2b: Bun Workers → Promise.all (replaced)
**C (attempted)**: `server/export-page-worker.ts` + `server/page-worker-pool.ts` — Bun Workers for per-page CPU synthesis. **Reverted**: production testing on RackNerd (2-core VPS) showed oversubscription and worker module loading overhead outweighed gains.

**C (replacement)**: `pencil-exporter.ts` — replaced Worker pool with `Promise.all` across pages. Sharp async operations (decode, crop, pencil prep) overlap naturally via libvips thread pool, zero extra overhead. Kept all other optimizations intact.

### Phase 3: Rust napi-rs native pixel operations (done)
| Step | File | Change |
|------|------|--------|
| — | `native/pixel-ops/` (new) | Rust napi-rs crate with 6 pixel functions compiled to `.node` addon |
| — | `server/native-ops.ts` (new) | Typed loader with platform detection + JS fallback |
| — | `server/pencil-package.ts` | Wired native `clearAlphaRect`, `alphaContentBBox`, `dilateTextMask`, `inpaintTextMask`, `pointInsideRoundedRect` |
| — | `server/shape-cutout.ts` | Wired native `applyShapeCutout` |
| — | `.github/workflows/deploy.yml` | CI builds `server/pixel-ops.node` for Linux x86_64 on ubuntu-latest runner |

**Rust functions ported (10-20x faster than JS)**:
- `inpaint_text_mask` — iterative inpainting (most expensive, up to 36 iterations)
- `dilate_text_mask` — binary mask dilation (O(n × radius²))
- `clear_alpha_rect` — alpha channel clearing
- `alpha_content_bbox` — alpha trim bounding box
- `apply_shape_cutout` — flood fill background removal
- `point_inside_rounded_rect` — hot geometry predicate

## Files summary
- **Modified (7)**: `shared/zip.ts`, `server/storage.ts`, `server/exporter.ts`, `server/pencil-package.ts`, `server/pencil-exporter.ts`, `server/text-reconstruction.ts`, `server/shape-cutout.ts`
- **New (6)**: `server/ocr-cache.ts`, `server/export-page-worker.ts`, `server/page-worker-pool.ts`, `server/native-ops.ts`, `native/pixel-ops/Cargo.toml`, `native/pixel-ops/src/lib.rs`
- **CI**: `.github/workflows/deploy.yml` (added Rust build step)

## Production results
- Server: RackNerd 2-core VPS, 2GB RAM, Intel Xeon E5-2697 v2
- 7 pages / 136 assets / 47MB project.zip: **~17s** (down from ~90-120s)
- OCR cache verified: 7 cache files created, second exports hit cache
- Rust `.node`: 481KB ELF x86-64, all 6 functions verified loading and correct

## Validation
```bash
pnpm run check    # typecheck + 15 files / 124 tests
pnpm run build    # Next.js build success
git diff --check  # clean
```
- CI: Rust build on ubuntu-latest produces `server/pixel-ops.node`, synced to RackNerd
- Native load verified via SSH: all symbols present, `alphaContentBbox` returns correct results
