from __future__ import annotations

from pathlib import Path

from ..png_tools import read_png_metadata
from ..visual_primitive_graph import bbox_in_bounds
from .types import VisualEvidenceDocument


def validate_visual_evidence_document(
    document: VisualEvidenceDocument,
    output_dir: Path,
    width: int,
    height: int,
    *,
    expected_count: int,
) -> None:
    if document.schema_name != "M2903VisualEvidenceDocument" or document.schema_version != "0.1":
        raise ValueError("invalid M29.0.3 document schema")
    if len(document.items) != expected_count:
        raise ValueError("M29.0.3 item count must match M29.0.2 mediaEvidence count")
    ids: set[str] = set()
    source_ids: set[str] = set()
    for item in document.items:
        if item.id in ids:
            raise ValueError(f"duplicate M29.0.3 item id: {item.id}")
        ids.add(item.id)
        if item.source_evidence_id in source_ids:
            raise ValueError(f"duplicate M29.0.2 source evidence id: {item.source_evidence_id}")
        source_ids.add(item.source_evidence_id)
        if not bbox_in_bounds(item.bbox, width, height):
            raise ValueError(f"M29.0.3 item bbox out of bounds: {item.id}")
        assert_readable_relative_png(output_dir, item.asset_path)
    for path in document.debug.to_dict().values():
        assert_readable_relative_png(output_dir, path)

def assert_readable_relative_png(output_dir: Path, path: str) -> None:
    resolved = output_dir / path
    if not resolved.exists() or read_png_metadata(resolved.read_bytes()) is None:
        raise ValueError(f"M29.0.3 PNG output missing or unreadable: {path}")
