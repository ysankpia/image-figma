# 123 Pencil Backend Deploy Runbook And Smoke

Status: completed

## Summary

Turn the validated Pencil Python Backend path into an operable self-use/server deployment surface.

The previous stage made `psdlike` the default boundary source. This stage documents how to run that service under systemd and adds a reusable HTTP smoke script so deployment validation is not reconstructed from chat history.

## Scope

- Add server env and systemd templates for `services/pencil-python-backend`.
- Add deployment runbook under `docs/runbooks/`.
- Add an HTTP smoke script that uploads one image without `boundarySource`.
- Validate that default `boundarySource=psdlike`, task completion, ZIP download, and `.pen` visible asset refs are correct.
- Update local service README to point at the runbook and smoke command.

## Non-Goals

- No algorithm changes.
- No Figma plugin changes.
- No nginx automation.
- No remote server mutation in this stage.

## Validation

Run:

```bash
cd services/pencil-python-backend
uv run python -m py_compile $(find app tests scripts -name '*.py' | sort)
uv run pytest -q
```

Start local server with `PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=psdlike`, then run:

```bash
uv run python scripts/http_smoke.py \
  --base-url http://127.0.0.1:8100 \
  --image /absolute/path/to/sample.png \
  --out /Volumes/WorkDrive/pencil-exports/pencil-backend-deploy-smoke-20260604
```

Acceptance:

- Health returns ok.
- Upload response reports `boundarySource=psdlike`.
- Task completes.
- Manifest reports `boundarySource=psdlike`.
- Downloaded ZIP contains all three mode `.pen` files and debug report.
- `.pen` image refs have `badRefs=0` and `missingRefs=0`.

## Completion Evidence

Static checks:

```text
uv run python -m py_compile $(find app tests scripts -name '*.py' | sort)
uv run pytest -q
15 passed, 1 warning
```

HTTP smoke:

```text
uv run python scripts/http_smoke.py \
  --base-url http://127.0.0.1:8100 \
  --image /Volumes/WorkDrive/pencil-exports/shengxian-batch001-alpha-fallback-fix-20260604/debug/pages/page_0015/source.png \
  --out /Volumes/WorkDrive/pencil-exports/pencil-backend-deploy-smoke-20260604
```

Result:

```text
health=ok
queued taskId=pencil_20260603211804_6d110631ce boundarySource=psdlike
status=completed boundarySource=psdlike
manifest boundarySource=psdlike pageCount=1 modes=clean-editable,visual-fidelity,visual-ocr
zip=/Volumes/WorkDrive/pencil-exports/pencil-backend-deploy-smoke-20260604/project.zip bytes=380283
clean-editable refs=2 badRefs=0 missingRefs=0
visual-fidelity refs=3 badRefs=0 missingRefs=0
visual-ocr refs=3 badRefs=0 missingRefs=0
ok
```
