from __future__ import annotations

from pathlib import Path
from typing import Any

from ..png_tools import read_png_metadata
from ..visual_primitive_graph import bbox_in_bounds
from .geometry import assert_unique
from .types import M2905Document


def validate_text_aware_visual_object_refinement_document(
    document: M2905Document,
    output_dir: Path,
    width: int,
    height: int,
    m2904_document: dict[str, Any],
    m2902_document: dict[str, Any],
    *,
    require_preview_artifacts: bool = True,
) -> None:
    if document.schema_name != "M2905TextAwareVisualObjectRefinementDocument" or document.schema_version != "0.1":
        raise ValueError("invalid M29.0.5 document schema")
    source_objects = {str(item.get("id")): item for item in m2904_document.get("objects", []) if isinstance(item, dict) and item.get("id")}
    source_nodes = {str(item.get("id")) for item in m2904_document.get("evidenceNodes", []) if isinstance(item, dict) and item.get("id")}
    source_text_boxes = {str(item.get("id")) for item in m2902_document.get("textBoxes", []) if isinstance(item, dict) and item.get("id")}
    object_ids = assert_unique([item.id for item in document.objects], "object")
    visual_asset_ids = assert_unique([item.id for item in document.visual_assets], "visual asset")
    shape_ids = assert_unique([item.id for item in document.shape_candidates], "shape candidate")
    text_ids = assert_unique([item.id for item in document.text_members], "text member")
    unresolved_ids = assert_unique([item.id for item in document.unresolved_members], "unresolved member")
    audit_ids = assert_unique([item.id for item in document.audit], "audit item")
    _ = audit_ids
    source_object_ids = [item.source_object_id for item in document.objects]
    if set(source_object_ids) != set(source_objects):
        raise ValueError("M29.0.5 must refine exactly the M29.0.4 source objects")
    assert_unique(source_object_ids, "source object reference")
    for item in document.objects:
        if item.source_object_id not in source_objects:
            raise ValueError(f"M29.0.5 object references missing source object: {item.id}")
        if item.combined_asset_use != "audit_only":
            raise ValueError(f"M29.0.5 combinedAssetUse must be audit_only: {item.id}")
        if not bbox_in_bounds(item.bbox, width, height):
            raise ValueError(f"M29.0.5 object bbox out of bounds: {item.id}")
        assert_png_size(output_dir, item.combined_asset_path, item.bbox)
        if item.decision == "text_only" and item.visual_asset_ids:
            raise ValueError(f"M29.0.5 text_only object cannot have visual assets: {item.id}")
        if item.decision == "visual_only" and item.text_member_ids:
            raise ValueError(f"M29.0.5 visual_only object cannot have text members: {item.id}")
        if item.decision == "separated" and (not item.visual_asset_ids or not item.text_member_ids):
            raise ValueError(f"M29.0.5 separated object requires visual and text members: {item.id}")
        if item.decision == "split_needed" and item.visual_asset_ids:
            raise ValueError(f"M29.0.5 split_needed object cannot have child visual assets: {item.id}")
        for asset_id in item.visual_asset_ids:
            if asset_id not in visual_asset_ids:
                raise ValueError(f"M29.0.5 object references missing visual asset: {item.id}")
        for shape_id in item.shape_candidate_ids:
            if shape_id not in shape_ids:
                raise ValueError(f"M29.0.5 object references missing shape candidate: {item.id}")
        for text_id in item.text_member_ids:
            if text_id not in text_ids:
                raise ValueError(f"M29.0.5 object references missing text member: {item.id}")
        for unresolved_id in item.unresolved_member_ids:
            if unresolved_id not in unresolved_ids:
                raise ValueError(f"M29.0.5 object references missing unresolved member: {item.id}")
    for item in document.visual_assets:
        if item.source_object_id not in source_objects:
            raise ValueError(f"M29.0.5 visual asset references missing source object: {item.id}")
        if item.asset_use not in {"image_asset", "icon_asset"}:
            raise ValueError(f"M29.0.5 formal visual asset has invalid assetUse: {item.id}")
        if not item.asset_path or not item.asset_path.startswith("assets/visual_assets/"):
            raise ValueError(f"M29.0.5 visual asset must live under assets/visual_assets: {item.id}")
        if not bbox_in_bounds(item.bbox, width, height):
            raise ValueError(f"M29.0.5 visual asset bbox out of bounds: {item.id}")
        assert_png_size(output_dir, item.asset_path, item.bbox)
        for node_id in item.source_evidence_node_ids:
            if node_id not in source_nodes:
                raise ValueError(f"M29.0.5 visual asset references missing evidence node: {item.id}")
    for item in document.shape_candidates:
        if item.asset_use != "shape_candidate":
            raise ValueError(f"M29.0.5 shape candidate assetUse must be shape_candidate: {item.id}")
        if item.preview_asset_path and item.preview_asset_path.startswith("assets/visual_assets/"):
            raise ValueError(f"M29.0.5 shape candidate cannot live under visual_assets: {item.id}")
        if not bbox_in_bounds(item.bbox, width, height):
            raise ValueError(f"M29.0.5 shape candidate bbox out of bounds: {item.id}")
        if item.preview_asset_path:
            assert_png_size(output_dir, item.preview_asset_path, item.bbox)
        for node_id in item.source_evidence_node_ids:
            if node_id not in source_nodes:
                raise ValueError(f"M29.0.5 shape candidate references missing evidence node: {item.id}")
    for item in document.text_members:
        if not item.text_preview:
            raise ValueError(f"M29.0.5 textPreview is required: {item.id}")
        if item.source_evidence_node_id and item.source_evidence_node_id not in source_nodes:
            raise ValueError(f"M29.0.5 text member references missing evidence node: {item.id}")
        if item.source_text_box_id and item.source_text_box_id not in source_text_boxes:
            raise ValueError(f"M29.0.5 text member references missing text box: {item.id}")
        if not item.source_evidence_node_id and not item.source_text_box_id:
            raise ValueError(f"M29.0.5 text member requires source ref: {item.id}")
        if not bbox_in_bounds(item.bbox, width, height):
            raise ValueError(f"M29.0.5 text member bbox out of bounds: {item.id}")
        if item.preview_asset_path:
            assert_png_size(output_dir, item.preview_asset_path, item.bbox)
    for item in document.unresolved_members:
        if item.source_evidence_node_id and item.source_evidence_node_id not in source_nodes:
            raise ValueError(f"M29.0.5 unresolved member references missing evidence node: {item.id}")
        if not bbox_in_bounds(item.bbox, width, height):
            raise ValueError(f"M29.0.5 unresolved member bbox out of bounds: {item.id}")
    audited = {item.refined_object_id for item in document.audit}
    if audited != object_ids:
        raise ValueError("M29.0.5 audit must cover all refined objects")
    for item in document.audit:
        if item.source_object_id not in source_objects:
            raise ValueError(f"M29.0.5 audit references missing source object: {item.id}")
    for path in document.debug.to_dict().values():
        metadata = assert_readable_png(output_dir, path)
        if metadata.width != width or metadata.height != height:
            raise ValueError(f"M29.0.5 overlay dimensions do not match source image: {path}")
    if require_preview_artifacts:
        assert_readable_png(output_dir, "preview_text_aware_refinement.png")

def assert_png_size(output_dir: Path, path: str, bbox: list[int]) -> None:
    metadata = assert_readable_png(output_dir, path)
    if metadata.width != bbox[2] or metadata.height != bbox[3]:
        raise ValueError(f"M29.0.5 asset dimensions do not match bbox: {path}")

def assert_readable_png(output_dir: Path, path: str):
    resolved = output_dir / path
    if not resolved.exists():
        raise ValueError(f"M29.0.5 PNG output missing or unreadable: {path}")
    metadata = read_png_metadata(resolved.read_bytes())
    if metadata is None:
        raise ValueError(f"M29.0.5 PNG output missing or unreadable: {path}")
    return metadata
