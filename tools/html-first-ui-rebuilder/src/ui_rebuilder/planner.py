from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from .geometry import BBox
from .io import copy_source_image, now_iso, read_json, rel, sha256_file, write_json
from .paths import RunPaths


def initialize_run(input_image: Path, out_dir: Path, force: bool = False) -> RunPaths:
    source = input_image.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(source)

    paths = RunPaths(out_dir.expanduser().resolve())
    paths.ensure()
    if paths.run_json.exists() and not force:
        return paths

    local_source = copy_source_image(source, paths.source_dir)
    with Image.open(local_source) as image:
        width, height = image.size

    run = {
        "schema": "html_first_ui_rebuilder_run.v1",
        "createdAt": now_iso(),
        "source": {
            "inputPath": str(source),
            "localPath": rel(local_source, paths.root),
            "sha256": sha256_file(local_source),
            "width": width,
            "height": height,
        },
    }
    write_json(paths.run_json, run)
    return paths


def create_asset_plan(paths: RunPaths, force: bool = False) -> dict[str, Any]:
    if paths.asset_plan_json.exists() and not force:
        return read_json(paths.asset_plan_json)

    run = read_json(paths.run_json)
    width = int(run["source"]["width"])
    height = int(run["source"]["height"])
    rois = _mobile_ui_rois(width, height)

    plan = {
        "schema": "html_first_asset_plan.v1",
        "createdAt": now_iso(),
        "planner": "heuristic_mobile_ui_v1",
        "source": run["source"],
        "rois": rois,
        "reconstructable": [
            {
                "id": "page_background",
                "kind": "css_background",
                "reason": "Use CSS gradient and flat surfaces; do not send the full screenshot to Qwen.",
            },
            {
                "id": "text_and_controls",
                "kind": "html_css",
                "reason": "Editable text, cards, buttons, and layout should be rebuilt as DOM/CSS when a visual plan is available.",
            },
        ],
        "notes": [
            "This is a draft plan. A vision-capable Codex/GPT pass should edit asset_plan.json before make-sheets for production work.",
            "Do not draw boxes onto the source image. Only this JSON carries ROI metadata.",
        ],
    }
    write_json(paths.asset_plan_json, plan)
    return plan


def _roi(
    roi_id: str,
    label: str,
    kind: str,
    bbox: BBox,
    width: int,
    height: int,
    reason: str,
    priority: int,
) -> dict[str, Any]:
    clamped = bbox.clamp(width, height)
    return {
        "id": roi_id,
        "label": label,
        "kind": kind,
        "bbox": clamped.to_dict(),
        "requiresRasterAsset": True,
        "priority": priority,
        "reason": reason,
    }


def _mobile_ui_rois(width: int, height: int) -> list[dict[str, Any]]:
    rois = [
        _roi(
            "top_chrome",
            "Status and app title chrome",
            "chrome",
            BBox(0, 0, width, round(height * 0.10)),
            width,
            height,
            "Fallback crop for status/title chrome until OCR/HTML reconstruction owns it.",
            30,
        ),
        _roi(
            "hero_visual",
            "Hero visual / carousel artwork",
            "hero",
            BBox(0, round(height * 0.10), width, round(height * 0.22)),
            width,
            height,
            "Large illustrated/banner area usually contains non-rebuildable artwork.",
            100,
        ),
        _roi(
            "category_strip",
            "Category icons strip",
            "icon_strip",
            BBox(round(width * 0.02), round(height * 0.325), round(width * 0.96), round(height * 0.11)),
            width,
            height,
            "Icon row usually contains complex app icons and soft shadows.",
            80,
        ),
        _roi(
            "recommendation_list",
            "Recommendation list visual assets",
            "list_assets",
            BBox(round(width * 0.02), round(height * 0.46), round(width * 0.96), round(height * 0.32)),
            width,
            height,
            "List rows often contain avatars, badges, and iconography that should be extracted.",
            70,
        ),
        _roi(
            "trust_badges",
            "Trust / feature badges",
            "badge_strip",
            BBox(round(width * 0.02), round(height * 0.79), round(width * 0.96), round(height * 0.09)),
            width,
            height,
            "Badges and small icons are better preserved as raster assets in v1.",
            50,
        ),
        _roi(
            "bottom_nav_icons",
            "Bottom navigation icons",
            "nav_icons",
            BBox(0, round(height * 0.90), width, round(height * 0.07)),
            width,
            height,
            "Navigation icons are small visual assets; text can later become DOM.",
            40,
        ),
    ]
    return [roi for roi in rois if BBox.from_dict(roi["bbox"]).area() > 0]


def source_image_path(paths: RunPaths) -> Path:
    run = read_json(paths.run_json)
    return paths.root / run["source"]["localPath"]
