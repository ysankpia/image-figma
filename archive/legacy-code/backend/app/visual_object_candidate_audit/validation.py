from __future__ import annotations

from pathlib import Path

from ..png_tools import read_png_metadata
from ..visual_primitive_graph import bbox_in_bounds
from .geometry import assert_unique
from .types import M2904Document


def validate_visual_object_candidate_audit_document(
    document: M2904Document,
    output_dir: Path,
    width: int,
    height: int,
    *,
    require_preview_artifacts: bool = True,
) -> None:
    if document.schema_name != "M2904GenericVisualObjectCandidateAuditDocument" or document.schema_version != "0.1":
        raise ValueError("invalid M29.0.4 document schema")
    node_ids = assert_unique([node.id for node in document.evidence_nodes], "evidence node")
    edge_ids = assert_unique([edge.id for edge in document.evidence_edges], "evidence edge")
    object_ids = assert_unique([item.id for item in document.objects], "object")
    assert_unique([item.id for item in document.sets], "set")
    for node in document.evidence_nodes:
        if not bbox_in_bounds(node.bbox, width, height):
            raise ValueError(f"M29.0.4 evidence node bbox out of bounds: {node.id}")
        if node.source not in {"m2903_visual_evidence", "m2902_text_box"}:
            raise ValueError(f"M29.0.4 illegal candidate source: {node.source}")
    for edge in document.evidence_edges:
        if edge.left_id not in node_ids or edge.right_id not in node_ids:
            raise ValueError(f"M29.0.4 edge references missing node: {edge.id}")
    for item in document.objects:
        if not bbox_in_bounds(item.bbox, width, height):
            raise ValueError(f"M29.0.4 object bbox out of bounds: {item.id}")
        for member in item.members:
            if member.evidence_node_id not in node_ids:
                raise ValueError(f"M29.0.4 object member references missing node: {item.id}")
        for edge_id in item.edge_ids:
            if edge_id not in edge_ids:
                raise ValueError(f"M29.0.4 object references missing edge: {item.id}")
        if item.asset_path is not None:
            metadata = assert_readable_relative_png(output_dir, item.asset_path)
            if metadata.width != item.bbox[2] or metadata.height != item.bbox[3]:
                raise ValueError(f"M29.0.4 object asset dimensions do not match bbox: {item.id}")
    for item in document.sets:
        for object_id in item.member_object_ids:
            if object_id not in object_ids:
                raise ValueError(f"M29.0.4 set references missing object: {item.id}")
            if next(obj for obj in document.objects if obj.id == object_id).decision == "rejected" and item.decision != "rejected":
                raise ValueError(f"M29.0.4 set references rejected object: {item.id}")
        for edge_id in item.edge_ids:
            if edge_id not in edge_ids:
                raise ValueError(f"M29.0.4 set references missing edge: {item.id}")
    audited = {item.edge_id for item in document.edge_audit}
    if audited != edge_ids:
        raise ValueError("M29.0.4 edgeAudit must cover all evidenceEdges")
    for path in document.debug.to_dict().values():
        metadata = assert_readable_relative_png(output_dir, path)
        if metadata.width != width or metadata.height != height:
            raise ValueError(f"M29.0.4 overlay dimensions do not match source image: {path}")
    if require_preview_artifacts:
        assert_readable_relative_png(output_dir, "preview_visual_objects.png")

def assert_readable_relative_png(output_dir: Path, path: str):
    resolved = output_dir / path
    if not resolved.exists():
        raise ValueError(f"M29.0.4 PNG output missing or unreadable: {path}")
    metadata = read_png_metadata(resolved.read_bytes())
    if metadata is None:
        raise ValueError(f"M29.0.4 PNG output missing or unreadable: {path}")
    return metadata
