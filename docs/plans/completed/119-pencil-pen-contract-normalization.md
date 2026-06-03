# 119 Pencil .pen Contract Normalization

## Status

Completed.

## Goal

Normalize `services/pencil-python-backend` output to match Pencil-native `.pen`
contracts observed from a real Pencil-authored design file. This is a contract
fix, not a visual-boundary algorithm change.

## Scope

- Emit image fills with `enabled: true`.
- Emit editable shape strokes as Pencil-native objects:
  `{"align":"inside","thickness":1,"fill":"#..."}`.
- Reject project-level `.pen` output that contains non-portable visible image
  references such as `../`, absolute local paths, raw crops, masks, debug paths,
  or `source.png`.
- Keep project visible asset filenames globally unique across pages and modes.
- Add unit coverage for the contract.

## Non-Goals

- Do not change OCR, text knockout, PSD-like, or hybrid boundary algorithms.
- Do not modify the Figma import plugin.
- Do not depend on Pencil agent auto-reconstruction.

## Validation

```bash
cd services/pencil-python-backend
uv run python -m py_compile $(find app tests -name '*.py' | sort)
uv run pytest -q
```

Run one sample export and verify Pencil CLI can export a preview PNG.

## Completion Evidence

- `cd services/pencil-python-backend && uv run python -m py_compile $(find app tests -name '*.py' | sort)`
- `cd services/pencil-python-backend && uv run pytest -q`
- `cd services/pencil-python-backend && PENCIL_BACKEND_M29EXTRACT=../backend-go/bin/m29extract uv run python -m app.cli.export_project --input "/Users/luhui/Downloads/兼职/ChatGPT Image 2026年5月28日 00_07_42 1.png" --out /Volumes/WorkDrive/pencil-exports/contract-smoke-20260603-214120 --project-name "Contract Smoke" --mode all --boundary-source m29 --ocr-provider none --include-debug`
- `pencil --in /Volumes/WorkDrive/pencil-exports/contract-smoke-20260603-214120/visual-fidelity/design.pen --export /Volumes/WorkDrive/pencil-exports/contract-smoke-20260603-214120/preview/visual-fidelity.png --export-scale 1`
