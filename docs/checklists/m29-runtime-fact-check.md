# M29 Runtime Fact Check

Use this checklist before closing changes that affect M29 evidence, image math, replay, cleanup, materialization, or generated artifacts.

## Report-Only Surfaces

Confirm these stages remain report-only unless a separate approved plan says otherwise:

```text
M29 ownership conservation report
M29.6 media internal decomposition report
M29 transparent asset report
M29 evidence contract report
M29 hierarchy candidate report
M29 sibling group candidate report
M29 layout energy report
M29 Auto Layout permission report
M29 design token report
M29 B-stage quality report
```

Check:

- `dslChanged=false`
- `assetChanged=false` unless the artifact is explicitly diagnostic
- `createdVisibleNodeCount=0`
- no cleanup authorization is issued from report-only stages
- no direct materializer input is created from report-only stages except through the documented bridge

## Promotion And Cleanup

Confirm:

- M29.6 does not promote source objects by itself.
- transparent asset report does not replace materialized assets by itself.
- evidence contract remains report-only and does not create source objects.
- internal source promotion is the only bridge from M29.6/transparent/evidence-contract evidence back into M29.2 source objects.
- promoted source objects are reprocessed through M29.3/M29.4/M29.5 before materialization.
- copied media cleanup exists only when M29.5 writes a cleanup target.
- materializer only consumes M29.5 cleanup targets.

## Image Math Boundary

Confirm:

- Pillow / NumPy / scikit-image direct imports appear only under `backend/app/image_math/`.
- `orjson` direct import appears only in `backend/app/json_tools.py`.
- `rich` does not appear under `backend/app/`.
- image_math does not import M29 domain modules, upload pipeline, plan materializer, Renderer, Figma plugin, or DSL schema.
- image_math does not contain source-truth decision strings such as `pixelOwner`, `replayDecision`, `cleanupAuthorization`, `materialize`, `autoLayout`, or `componentIdentity`.

## Anti-Specialization

Search or inspect for new logic tied to:

```text
filename
path
sample id
fixture id
visible text
brand
theme color
industry
fixed coordinate
fixed screen size
fixed bbox
one screenshot structure
```

If a threshold is added, record:

- why it exists;
- which domain it applies to;
- which domain it does not apply to;
- which tests or real samples protect it;
- what failure mode it accepts.

## Validation

For image_math boundary changes:

```bash
cd backend
uv run pytest tests/test_image_math_import_boundaries.py -q
uv run pytest -q
git diff --check
```

For behavior-affecting M29 changes, also map the change to:

```text
docs/engineering/m29-contract-regression-matrix.md
```

and run the affected targeted tests before full backend regression.
