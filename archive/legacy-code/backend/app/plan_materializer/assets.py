from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ..m29_materialization_utils import layout_from_bbox, next_unique_asset_id, next_unique_id
from ..png_tools import PngPixels
from ..visual_primitive_graph import crop_pixels
from .types import ReplayNode


def append_image_replay_node(
    dsl: dict[str, Any],
    children: list[dict[str, Any]],
    existing_ids: set[str],
    asset_ids: set[str],
    pixels: PngPixels,
    m29_dir: Path | None,
    output_dir: Path,
    node: dict[str, Any],
    bbox: list[int],
    replayed: list[ReplayNode],
    role: str,
    *,
    extra_meta: dict[str, Any] | None = None,
    force_crop: bool = False,
    replay_source_id: str | None = None,
    source_asset_override: Path | None = None,
) -> None:
    source_id = str(node.get("id") or f"{role}_unknown")
    replay_kind = "symbol" if role == "m29_symbol" else "image"
    replay_decision = "icon_replay" if role == "m29_symbol" else "image_replay"
    asset_dir = output_dir / "assets" / role
    asset_dir.mkdir(parents=True, exist_ok=True)
    source_asset = source_asset_override or resolve_source_asset(m29_dir, node)
    suffix = source_asset.suffix.lower() if source_asset is not None else ".png"
    copied_path = asset_dir / f"{source_id}{suffix or '.png'}"
    if source_asset is not None and source_asset.exists() and (not force_crop or source_asset_override is not None):
        shutil.copy2(source_asset, copied_path)
    else:
        copied_path.write_bytes(crop_pixels(pixels, bbox))

    asset_id = next_unique_asset_id(asset_ids, f"{role}_{len([item for item in replayed if item.kind in {'image', 'symbol'}]) + 1:04d}")
    dsl["assets"].append(
        {
            "assetId": asset_id,
            "type": "image",
            "role": role,
            "url": relative_posix(output_dir, copied_path),
            "format": "png",
            "width": bbox[2],
            "height": bbox[3],
            "storage": "local",
            "meta": {
                "m29PlanDrivenMaterialization": True,
                "sourceKind": f"m29_{node.get('type')}",
                "sourceM29NodeId": source_id,
                "sourceAssetPath": node.get("assetPath"),
                "sourceAssetOverridePath": str(source_asset_override) if source_asset_override is not None else None,
            },
        }
    )
    node_id = next_unique_id(existing_ids, f"{role}_{len(replayed) + 1:04d}")
    children.append(
        {
            "id": node_id,
            "type": "image",
            "role": role,
            "name": f"M29 {str(node.get('type') or 'Image').title()} / {source_id}",
            "layout": layout_from_bbox(bbox),
            "source": {"assetId": asset_id},
            "imageFill": {"mode": "fit"},
            "style": {"visible": True, "opacity": 1},
            "meta": {
                "m29PlanDrivenMaterialization": True,
                "sourceKind": f"m29_{node.get('type')}",
                "sourceM29NodeId": source_id,
                "sourceBBox": bbox,
                "sourceAssetPath": node.get("assetPath"),
                "sourceAssetOverridePath": str(source_asset_override) if source_asset_override is not None else None,
                "replayDecision": replay_decision,
                "replayReasons": ["m29_visual_primitive_replay"],
                **(extra_meta or {}),
            },
        }
    )
    replayed.append(
        ReplayNode(
            node_id,
            replay_kind,
            replay_source_id or source_id,
            bbox,
            role=role,
            asset_id=asset_id,
            asset_url=relative_posix(output_dir, copied_path),
            replay_decision=replay_decision,
        )
    )


def resolve_m29_dir(m29_document: dict[str, Any]) -> Path | None:
    source = str(m29_document.get("sourceM29NodesJson") or "")
    if source:
        return Path(source).expanduser().resolve().parent
    source_image = str(m29_document.get("sourceImage") or "")
    if source_image:
        return None
    return None


def resolve_source_asset(m29_dir: Path | None, node: dict[str, Any]) -> Path | None:
    asset_path = str(node.get("assetPath") or "").strip()
    if not asset_path:
        return None
    candidate = Path(asset_path).expanduser()
    if candidate.is_absolute():
        return candidate
    if m29_dir is None:
        return None
    return (m29_dir / candidate).resolve()


def relative_posix(base: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()
