---
name: html-first-ui-rebuilder
description: Standalone screenshot-to-HTML reconstruction workflow using clean ROI asset sheets, Qwen-Image-Layered masks, and Python CLI artifacts. Use when Codex needs to turn UI screenshots into extracted raster assets, preview.html, asset_manifest.json, and report.md without wiring into Slice Studio, Draft, Renderer, or Figma plugin runtimes.
---

# HTML-first UI Rebuilder

## Workflow

Use this skill for the new independent route:

```text
screenshot -> full-page Qwen layers -> connected components -> clean ROI crops/sheets for retries -> assets -> preview.html -> report.md
```

Do not draw boxes onto the image before Qwen. Put all box guidance in `asset_plan.json`; the sheet image must contain only clean source pixels and whitespace.

Prefer the full-page Qwen first pass when quality matters. Real tests showed Qwen keeps better semantic separation with the whole screenshot context; ROI sheets remain a fallback/retry path for missing assets.

## Commands

Run the repo-local CLI through the bundled wrapper:

```bash
python tools/html-first-ui-rebuilder/skill/html-first-ui-rebuilder/scripts/run_ui_rebuilder.py run --input /abs/page.png --out /abs/run-dir --mock-qwen
```

Use real Qwen only when `MOARK_API_TOKEN` is set:

```bash
python tools/html-first-ui-rebuilder/skill/html-first-ui-rebuilder/scripts/run_ui_rebuilder.py qwen --run /abs/run-dir --token-env MOARK_API_TOKEN
```

Stage commands:

```bash
python tools/html-first-ui-rebuilder/skill/html-first-ui-rebuilder/scripts/run_ui_rebuilder.py plan-assets --input /abs/page.png --out /abs/run-dir
python tools/html-first-ui-rebuilder/skill/html-first-ui-rebuilder/scripts/run_ui_rebuilder.py qwen-full --run /abs/run-dir --token-env MOARK_API_TOKEN
python tools/html-first-ui-rebuilder/skill/html-first-ui-rebuilder/scripts/run_ui_rebuilder.py make-sheets --run /abs/run-dir
python tools/html-first-ui-rebuilder/skill/html-first-ui-rebuilder/scripts/run_ui_rebuilder.py extract-assets --run /abs/run-dir
python tools/html-first-ui-rebuilder/skill/html-first-ui-rebuilder/scripts/run_ui_rebuilder.py build-html --run /abs/run-dir
python tools/html-first-ui-rebuilder/skill/html-first-ui-rebuilder/scripts/run_ui_rebuilder.py diff --run /abs/run-dir
```

Use one-call full-page quality mode to test the new route without burning per-ROI quota:

```bash
python tools/html-first-ui-rebuilder/skill/html-first-ui-rebuilder/scripts/run_ui_rebuilder.py run --input /abs/page.png --out /abs/run-dir --full-page-qwen --skip-sheet-qwen
```

Use quality mode when Qwen is expected to separate assets:

```bash
python tools/html-first-ui-rebuilder/skill/html-first-ui-rebuilder/scripts/run_ui_rebuilder.py run --input /abs/page.png --out /abs/run-dir --one-roi-per-sheet
```

## Editing Loop

1. Generate `asset_plan.json`.
2. Use vision reasoning to edit ROI boxes and names in that JSON.
3. Run `make-sheets`; inspect `work/sheets/*.png`.
4. Run `qwen-full`; inspect `qwen_full_manifest.json` and `work/qwen_full/full_page/layer_*.png`.
5. Run `qwen` only for ROI retries; inspect `qwen_manifest.json`.
6. Run `extract-assets`; inspect `assets/` and `asset_manifest.json`.
7. Run `build-html` and `diff`; inspect `preview.html` and `report.md`.

For contract details, read `references/pipeline-contract.md`.
