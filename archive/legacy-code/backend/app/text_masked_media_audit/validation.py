from __future__ import annotations

from pathlib import Path

from ..png_tools import read_png_metadata
from ..visual_primitive_graph import bbox_in_bounds
from .types import TextMaskedMediaAuditDocument


def validate_text_masked_media_audit(document: TextMaskedMediaAuditDocument, output_dir: Path, width: int, height: int) -> None:
    if document.schema_name != "M2902TextMaskedMediaAuditDocument" or document.schema_version != "0.1":
        raise ValueError("invalid M29.0.2 document schema")
    seen: set[str] = set()
    for item in document.media_evidence:
        if item.id in seen:
            raise ValueError(f"duplicate M29.0.2 evidence id: {item.id}")
        seen.add(item.id)
        if not bbox_in_bounds(item.bbox, width, height):
            raise ValueError(f"M29.0.2 evidence bbox out of bounds: {item.id}")
        if item.asset_path is not None:
            assert_readable_relative_png(output_dir, item.asset_path)
    for path in document.debug.to_dict().values():
        assert_readable_relative_png(output_dir, path)

def assert_readable_relative_png(output_dir: Path, path: str) -> None:
    resolved = output_dir / path
    if not resolved.exists() or read_png_metadata(resolved.read_bytes()) is None:
        raise ValueError(f"M29.0.2 PNG output missing or unreadable: {path}")
