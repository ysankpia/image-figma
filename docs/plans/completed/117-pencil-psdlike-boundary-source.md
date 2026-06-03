# 117 Pencil PSD-like Boundary Source Integration

## Summary

Formalize the previously validated PSD-like layer decomposition as an optional Pencil Python Backend boundary source. The current `M29 -> Pencil` path is already usable, but M29 emits many primitive crops. PSD-like produces coarser raster/shape/text layer boundaries and is a better source for fewer visible Pencil objects.

This plan does not revive the rejected resource-kit experiment. The new contract is:

```text
1..N images
-> boundary source: psdlike | m29
-> normalized single-page Pencil evidence
-> existing clean-editable / visual-fidelity / visual-ocr exporter
-> project ZIP
```

## First-Principles Judgment

The source truth for this problem is not the HTML preview. `preview.html` only renders an already-selected DSL. The useful source truth is the PSD-like `layer_stack.v1.json`, because it contains the coarse object boundaries that reduce fragment explosion.

M29 remains useful as high-recall physical evidence. PSD-like is useful as page-level boundary proposal. They should be selectable boundary sources, not patched into each other with file-, page-, or UI-specific rules.

## Scope

- Add `boundarySource` support to `services/pencil-python-backend`.
- Supported values:
  - `psdlike`: run `services/psdlike-python/tools/run_one.py` as a subprocess, then normalize `layer_stack.v1.json` to the existing single-page exporter input.
  - `m29`: preserve the existing `m29extract` path.
- Preserve the existing output modes and ZIP layout.
- Preserve existing HTTP and CLI behavior with one extra option.
- Keep debug artifacts for boundary inspection.

## Non-Goals

- No web/mobile/tab/header/button special cases.
- No resource-kit manifest revival.
- No direct import of `services/psdlike-python/app` into the Pencil backend process, because both services use the top-level Python package name `app`.
- No Figma plugin, Draft runtime, renderer, or Go backend changes.
- No new model dependency.

## Implementation

1. Add a PSD-like runner subprocess wrapper.
2. Add a PSD-like adapter:
   - raster layers become image crop replay layers;
   - shape layers become editable shape replay layers, not image assets;
   - text layers become OCR text primitives with source crops for color sampling and visual-fidelity fallback.
3. Extend the single-page Pencil exporter to render replay shape layers as Pencil rectangles.
4. Extend project builder, CLI, API, task state, and manifest with `boundarySource`.
5. Update tests and docs.

## Validation

Run:

```bash
cd services/pencil-python-backend
uv run python -m py_compile $(find app tests -name '*.py' | sort)
uv run pytest -q
```

Run real sample export:

```bash
cd services/pencil-python-backend
OCR_PROVIDER=baidu_ppocrv5 uv run python -m app.cli.export_project \
  --input /Users/luhui/Downloads/兼职 \
  --out /Volumes/WorkDrive/pencil-exports/jianzhi-psdlike-boundary-smoke \
  --project-name "兼职 PSD-like Boundary" \
  --mode all \
  --columns auto \
  --boundary-source psdlike \
  --include-debug
```

Acceptance signals:

- ZIP exists.
- All requested modes contain `design.pen`.
- Project manifest records `boundarySource=psdlike`.
- Debug contains PSD-like `layer_stack.v1.json`, `overlay.png`, `preview.html`, and adapted evidence.
- Asset counts are materially lower than M29-fragment-heavy exports on the same set.
- `.pen` files do not reference source/raw/mask/debug assets.
