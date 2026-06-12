from __future__ import annotations

from pathlib import Path
from typing import Any

from ..png_tools import decode_png_pixels
from .artifacts import build_preview_sheet, write_m291_outputs, write_m291_overlays
from .assets import build_asset_audit, export_group_assets
from .candidates import collect_fragment_candidates, require_m29_0_1_document
from .edges import build_fragment_edges
from .groups import build_symbol_groups
from .icon_button import add_icon_button_groups
from .types import M291DebugArtifacts, M291Document, M291EdgeAuditItem, M291Options
from .validation import build_m291_meta, validate_m291_document


def extract_m291_symbol_fragment_grouping(
    *,
    m29_document: dict[str, Any],
    m29_nodes_json_path: str,
    png_data: bytes,
    source_image: str,
    output_dir: Path,
    options: M291Options | None = None,
    emit_debug_artifacts: bool = True,
    emit_preview_artifacts: bool = True,
) -> M291Document:
    options = options or M291Options()
    require_m29_0_1_document(m29_document)
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)

    nodes = [item for item in m29_document.get("nodes", []) if isinstance(item, dict)]
    blocked = [item for item in m29_document.get("blocked", []) if isinstance(item, dict)]
    m29_options = dict(m29_document.get("meta", {}).get("options", {}))
    candidates = collect_fragment_candidates(nodes, blocked, pixels, m29_options, options)
    edges = build_fragment_edges(candidates, nodes, pixels, options)
    groups = build_symbol_groups(candidates, edges, nodes, pixels, options)
    groups = add_icon_button_groups(groups, candidates, nodes, pixels, options)
    groups = export_group_assets(groups, pixels, output_dir)
    edge_audit = [M291EdgeAuditItem(edge.id, edge.left_id, edge.right_id, edge.decision, edge.score, edge.reasons, edge.metrics) for edge in edges]
    asset_audit = build_asset_audit(candidates, edges, groups, options)
    debug = M291DebugArtifacts()
    if emit_debug_artifacts:
        debug = write_m291_overlays(pixels, output_dir, candidates, groups, asset_audit)
    if emit_preview_artifacts and debug.to_dict():
        preview_path = output_dir / "preview_sheet.png"
        preview_path.write_bytes(build_preview_sheet(pixels, output_dir, debug, candidates, groups))
    meta = build_m291_meta(candidates, edges, groups, asset_audit)
    document = M291Document(
        schema_name="M291SymbolFragmentGroupingDocument",
        schema_version="0.1",
        source_m29_nodes_json=m29_nodes_json_path,
        source_image=source_image,
        options=options,
        candidates=candidates,
        edges=edges,
        groups=groups,
        asset_audit=asset_audit,
        edge_audit=edge_audit,
        debug=debug,
        warnings=[],
        meta=meta,
    )
    validate_m291_document(document, output_dir, pixels.width, pixels.height)
    write_m291_outputs(document, output_dir)
    return document
