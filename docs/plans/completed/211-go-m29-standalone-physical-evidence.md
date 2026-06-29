# 211 Go M29 Standalone Physical Evidence

Status: completed

Note: final standalone shape was narrowed by [212 Go M29 Standalone Minimal Locator](212-go-m29-standalone-minimal-locator.md). Plan 211 records the initial copy-and-isolate split; plan 212 is the current tool contract.

## Goal

Split the archived Go M29 physical evidence capability into a standalone tool directory without moving or editing the archived source.

## Scope

- Add a new standalone Go module under `tools/go-m29-physical-evidence/`.
- Copy the Go M29 physical evidence chain needed by `m29extract`:
  - `cmd/m29extract`
  - `cmd/m29tokens`
  - `internal/m29`
- Keep output contracts compatible with the archived implementation:
  - `m29_physical_evidence.v1.json`
  - `evidence_tokens.v1.json`
  - masks, crops, debug overlay, preview sheet
- Document the standalone commands and the original source boundary.

## Non-Scope

```text
Do not edit archive/legacy-code/services/backend-go/.
Do not move or delete archived source.
Do not revive Draft, vision, renderer, plugin, or Codia routes.
Do not wire the standalone tool into Slice Studio runtime in this pass.
```

## Acceptance

- `go test ./...` passes inside `tools/go-m29-physical-evidence/`.
- `go run ./cmd/m29extract --input <png> --out <dir> --ocr-provider none` writes `m29_physical_evidence.v1.json`.
- `go run ./cmd/m29tokens --input <m29_physical_evidence.v1.json> --out <dir>` writes `evidence_tokens.v1.json`.
- Git diff shows archived Go M29 source untouched.

## Validation

```bash
cd tools/go-m29-physical-evidence
go test ./...
go run ./cmd/m29extract --input <sample.png> --out <tmp>/m29 --ocr-provider none
go run ./cmd/m29tokens --input <tmp>/m29/m29_physical_evidence.v1.json --out <tmp>/tokens

git diff -- archive/legacy-code/services/backend-go
git diff --check
git status --short --branch
```

## Completion Evidence

- Added standalone module: `tools/go-m29-physical-evidence/`.
- Copied `cmd/m29extract`, `cmd/m29tokens`, and `internal/m29` into the standalone module.
- Rewrote imports only inside the new module.
- `go test ./...` passed inside `tools/go-m29-physical-evidence/`.
- Real sample smoke passed:
  - `go run ./cmd/m29extract --input docs/reference/codia-samples/images/腾讯动漫_018_1440.png --out /tmp/go-m29-standalone-smoke/m29 --ocr-provider none`
  - `go run ./cmd/m29tokens --input /tmp/go-m29-standalone-smoke/m29/m29_physical_evidence.v1.json --out /tmp/go-m29-standalone-smoke/tokens`
  - output contained `m29_physical_evidence.v1.json` with `210` primitives and `evidence_tokens.v1.json` with `76` tokens.
  - sample primitive bbox: `{ "x": 249, "y": 14, "width": 167, "height": 42 }`.
