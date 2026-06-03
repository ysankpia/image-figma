# 126 Pencil Export Codex Skill Refresh

Status: completed

## Summary

Refresh the local Codex `pencil-export` skill so future agent runs use the current Pencil Python Backend product path:

```text
PSD-like boundary source by default
-> Pencil Python exporter
-> clean-editable / visual-fidelity / visual-ocr
-> project.zip
```

The skill was stale and still described the old `local m29extract executable -> Python Pencil exporter` path as the product default.

## Scope

Updated local files outside this git repository:

```text
/Users/luhui/.codex/skills/pencil-export/SKILL.md
/Users/luhui/.codex/skills/pencil-export/evals.json
```

Changes:

- Described PSD-like as the normal product boundary source.
- Kept `m29` and `hybrid` as explicit diagnostic/fallback paths.
- Added preflight as a first check.
- Added HTTP smoke as a deployment validation gate.
- Linked the current caller API contract and deploy runbook.
- Updated common commands to set `PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=psdlike`.
- Added eval expectations for default PSD-like, preflight, HTTP smoke, and caller API contract usage.

## Non-Goals

- Did not copy local skill files into this repo.
- Did not change backend runtime behavior.
- Did not change visual algorithms.
- Did not install or publish a marketplace skill.

## Validation

Commands:

```bash
command -v pencil-export
pencil-export --help
PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=psdlike uv run python scripts/preflight.py
python -m json.tool /Users/luhui/.codex/skills/pencil-export/evals.json >/dev/null
```

Evidence:

```text
/Users/luhui/.local/bin/pencil-export
--boundary-source help: Boundary source. Defaults to PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE.
defaultBoundarySource=psdlike
psdlikeRunner=ok /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python/tools/run_one.py
m29extract=ok /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/backend-go/bin/m29extract
preflight=ok
evals_json_ok
```
