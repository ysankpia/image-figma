from __future__ import annotations

import html
from typing import Any

from .geometry import BBox
from .io import now_iso, read_json, rel, write_json
from .paths import RunPaths


def build_html(paths: RunPaths, force: bool = False) -> dict[str, Any]:
    if paths.preview_html.exists() and not force:
        return {"path": rel(paths.preview_html, paths.root), "cached": True}

    run = read_json(paths.run_json)
    manifest = read_json(paths.asset_manifest_json)
    width = int(run["source"]["width"])
    height = int(run["source"]["height"])
    primary_assets = [asset for asset in manifest["assets"] if asset.get("primary")]

    body = "\n".join(_asset_img(asset) for asset in primary_assets)
    css_blocks = _scaffold_css(width, height)
    content = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HTML-first UI Rebuilder Preview</title>
  <style>
{css_blocks}
  </style>
</head>
<body>
  <main class="page" aria-label="reconstructed screenshot">
    <div class="status-bar"></div>
    <div class="top-title"></div>
    <div class="search-row">
      <div class="search-pill"></div>
      <div class="order-pill"></div>
    </div>
    <div class="soft-card category-card"></div>
    <div class="soft-card list-card"></div>
    <div class="notice-strip"></div>
{body}
  </main>
</body>
</html>
"""
    paths.preview_html.write_text(content, encoding="utf-8")
    result = {
        "schema": "html_first_preview_result.v1",
        "createdAt": now_iso(),
        "path": rel(paths.preview_html, paths.root),
        "primaryAssetCount": len(primary_assets),
    }
    write_json(paths.root / "html_result.json", result)
    return result


def _asset_img(asset: dict[str, Any]) -> str:
    bbox = BBox.from_dict(asset["bboxOnPage"])
    src = html.escape(asset["path"], quote=True)
    alt = html.escape(asset["id"], quote=True)
    return (
        f'    <img class="asset asset-{html.escape(asset["roiId"], quote=True)}" '
        f'src="{src}" alt="{alt}" '
        f'style="left:{bbox.x}px;top:{bbox.y}px;width:{bbox.width}px;height:{bbox.height}px;">'
    )


def _scaffold_css(width: int, height: int) -> str:
    radius = max(18, round(width * 0.035))
    return f"""    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: start center;
      background: #e9edf3;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    .page {{
      position: relative;
      width: {width}px;
      height: {height}px;
      overflow: hidden;
      background:
        linear-gradient(180deg, #eaf6ff 0%, #9bddff 32%, #f8f8fb 47%, #ffffff 100%);
    }}
    .asset {{
      position: absolute;
      display: block;
      object-fit: contain;
      z-index: 5;
    }}
    .status-bar {{
      position: absolute;
      left: 0;
      top: 0;
      width: 100%;
      height: {round(height * 0.052)}px;
      background: rgba(237, 248, 255, 0.45);
      z-index: 1;
    }}
    .top-title {{
      position: absolute;
      left: {round(width * 0.32)}px;
      top: {round(height * 0.06)}px;
      width: {round(width * 0.36)}px;
      height: {round(height * 0.035)}px;
      border-radius: 999px;
      background: rgba(20, 23, 31, 0.10);
      z-index: 1;
    }}
    .search-row {{
      position: absolute;
      left: {round(width * 0.035)}px;
      top: {round(height * 0.10)}px;
      width: {round(width * 0.93)}px;
      height: {round(height * 0.055)}px;
      display: grid;
      grid-template-columns: 1fr {round(width * 0.25)}px;
      gap: {round(width * 0.04)}px;
      z-index: 1;
    }}
    .search-pill,
    .order-pill {{
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.76);
      box-shadow: 0 8px 24px rgba(60, 128, 170, 0.12);
    }}
    .soft-card {{
      position: absolute;
      left: {round(width * 0.035)}px;
      width: {round(width * 0.93)}px;
      border-radius: {radius}px;
      background: rgba(255, 255, 255, 0.92);
      box-shadow: 0 10px 24px rgba(64, 71, 94, 0.10);
      z-index: 0;
    }}
    .category-card {{
      top: {round(height * 0.325)}px;
      height: {round(height * 0.105)}px;
    }}
    .list-card {{
      top: {round(height * 0.475)}px;
      height: {round(height * 0.29)}px;
    }}
    .notice-strip {{
      position: absolute;
      left: {round(width * 0.035)}px;
      top: {round(height * 0.855)}px;
      width: {round(width * 0.93)}px;
      height: {round(height * 0.045)}px;
      border-radius: {round(radius * 0.6)}px;
      background: rgba(255, 248, 222, 0.95);
      z-index: 0;
    }}
"""
