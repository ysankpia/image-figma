# Plan 209: HTML-first UI Rebuilder

Date: 2026-06-26
Status: completed

## Objective

Create a standalone Python-first project for the new screenshot-to-HTML route. It must not attach to the current Slice Studio runtime.

Target pipeline:

```text
UI screenshot
-> asset_plan.json
-> clean ROI crops
-> asset sheets
-> Qwen-Image-Layered layers
-> extracted assets
-> preview.html
-> report.md
```

## Scope

- Add an independent CLI project under `tools/html-first-ui-rebuilder/`.
- Add a repo-local Codex skill under `tools/html-first-ui-rebuilder/skill/html-first-ui-rebuilder/`.
- Keep MoArk token handling environment-variable only.
- Keep Qwen calls resumable and cacheable through on-disk artifacts.
- Provide an offline/mock path for validation when no API token is available.

## Non-goals

- Do not wire into Slice Studio APIs, database, Review Workbench, or export contracts.
- Do not revive Go Draft, old Python upload-preview, old Figma plugin, or old Renderer as runtime dependencies.
- Do not hardcode the user-provided MoArk token.
- Do not make Figma import part of v1; v1 produces HTML/CSS and artifacts.

## Validation

- `PYTHONPATH=src python3 -m unittest discover -s tests` passed.
- Repo-local skill validation passed with `quick_validate.py`.
- The provided WeChat home screenshot was processed through the mock-Qwen route at `tools/html-first-ui-rebuilder/runs/wechat-home-mock/`.
- The sample produced 6 ROIs, 2 sheets, 12 assets, `preview.html`, and `report.md`.
- Browser screenshot validation used system Chrome through Playwright CLI; rendered preview diff reported `mae=1.795`, `psnr=24.51`.
- The global skill was installed at `/Users/luhui/.agents/skills/html-first-ui-rebuilder`.
- Real MoArk/Qwen tests completed. Multi-cell sheets produced only one useful mask after filtering; quality mode with one ROI per sheet produced 6 successful Qwen requests, 14 total assets, and 8 Qwen-mask assets. Useful masks included hero title artwork and bottom navigation icon strip; category/list rows still skewed toward text blocks, proving the next quality step is smaller vision-planned ROIs rather than larger row-level ROIs.
- `git diff --check` passed.
