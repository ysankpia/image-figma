# ADR 0074: Introduce Image Math Execution Dependencies

- 状态：accepted
- 日期：2026-05-26

## Context

The M29 pipeline has multiple pixel-heavy report and diagnostic stages: foreground masks, connected components, text masks, local background estimates, alpha extraction, and visual comparison. Some current implementations use standard-library PNG decoding and pure Python loops. That kept the early system deterministic and dependency-light, but it now makes image math slower and harder to test in isolation.

The risk is not the libraries themselves. The risk is letting image libraries become a new decision authority that bypasses M29 source truth.

## Decision

Introduce Pillow, NumPy, and scikit-image strictly as an image math execution layer under:

```text
backend/app/image_math/
```

Introduce orjson strictly behind:

```text
backend/app/json_tools.py
```

Introduce rich only as a backend dev/script dependency.

Core sentence:

```text
Pillow / NumPy / scikit-image are image math execution dependencies.
They are not source truth dependencies.
They must not decide ownership, replay, cleanup, materialization, component identity, or Auto Layout permission.
```

## Allowed Usage

Pillow, NumPy, and scikit-image may:

- decode and normalize pixels;
- convert PIL images to arrays and arrays to PIL images;
- crop arrays by bbox;
- calculate masks, mask area, mask bbox, overlap, IoU, and containment;
- label connected components and expose pure component metrics;
- run morphology operations such as open, close, dilate, erode, remove small objects, and fill holes;
- estimate local backgrounds, edge/ring samples, distance maps, luma, edge strength, texture, variance, and pixel difference metrics;
- generate RGBA bytes or diagnostic overlay images.

orjson may:

- serialize and deserialize backend-owned JSON through `json_tools`;
- keep Chinese text unescaped;
- support compact and pretty output.

rich may:

- format developer-facing script output;
- improve batch validation logs;
- run in dev/test tooling only.

## Forbidden Usage

Pillow, NumPy, and scikit-image must not:

- decide `pixelOwner`;
- decide `visualKind`;
- decide `replayDecision`;
- sign cleanup authorization;
- create DSL nodes;
- mutate materialization output;
- infer component identity;
- infer Auto Layout permission;
- replace M29.2, M29.5, ownership conservation, or evidence contract decisions;
- contain text, filename, brand, theme, path, coordinate, bbox, sample-id, or screenshot-specific rules.

orjson must not:

- be imported directly across backend app modules;
- change API response shape;
- change DSL schema or semantic output;
- hide non-serializable objects behind silent lossy conversion.

rich must not:

- be imported under `backend/app/`;
- affect production runtime behavior.

## Consequences

Benefits:

- Pixel math becomes faster and easier to test.
- Image math dependencies are auditable because import-boundary tests localize them.
- Future migrations can be guarded with parity tests before changing production behavior.

Costs:

- Backend install size increases.
- `uv.lock` churn is expected.
- Boundary tests become mandatory to prevent dependency creep.
- Stage 1 must update dependency policy and local setup expectations.

## Validation

Required tests:

```text
backend/tests/test_json_tools.py
backend/tests/test_image_math_arrays.py
backend/tests/test_image_math_masks.py
backend/tests/test_image_math_components.py
backend/tests/test_image_math_alpha.py
backend/tests/test_image_math_import_boundaries.py
```

Required commands:

```bash
cd backend
uv sync
uv run pytest -q
git diff --check
```

## Non-Goals

- No production migration in the first round.
- No DSL schema change.
- No API response contract change.
- No Renderer or Figma plugin change.
- No cleanup authorization change.
- No materializer decision change.
- No Auto Layout, Component, Variant, Variables, SVG, or vectorization.
- No SAM, ONNX, OpenCV, PyTorch, or local OCR dependency.
