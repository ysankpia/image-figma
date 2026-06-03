# 122 Pencil Default PSD-like Boundary Source

Status: completed

## Summary

Make the Pencil Python backend default to the already validated PSD-like boundary path when callers do not explicitly choose a boundary source.

Current delivery evidence shows:

```text
psdlike -> pencil-python-backend -> .pen/project.zip
```

is the lower-fragment product path for Pencil handoff. Keeping HTTP/CLI defaults on `m29` makes deployed clients silently fall back to the fragmented path whenever they omit `boundarySource`.

## Scope

- Add `PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE`.
- Default it to `psdlike`.
- Use the same default for HTTP uploads and CLI exports when `boundarySource` / `--boundary-source` is omitted.
- Preserve explicit `m29`, `psdlike`, and `hybrid` requests.
- Update README, `.env.example`, and environment variable docs.

## Non-Goals

- No new visual heuristics.
- No YOLO integration.
- No Figma plugin changes.
- No `services/pencil-go` changes.
- No change to the existing `m29`, `psdlike`, or `hybrid` exporter behavior.

## Validation

Run:

```bash
cd services/pencil-python-backend
uv run python -m py_compile $(find app tests -name '*.py' | sort)
uv run pytest -q
```

Run HTTP smoke without sending `boundarySource`:

```text
PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=psdlike
POST /api/pencil/projects
```

Acceptance:

- queued/status/manifest report `boundarySource=psdlike`.
- project ZIP is downloadable.
- generated `.pen` files have no missing visible asset refs.

## Completion Evidence

Static validation:

```bash
cd services/pencil-python-backend
uv run python -m py_compile $(find app tests -name '*.py' | sort)
uv run pytest -q
```

Result:

```text
15 passed, 1 warning
```

HTTP smoke without `boundarySource`:

```text
taskId=pencil_20260603211125_9e50756059
queued boundarySource=psdlike
status completed boundarySource=psdlike
manifest boundarySource=psdlike pageCount=1 modes=clean-editable,visual-fidelity,visual-ocr
zip bytes=380332
```

Downloaded ZIP:

```text
/Volumes/WorkDrive/pencil-exports/http-default-psdlike-smoke-20260604.zip
```

Unzipped contract check:

```text
manifest.json exists
clean-editable/design.pen exists
visual-fidelity/design.pen exists
visual-ocr/design.pen exists
debug/report.md exists
clean-editable refs=0 bad=0 missing=0
visual-fidelity refs=0 bad=0 missing=0
visual-ocr refs=0 bad=0 missing=0
```
