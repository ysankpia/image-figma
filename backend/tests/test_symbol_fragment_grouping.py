from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.png_tools import PngPixels, encode_rgb_png, read_png_metadata
from app.symbol_fragment_grouping import (
    M291Options,
    extract_m291_symbol_fragment_grouping,
)
from app.visual_primitive_graph import M29PrimitiveMetrics, metrics_to_dict


def test_requires_m29_0_1_blocked_evidence(tmp_path: Path) -> None:
    document = make_m29_document([symbol("symbol_001", [10, 10, 8, 8])])
    document["meta"].pop("blockedEvidenceVersion")

    with pytest.raises(ValueError, match="blockedEvidenceVersion"):
        run_grouping(document, tmp_path, make_canvas(40, 40, (255, 255, 255)))


def test_eligible_blocked_and_hard_blocked_reasons(tmp_path: Path) -> None:
    canvas = make_canvas(80, 80, (255, 255, 255))
    document = make_m29_document(
        [symbol("symbol_001", [20, 20, 8, 8])],
        blocked=[
            blocked("blocked_001", [31, 20, 5, 5], ["weak_symbol_metrics"]),
            blocked("blocked_002", [42, 20, 5, 5], ["inside_image_primitive", "image_internal_texture"]),
        ],
    )

    result = run_grouping(document, tmp_path, canvas)

    ids = {candidate.source_node_id for candidate in result.candidates}
    assert "symbol_001" in ids
    assert "blocked_001" in ids
    assert "blocked_002" not in ids


def test_search_circle_and_handle_group(tmp_path: Path) -> None:
    canvas = make_canvas(80, 80, (255, 255, 255))
    document = make_m29_document(
        [
            symbol("symbol_circle", [20, 20, 14, 14]),
        ],
        blocked=[blocked("blocked_handle", [33, 33, 8, 3], ["weak_symbol_metrics"])],
    )

    result = run_grouping(document, tmp_path, canvas)

    assert any(group.decision == "accepted" and group.group_type == "grouped_symbol" for group in result.groups)
    assert any((tmp_path / (group.asset_path or "")).exists() for group in result.groups if group.decision == "accepted")


def test_cart_body_and_wheels_group(tmp_path: Path) -> None:
    canvas = make_canvas(100, 80, (255, 255, 255))
    document = make_m29_document(
        [
            symbol("cart_body", [20, 20, 24, 12]),
        ],
        blocked=[
            blocked("wheel_left", [23, 35, 5, 5], ["weak_symbol_metrics"]),
            blocked("wheel_right", [38, 35, 5, 5], ["weak_symbol_metrics"]),
        ],
    )

    result = run_grouping(document, tmp_path, canvas)
    accepted = [group for group in result.groups if group.decision == "accepted" and group.group_type == "grouped_symbol"]

    assert accepted
    assert len(accepted[0].members) == 3


def test_location_outer_and_center_group(tmp_path: Path) -> None:
    canvas = make_canvas(80, 80, (255, 255, 255))
    document = make_m29_document(
        [
            symbol("location_outer", [20, 20, 18, 22]),
        ],
        blocked=[blocked("location_dot", [27, 28, 5, 5], ["symbol_area_too_small"])],
    )

    result = run_grouping(document, tmp_path, canvas)

    assert any(group.decision == "accepted" for group in result.groups)


def test_icon_button_group_preserves_member_roles(tmp_path: Path) -> None:
    canvas = make_canvas(100, 100, (255, 255, 255))
    document = make_m29_document(
        [
            shape("shape_button", [20, 20, 36, 36], "badge_background"),
            symbol("symbol_plus_h", [30, 36, 16, 4]),
            symbol("symbol_plus_v", [36, 30, 4, 16]),
        ],
    )

    result = run_grouping(document, tmp_path, canvas)
    groups = [group for group in result.groups if group.group_type == "icon_button_group"]

    assert groups
    roles = {member.role for member in groups[0].members}
    assert {"button_background", "foreground_symbol"} <= roles


def test_neighbor_tab_icons_do_not_merge(tmp_path: Path) -> None:
    canvas = make_canvas(120, 80, (255, 255, 255))
    document = make_m29_document(
        [
            symbol("tab_1_a", [20, 20, 8, 8]),
            symbol("tab_1_b", [29, 20, 8, 8]),
            symbol("tab_2_a", [78, 20, 8, 8]),
            symbol("tab_2_b", [87, 20, 8, 8]),
        ]
    )

    result = run_grouping(document, tmp_path, canvas)

    assert all(group.bbox[2] < 40 for group in result.groups)


def test_text_like_sequence_rejected(tmp_path: Path) -> None:
    canvas = make_canvas(120, 50, (255, 255, 255))
    document = make_m29_document(
        [
            symbol("glyph_1", [10, 20, 8, 10]),
            symbol("glyph_2", [24, 20, 8, 10]),
            symbol("glyph_3", [38, 20, 8, 10]),
            symbol("glyph_4", [52, 20, 8, 10]),
        ]
    )

    result = run_grouping(document, tmp_path, canvas, M291Options(neighbor_search_radius=18))

    assert any("text_like_sequence" in group.reasons and group.decision == "rejected" for group in result.groups)


def test_image_internal_texture_does_not_enter_graph(tmp_path: Path) -> None:
    canvas = make_canvas(80, 80, (255, 255, 255))
    document = make_m29_document(
        [symbol("symbol_001", [8, 8, 8, 8])],
        blocked=[blocked("image_texture", [12, 12, 8, 8], ["inside_image_primitive", "image_internal_texture"])],
    )

    result = run_grouping(document, tmp_path, canvas)

    assert "image_texture" not in {candidate.source_node_id for candidate in result.candidates}


def test_outputs_and_audits_are_written(tmp_path: Path) -> None:
    canvas = make_canvas(80, 80, (255, 255, 255))
    document = make_m29_document([symbol("symbol_001", [20, 20, 8, 8])], blocked=[blocked("blocked_001", [30, 20, 6, 6], ["weak_symbol_metrics"])])

    result = run_grouping(document, tmp_path, canvas)

    assert (tmp_path / "group_nodes.json").exists()
    assert (tmp_path / "symbol_asset_audit.json").exists()
    assert (tmp_path / "edge_audit.json").exists()
    assert read_png_metadata((tmp_path / "overlays" / "09_symbol_fragment_risks.png").read_bytes()) is not None
    assert read_png_metadata((tmp_path / "overlays" / "10_symbol_groups.png").read_bytes()) is not None
    assert read_png_metadata((tmp_path / "overlays" / "11_grouped_vs_original.png").read_bytes()) is not None
    assert result.edge_audit
    assert any(edge.decision in {"accepted", "weak", "rejected"} for edge in result.edge_audit)


def test_preview_sheet_retains_parent_m29_image_assets(tmp_path: Path) -> None:
    m29_output = tmp_path / "m29_output"
    m291_output = m29_output / "m29_1"
    (m29_output / "assets" / "images").mkdir(parents=True)
    canvas = make_canvas(96, 80, (255, 255, 255))
    draw_rect(canvas, 8, 8, 36, 24, (20, 120, 60))
    (m29_output / "assets" / "images" / "image_001.png").write_bytes(encode_rgb_png(canvas.width, canvas.height, canvas.rows))
    document = make_m29_document([symbol("symbol_001", [20, 44, 8, 8])], blocked=[blocked("blocked_001", [30, 44, 6, 6], ["weak_symbol_metrics"])])

    result = run_grouping(document, m291_output, canvas)

    preview = read_png_metadata((m291_output / "preview_sheet.png").read_bytes())
    assert preview is not None
    assert preview.height > 180
    assert result.meta["counts"]["acceptedGroups"] >= 1


def run_grouping(document: dict, output_dir: Path, canvas: PngPixels, options: M291Options | None = None):
    output_dir.mkdir(parents=True, exist_ok=True)
    source_path = output_dir / "source.png"
    png = encode_rgb_png(canvas.width, canvas.height, canvas.rows)
    source_path.write_bytes(png)
    nodes_path = output_dir / "nodes.json"
    nodes_path.write_text(json.dumps(document), encoding="utf-8")
    return extract_m291_symbol_fragment_grouping(
        m29_document=document,
        m29_nodes_json_path=str(nodes_path),
        png_data=png,
        source_image=str(source_path),
        output_dir=output_dir,
        options=options,
    )


def make_m29_document(nodes: list[dict], blocked: list[dict] | None = None) -> dict:
    return {
        "version": "0.1",
        "sourceImage": "synthetic.png",
        "imageSize": {"width": 120, "height": 120},
        "nodes": nodes,
        "relations": [],
        "blocked": blocked or [],
        "debug": {},
        "warnings": [],
        "meta": {
            "blockedEvidenceVersion": "0.2",
            "options": {"symbol_min_area": 16, "symbol_max_area": 12000},
        },
    }


def symbol(id: str, bbox: list[int], metrics: M29PrimitiveMetrics | None = None) -> dict:
    metrics = metrics or M29PrimitiveMetrics(2, 0.05, 0.05, 0.6, bbox[2] / max(1, bbox[3]), 40, (40, 40, 40))
    return {
        "id": id,
        "type": "symbol",
        "subtype": "icon_candidate",
        "bbox": bbox,
        "confidence": 0.8,
        "source": "test",
        "sourceOrder": 0,
        "layerHint": "content",
        "reasons": ["test"],
        "metrics": metrics_to_dict(metrics),
    }


def blocked(id: str, bbox: list[int], reasons: list[str], metrics: M29PrimitiveMetrics | None = None) -> dict:
    metrics = metrics or M29PrimitiveMetrics(28, 0.22, 0.18, 0.5, bbox[2] / max(1, bbox[3]), 50, (50, 50, 50))
    return {
        "id": id,
        "bbox": bbox,
        "source": "test",
        "reasons": reasons,
        "metrics": metrics_to_dict(metrics),
        "context": {
            "area": bbox_area(bbox),
            "maxEdge": max(bbox[2], bbox[3]),
            "textOverlapRatio": 0.0,
            "imageOverlapRatio": 0.0,
            "protectiveShapeOverlapRatio": 0.0,
            "insideImage": False,
            "nearImage": False,
            "nearProtectiveShape": False,
            "nearestShapeId": None,
        },
    }


def shape(id: str, bbox: list[int], subtype: str) -> dict:
    return {
        "id": id,
        "type": "shape",
        "subtype": subtype,
        "bbox": bbox,
        "confidence": 0.8,
        "source": "test",
        "sourceOrder": 0,
        "layerHint": "overlay",
        "reasons": ["test"],
        "metrics": metrics_to_dict(M29PrimitiveMetrics(1, 0.0, 0.0, 0.8, bbox[2] / max(1, bbox[3]), 220, (220, 20, 20))),
    }


def bbox_area(bbox: list[int]) -> int:
    return bbox[2] * bbox[3]


def make_canvas(width: int, height: int, fill: tuple[int, int, int]) -> PngPixels:
    return PngPixels(width=width, height=height, rows=[bytes(fill) * width for _ in range(height)])


def draw_rect(canvas: PngPixels, x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> None:
    rows = [bytearray(row) for row in canvas.rows]
    color_bytes = bytes(color)
    for row_index in range(y, min(canvas.height, y + height)):
        for column in range(x, min(canvas.width, x + width)):
            rows[row_index][column * 3 : column * 3 + 3] = color_bytes
    canvas.rows[:] = [bytes(row) for row in rows]
