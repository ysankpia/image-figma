from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..png_tools import PngMetadata
from ..state import state


def publish_m29_assets(task_id: str, m29_dir: Path, dsl: dict[str, Any], image: PngMetadata) -> None:
    publish_variant_assets(task_id, "m29", m29_dir, dsl, image)


def publish_variant_assets(task_id: str, variant: str, source_dir: Path, dsl: dict[str, Any], image: PngMetadata) -> None:
    public_dir = state.storage.assets_dir / task_id / variant
    public_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat()
    seen_names: set[str] = set()
    for asset in dsl.get("assets", []):
        if not isinstance(asset, dict):
            continue
        url = str(asset.get("url") or "")
        if not url or url.startswith(("http://", "https://")):
            continue
        source = resolve_materialized_asset_path(source_dir, url)
        if source is None or not source.exists():
            continue
        filename = unique_filename(source.name, seen_names)
        target = public_dir / filename
        shutil.copy2(source, target)
        asset["url"] = variant_asset_url(task_id, variant, filename)
        asset["storage"] = "local"
        state.database.insert_asset(
            {
                "asset_id": str(asset.get("assetId") or filename),
                "task_id": task_id,
                "role": str(asset.get("role") or "m29_asset"),
                "path": str(target),
                "url": asset["url"],
                "mime_type": "image/png",
                "width": int(asset.get("width") or image.width),
                "height": int(asset.get("height") or image.height),
                "created_at": now,
            }
        )


def variant_asset_url(task_id: str, variant: str, filename: str) -> str:
    return f"{state.storage.public_base_url}/files/assets/{task_id}/{variant}/{filename}"


def resolve_materialized_asset_path(source_dir: Path, url: str) -> Path | None:
    candidate = Path(url)
    if candidate.is_absolute():
        return candidate
    try:
        return (source_dir / candidate).resolve()
    except OSError:
        return None


def unique_filename(filename: str, seen: set[str]) -> str:
    clean = "".join(char if char.isalnum() or char in "._-" else "_" for char in filename) or "asset.png"
    stem = Path(clean).stem or "asset"
    suffix = Path(clean).suffix or ".png"
    candidate = f"{stem}{suffix}"
    index = 2
    while candidate in seen:
        candidate = f"{stem}_{index}{suffix}"
        index += 1
    seen.add(candidate)
    return candidate

