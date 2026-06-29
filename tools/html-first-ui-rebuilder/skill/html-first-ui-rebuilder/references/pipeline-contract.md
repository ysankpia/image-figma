# Pipeline Contract

## Truth Sources

- `asset_plan.json` is the ROI planning truth.
- `sheet_manifest.json` maps every sheet cell back to original page coordinates.
- `qwen_full_manifest.json` records the full-page Qwen request, cache hit/failure, and saved layers.
- `qwen_manifest.json` records Qwen requests, cache hits, failures, and saved layers.
- `asset_manifest.json` records extracted assets and their original page placement.
- `preview.html` is the first visual reconstruction artifact.

## Rules

- Never annotate source pixels before Qwen.
- Keep MoArk tokens in environment variables only.
- Cache by files on disk; do not delete `work/qwen/` between retries.
- Prefer original high-resolution pixels with Qwen-derived alpha masks over direct Qwen RGB output.
- If Qwen fails or no token is configured, still emit original ROI crops so HTML preview can be reviewed.
- Prefer full-page Qwen first when semantic layer separation is more important than quota minimization.
- Prefer `--one-roi-per-sheet` when quality matters. Multi-cell sheets are cheaper, but real Qwen tests showed they tend to produce coarse whole-cell layers.

## Manual Review Points

- Edit `asset_plan.json` before `make-sheets` when the heuristic ROI plan is too broad or misses assets.
- Inspect sheets before spending Qwen calls.
- Inspect `asset_manifest.json` before trusting `preview.html`.
- Use `report.md` as the durable handoff, not chat history.
