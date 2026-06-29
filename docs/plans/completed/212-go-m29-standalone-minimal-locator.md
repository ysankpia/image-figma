# 212 Go M29 Standalone Minimal Locator

Status: completed

## Goal

Prune `tools/go-m29-physical-evidence/` down to the M29.0 capability the user actually needs:

```text
input PNG
-> original-image pixel bbox JSON
-> matching crop PNGs
```

## Scope

- Keep only the pixel-location chain:
  - PNG read/write
  - background estimate
  - foreground mask
  - connected components
  - component measurements and coarse kind
  - bbox JSON
  - crop PNG per bbox
- Replace the old copied `m29extract`/`m29tokens` surface with a minimal locator command.
- Keep the archived Go backend untouched.

## Remove From Standalone Module

```text
OCR/Baidu OCR
env/config loading
M29 evidence token compiler
Draft-era token overlays and preview sheets
debug overlay/preview sheet generation
surface OCR owner detection
internal raster crop heuristics
physical relation graph
```

## Non-Scope

```text
Do not modify archive/legacy-code/services/backend-go/.
Do not wire this into Slice Studio.
Do not revive Draft, vision, renderer, plugin, Codia, or OCR routes.
```

## Acceptance

- `tools/go-m29-physical-evidence/` has one CLI for minimal location.
- Running it on one PNG writes:
  - `m29_locations.v1.json`
  - `crops/*.png`
- JSON items contain `id`, `kind`, `bbox`, `cropPath`, and measurements/hints needed to inspect the result.
- `go test ./...` passes inside the standalone module.
- `git diff -- archive/legacy-code/services/backend-go` remains empty.

## Validation

```bash
cd tools/go-m29-physical-evidence
go test ./...
go run ./cmd/m29locate --input <sample.png> --out <tmp>/m29locate
```

## Completion Evidence

- Pruned the standalone module from the copied 204KB Go M29 backend subset down to a 52KB locator module.
- Removed from the standalone module:
  - `cmd/m29extract`
  - `cmd/m29tokens`
  - `internal/m29/config`
  - `internal/m29/debug`
  - `internal/m29/evidence`
  - `internal/m29/ocr`
  - `internal/m29/pipeline`
- Added the minimal CLI:
  - `cmd/m29locate`
- Added the minimal output contract:
  - `m29_locations.v1.json`
  - `crops/loc_*.png`
- Validation passed:
  - `go test ./...`
  - `go run ./cmd/m29locate --input docs/reference/codia-samples/images/腾讯动漫_018_1440.png --out /tmp/go-m29-locate-smoke`
- Real sample output:
  - `210` JSON items.
  - `210` crop PNGs plus one JSON file.
  - first bbox: `{ "x": 249, "y": 14, "width": 167, "height": 42 }`.
  - no token, OCR, overlay, preview, Draft, vision, or relation artifacts were produced.
