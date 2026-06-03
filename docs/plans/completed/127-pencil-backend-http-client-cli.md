# 127 Pencil Backend HTTP Client CLI

Status: completed

## Summary

Add a small caller-side CLI for the Pencil Python Backend HTTP API.

The backend now has a caller API contract, but practical use still requires hand-written curl or custom frontend code. A deterministic CLI should upload one or more images, poll until completion, download `project.zip`, and verify the ZIP contract.

## Scope

- Add `scripts/upload_project.py`.
- Support repeated `--input` image files and input directories.
- Omit `boundarySource` by default so server default `psdlike` remains authoritative.
- Allow explicit `--boundary-source` for diagnostics.
- Poll status until `completed` or `failed`.
- Download `project.zip`.
- Verify required ZIP files and visible image refs.
- Document usage in README, API contract, and deploy runbook.

## Non-Goals

- No server API shape change.
- No frontend UI.
- No visual algorithm changes.
- No replacement for local offline `pencil-export`; this is only the HTTP caller path.

## Validation

Run:

```bash
cd services/pencil-python-backend
uv run python -m py_compile $(find app tests scripts -name '*.py' | sort)
uv run pytest -q
uv run python scripts/preflight.py
```

Start the local server and run:

```bash
uv run python scripts/upload_project.py \
  --base-url http://127.0.0.1:8100 \
  --input /absolute/path/to/sample.png \
  --out /Volumes/WorkDrive/pencil-exports/http-client-cli-smoke-20260604
```

Acceptance:

- CLI creates task without sending `boundarySource`.
- Task completes with `boundarySource=psdlike`.
- ZIP downloads.
- ZIP contract check returns `badRefs=0` and `missingRefs=0`.

## Completion Evidence

Static checks:

```text
uv run python -m py_compile $(find app tests scripts -name '*.py' | sort)
uv run pytest -q
15 passed, 1 warning
uv run python scripts/preflight.py
preflight=ok
```

HTTP caller CLI smoke:

```text
uv run python scripts/upload_project.py \
  --base-url http://127.0.0.1:8100 \
  --input /Volumes/WorkDrive/pencil-exports/shengxian-batch001-alpha-fallback-fix-20260604/debug/pages/page_0015/source.png \
  --out /Volumes/WorkDrive/pencil-exports/http-client-cli-smoke-20260604 \
  --project-name "HTTP Client CLI Smoke" \
  --mode all
```

Result:

```text
health=ok
queued taskId=pencil_20260603213324_94a6761db5 boundarySource=psdlike inputCount=1
status=running boundarySource=psdlike
completed taskId=pencil_20260603213324_94a6761db5 boundarySource=psdlike pageCount=1 modes=clean-editable,visual-fidelity,visual-ocr
manifest=/Volumes/WorkDrive/pencil-exports/http-client-cli-smoke-20260604/manifest.json
zip=/Volumes/WorkDrive/pencil-exports/http-client-cli-smoke-20260604/project.zip bytes=380309
clean-editable refs=2 badRefs=0 missingRefs=0
visual-fidelity refs=3 badRefs=0 missingRefs=0
visual-ocr refs=3 badRefs=0 missingRefs=0
ok
```
