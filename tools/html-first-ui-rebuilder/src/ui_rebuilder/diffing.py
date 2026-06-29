from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat

from .io import now_iso, read_json, rel, write_json
from .paths import RunPaths
from .planner import source_image_path


def write_report(paths: RunPaths, rendered: Path | None = None) -> dict[str, Any]:
    asset_manifest = read_json(paths.asset_manifest_json) if paths.asset_manifest_json.exists() else {"assets": [], "summary": {}}
    qwen_manifest = read_json(paths.qwen_manifest_json) if paths.qwen_manifest_json.exists() else {"results": []}
    qwen_full_manifest = read_json(paths.qwen_full_manifest_json) if paths.qwen_full_manifest_json.exists() else {"result": {}}
    sheet_manifest = read_json(paths.sheet_manifest_json) if paths.sheet_manifest_json.exists() else {"sheets": []}
    metrics: dict[str, Any] | None = None
    rendered_path: Path | None = rendered

    if rendered_path is None:
        rendered_path = _try_render_with_playwright(paths)
    if rendered_path and rendered_path.exists():
        metrics = image_diff(source_image_path(paths), rendered_path, paths.diff_png)

    lines = [
        "# HTML-first UI Rebuilder Report",
        "",
        f"Generated: {now_iso()}",
        "",
        "## Artifacts",
        "",
        f"- preview: `{rel(paths.preview_html, paths.root)}`" if paths.preview_html.exists() else "- preview: missing",
        f"- asset manifest: `{rel(paths.asset_manifest_json, paths.root)}`" if paths.asset_manifest_json.exists() else "- asset manifest: missing",
        f"- sheet manifest: `{rel(paths.sheet_manifest_json, paths.root)}`" if paths.sheet_manifest_json.exists() else "- sheet manifest: missing",
        "",
        "## Summary",
        "",
        f"- sheets: {len(sheet_manifest.get('sheets', []))}",
        f"- assets: {asset_manifest.get('summary', {}).get('assetCount', len(asset_manifest.get('assets', [])))}",
        f"- qwen ok sheets: {len([item for item in qwen_manifest.get('results', []) if item.get('ok')])}",
        f"- qwen failed sheets: {len([item for item in qwen_manifest.get('results', []) if not item.get('ok')])}",
        f"- qwen full-page ok: {bool(qwen_full_manifest.get('result', {}).get('ok'))}",
        f"- qwen full-page components: {asset_manifest.get('summary', {}).get('qwenFullComponentCount', 0)}",
    ]
    if metrics:
        lines.extend(
            [
                "",
                "## Visual Diff",
                "",
                f"- rendered screenshot: `{rel(rendered_path, paths.root)}`",
                f"- diff image: `{rel(paths.diff_png, paths.root)}`",
                f"- mae: {metrics['mae']}",
                f"- psnr: {metrics['psnr']}",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## Visual Diff",
                "",
                "- skipped: install optional Playwright support or pass `--rendered rendered.png` to compare a browser screenshot.",
            ]
        )
    paths.report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = {
        "schema": "html_first_report_result.v1",
        "createdAt": now_iso(),
        "path": rel(paths.report_md, paths.root),
        "metrics": metrics,
    }
    write_json(paths.root / "report_result.json", result)
    return result


def image_diff(source: Path, rendered: Path, diff_path: Path) -> dict[str, Any]:
    original = Image.open(source).convert("RGB")
    candidate = Image.open(rendered).convert("RGB")
    if candidate.size != original.size:
        candidate = candidate.resize(original.size, Image.Resampling.LANCZOS)
    diff = ImageChops.difference(original, candidate)
    diff.save(diff_path)
    stat = ImageStat.Stat(diff)
    mae = sum(stat.mean) / len(stat.mean)
    mse = sum(value * value for value in stat.rms) / len(stat.rms)
    psnr = "inf" if mse == 0 else round(20 * math.log10(255 / math.sqrt(mse)), 2)
    return {"mae": round(mae, 3), "psnr": psnr}


def _try_render_with_playwright(paths: RunPaths) -> Path | None:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None

    run = read_json(paths.run_json)
    width = int(run["source"]["width"])
    height = int(run["source"]["height"])
    screenshot_path = paths.root / "preview-rendered.png"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
            page.goto(paths.preview_html.resolve().as_uri())
            page.screenshot(path=str(screenshot_path), full_page=True)
            browser.close()
    except Exception:
        return None
    return screenshot_path
