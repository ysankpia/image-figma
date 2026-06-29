# Plan 210: HTML-first full-page Qwen pass

Date: 2026-06-27
Status: completed

## Objective

Add and validate a full-page Qwen first pass for the standalone HTML-first UI Rebuilder skill.

The revised route is:

```text
screenshot
-> full-page Qwen layers
-> connected components from layer alpha
-> original-pixel masked assets
-> optional ROI sheet retry for missing assets
-> preview.html/report.md
```

## Scope

- Add a `qwen-full` CLI stage that sends the clean full screenshot to MoArk/Qwen once.
- Persist full-page request config, raw response, layers, and manifest separately from ROI sheet Qwen output.
- Extract full-page layer connected components into `asset_manifest.json` using Qwen alpha as mask and original image RGB as truth.
- Keep ROI sheet stages intact as fallback/retry path.
- Sync the repo-local skill and global `/Users/luhui/.agents/skills/html-first-ui-rebuilder` skill.
- Run the WeChat home screenshot as the golden experiment and write durable artifacts.

## Non-goals

- Do not connect this to Slice Studio runtime.
- Do not hardcode or document MoArk credentials.
- Do not rely on Qwen RGB output as the final asset when original pixels are available.
- Do not attempt Figma import in this pass.

## Validation

- `PYTHONPATH=src python3 -m unittest discover -s tests` passed.
- Global wrapper exposes `qwen-full`.
- The provided WeChat home screenshot was processed through a full-page Qwen 4-layer / 50-step real cached run imported from `/private/tmp/qwen-layered-probe/layers4_steps50`.
- Output run: `/Users/luhui/.agents/skills/html-first-ui-rebuilder/runs/wechat-home-full-page-real-cache`.
- Result: 16 total assets, 6 original ROI crops, 10 full-page Qwen connected components.
- Visual inspection contact sheet: `/Users/luhui/.agents/skills/html-first-ui-rebuilder/runs/wechat-home-full-page-real-cache/qwen-full-components-contact.jpg`.
- Observed quality: full-page Qwen is better than ROI sheets for hero title, hero characters, and avatars, but still emits reconstructable text as foreground components. The next quality gate must filter text/control components before using assets in HTML.
