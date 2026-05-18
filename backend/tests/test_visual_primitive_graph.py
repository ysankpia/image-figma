from __future__ import annotations

from pathlib import Path

from app.png_tools import PngPixels, encode_rgb_png, read_png_metadata
from app.visual_primitive_graph import (
    M29ConnectedComponent,
    M29PrimitiveMetrics,
    M29PrimitiveNode,
    M29TextBox,
    M29VisualPrimitiveOptions,
    bbox_area,
    bbox_clamp,
    bbox_contains,
    bbox_intersects,
    bbox_iou,
    bbox_x2,
    bbox_y2,
    build_text_exclusion_mask,
    connected_components,
    detect_symbols,
    extract_m29_visual_primitive_graph,
    is_protective_shape,
    mask_empty,
    mask_from_bboxes,
    mask_get,
    mask_intersects_bbox,
    mask_subtract,
    mask_to_png,
    mask_union,
    measure_region,
)


def test_bbox_utils_use_xywh_left_closed_right_open() -> None:
    bbox = [10, 20, 30, 40]

    assert bbox_x2(bbox) == 40
    assert bbox_y2(bbox) == 60
    assert bbox_area(bbox) == 1200
    assert bbox_intersects(bbox, [39, 59, 10, 10])
    assert not bbox_intersects(bbox, [40, 60, 10, 10])
    assert bbox_contains(bbox, [12, 22, 4, 5])
    assert bbox_iou([0, 0, 10, 10], [5, 0, 10, 10]) == 0.3333333333333333
    assert bbox_clamp([-2, -2, 6, 6], 10, 10) == [0, 0, 4, 4]


def test_binary_mask_utils_and_png_export() -> None:
    left = mask_from_bboxes(8, 6, [[1, 1, 3, 3]])
    right = mask_from_bboxes(8, 6, [[3, 1, 3, 3]])

    union = mask_union(left, right)
    subtracted = mask_subtract(union, right)

    assert len(left.data) == 48
    assert mask_get(left, 1, 1)
    assert not mask_get(left, 0, 0)
    assert mask_intersects_bbox(union, [4, 2, 1, 1])
    assert mask_get(subtracted, 1, 1)
    assert not mask_get(subtracted, 3, 1)
    assert read_png_metadata(mask_to_png(union)) is not None


def test_region_metrics_distinguish_solid_line_and_texture() -> None:
    solid = make_canvas(24, 24, (246, 246, 246))
    line = make_canvas(24, 24, (246, 246, 246))
    draw_line(line, 2, 12, 20, 2, (20, 20, 20))
    noisy = make_canvas(24, 24, (246, 246, 246))
    draw_noise_patch(noisy, 4, 4, 16, 16)

    solid_metrics = measure_region(solid, [0, 0, 24, 24])
    line_metrics = measure_region(line, [2, 12, 20, 2])
    noisy_metrics = measure_region(noisy, [4, 4, 16, 16])

    assert solid_metrics.color_count == 1
    assert line_metrics.aspect_ratio == 10
    assert noisy_metrics.color_count > solid_metrics.color_count
    assert noisy_metrics.texture_score > solid_metrics.texture_score


def test_connected_components_finds_separate_components_and_filters_noise() -> None:
    mask = mask_from_bboxes(20, 20, [[2, 2, 4, 4], [12, 12, 5, 5], [0, 19, 1, 1]])
    pixels = make_canvas(20, 20, (255, 255, 255))

    components = connected_components(mask, pixels, min_area=4, max_area_ratio=0.9)

    assert [component.bbox for component in components] == [[2, 2, 4, 4], [12, 12, 5, 5]]


def test_text_exclusion_blocks_symbol_detection(tmp_path: Path) -> None:
    canvas = make_canvas(40, 40, (255, 255, 255))
    draw_rect(canvas, 10, 10, 8, 8, (20, 20, 20))
    png = pixels_to_png(canvas)

    document = extract_m29_visual_primitive_graph(
        png_data=png,
        source_image="synthetic.png",
        output_dir=tmp_path,
        text_boxes=[M29TextBox("text_1", [8, 8, 14, 14], source="test", kind="block")],
    )

    assert document.meta["counts"]["symbol"] == 0
    assert document.meta["counts"]["text"] == 1


def test_solid_rect_line_texture_and_symbol_classification(tmp_path: Path) -> None:
    canvas = make_canvas(96, 96, (255, 255, 255))
    draw_rect(canvas, 6, 6, 40, 26, (232, 232, 232))
    draw_line(canvas, 8, 50, 70, 2, (210, 210, 210))
    draw_noise_patch(canvas, 52, 8, 36, 36)
    draw_circle(canvas, 20, 72, 6, (30, 30, 30))

    document = extract_m29_visual_primitive_graph(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        output_dir=tmp_path,
    )

    types = {(node.type, node.subtype) for node in document.nodes}
    assert any(node.type == "shape" and node.subtype in {"card_background", "large_container", "separator"} for node in document.nodes)
    assert any(node.type == "image" for node in document.nodes)
    assert any(node.type == "symbol" for node in document.nodes)
    assert ("shape", "separator") in types
    assert read_png_metadata((tmp_path / "overlays" / "08_final_nodes.png").read_bytes()) is not None
    assert read_png_metadata((tmp_path / "preview_sheet.png").read_bytes()) is not None


def test_low_confidence_image_stays_unknown_without_protection(tmp_path: Path) -> None:
    canvas = make_canvas(80, 80, (255, 255, 255))
    draw_noise_patch(canvas, 20, 20, 18, 18)
    document = extract_m29_visual_primitive_graph(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        output_dir=tmp_path,
        options=M29VisualPrimitiveOptions(min_image_area=1200),
    )

    assert document.meta["counts"]["image"] == 0


def test_image_protection_blocks_internal_fragments(tmp_path: Path) -> None:
    canvas = make_canvas(100, 100, (255, 255, 255))
    draw_noise_patch(canvas, 10, 10, 60, 60)
    draw_rect(canvas, 27, 27, 14, 14, (255, 255, 255))
    draw_rect(canvas, 30, 30, 8, 8, (20, 20, 20))

    document = extract_m29_visual_primitive_graph(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        output_dir=tmp_path,
        options=M29VisualPrimitiveOptions(min_image_area=800, image_accept_threshold=0.70),
    )

    assert document.meta["counts"]["image"] >= 1
    assert any("inside_image_primitive" in item.reasons for item in document.blocked)
    assert any("image_internal_texture" in item.reasons for item in document.blocked)


def test_document_exports_assets_only_for_image_and_symbol(tmp_path: Path) -> None:
    canvas = make_canvas(96, 96, (255, 255, 255))
    draw_noise_patch(canvas, 12, 12, 32, 32)
    draw_circle(canvas, 70, 70, 6, (20, 20, 20))

    document = extract_m29_visual_primitive_graph(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        output_dir=tmp_path,
        options=M29VisualPrimitiveOptions(min_image_area=500, image_accept_threshold=0.70),
    )

    for node in document.nodes:
        if node.type in {"image", "symbol"}:
            assert node.asset_path is not None
            assert read_png_metadata((tmp_path / node.asset_path).read_bytes()) is not None
        else:
            assert node.asset_path is None


def test_blocked_evidence_has_fine_reasons_context_and_meta(tmp_path: Path) -> None:
    canvas = make_canvas(96, 96, (255, 255, 255))
    draw_noise_patch(canvas, 16, 16, 24, 24)
    document = extract_m29_visual_primitive_graph(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        output_dir=tmp_path,
        options=M29VisualPrimitiveOptions(min_image_area=2000),
    )

    assert document.meta["blockedEvidenceVersion"] == "0.2"
    assert document.meta["blockedReasonSummary"]
    assert all("symbol_metrics_rejected" not in item.reasons for item in document.blocked)
    assert any("symbol_color_too_high" in item.reasons for item in document.blocked)
    assert any("symbol_texture_too_high" in item.reasons for item in document.blocked)
    assert all(item.metrics is not None for item in document.blocked)
    assert all(item.context is not None for item in document.blocked)
    sample = document.blocked[0].context or {}
    assert {"area", "maxEdge", "textOverlapRatio", "imageOverlapRatio", "protectiveShapeOverlapRatio", "insideImage", "nearImage", "nearProtectiveShape", "nearestShapeId"} <= set(sample)


def test_blocked_reason_taxonomy_from_symbol_detector() -> None:
    pixels = make_canvas(80, 80, (255, 255, 255))
    text_mask = mask_from_bboxes(80, 80, [[4, 4, 12, 12]])
    image_mask = mask_from_bboxes(80, 80, [[18, 4, 12, 12]])
    protective_shape = M29PrimitiveNode(
        id="shape_001",
        type="shape",
        subtype="card_background",
        bbox=[40, 4, 20, 20],
        confidence=0.8,
        source="test",
        source_order=0,
        layer_hint="container",
        reasons=["test"],
        metrics=M29PrimitiveMetrics(1, 0.0, 0.0, 1.0, 1.0, 240, (240, 240, 240)),
    )
    assert is_protective_shape(protective_shape)
    options = M29VisualPrimitiveOptions(symbol_min_area=16, symbol_max_area=120)
    components = [
        make_component("text", [5, 5, 8, 8], area=64, metrics=M29PrimitiveMetrics(1, 0.0, 0.0, 1.0, 1.0, 20, (20, 20, 20))),
        make_component("image", [20, 5, 8, 8], area=64, metrics=M29PrimitiveMetrics(1, 0.0, 0.0, 1.0, 1.0, 20, (20, 20, 20))),
        make_component("shape", [40, 4, 20, 20], area=400, metrics=M29PrimitiveMetrics(1, 0.0, 0.0, 1.0, 1.0, 20, (20, 20, 20))),
        make_component("small", [64, 6, 2, 2], area=4, metrics=M29PrimitiveMetrics(1, 0.0, 0.0, 1.0, 1.0, 20, (20, 20, 20))),
        make_component("large", [4, 36, 20, 20], area=400, metrics=M29PrimitiveMetrics(1, 0.0, 0.0, 1.0, 1.0, 20, (20, 20, 20))),
        make_component("line", [32, 36, 24, 2], area=48, metrics=M29PrimitiveMetrics(1, 0.0, 0.0, 1.0, 12.0, 20, (20, 20, 20))),
        make_component("metrics", [60, 36, 10, 10], area=100, metrics=M29PrimitiveMetrics(80, 0.6, 0.5, 0.8, 1.0, 80, (80, 80, 80))),
        make_component("weak", [60, 52, 10, 10], area=100, metrics=M29PrimitiveMetrics(30, 0.25, 0.2, 0.8, 1.0, 80, (80, 80, 80))),
    ]

    _symbols, blocked = detect_symbols(components, pixels, text_mask, image_mask, [protective_shape], options)
    reasons = {reason for item in blocked for reason in item.reasons}

    assert "text_overlap" in reasons
    assert "inside_image_primitive" in reasons
    assert "protective_shape_overlap" in reasons
    assert "symbol_area_too_small" in reasons
    assert "symbol_area_too_large" in reasons
    assert "line_like" in reasons
    assert "symbol_color_too_high" in reasons
    assert "symbol_texture_too_high" in reasons
    assert "symbol_edge_too_high" in reasons
    assert "weak_symbol_metrics" in reasons
    assert "symbol_metrics_rejected" not in reasons
    assert all(item.context is not None for item in blocked)


def test_blocked_evidence_does_not_change_accepted_node_signature(tmp_path: Path) -> None:
    canvas = make_canvas(96, 96, (255, 255, 255))
    draw_rect(canvas, 6, 6, 40, 26, (232, 232, 232))
    draw_noise_patch(canvas, 52, 8, 36, 36)
    draw_circle(canvas, 20, 72, 6, (30, 30, 30))

    document = extract_m29_visual_primitive_graph(
        png_data=pixels_to_png(canvas),
        source_image="synthetic.png",
        output_dir=tmp_path,
        options=M29VisualPrimitiveOptions(min_image_area=500, image_accept_threshold=0.70),
    )

    accepted_signature = [(node.type, node.subtype, node.bbox) for node in document.nodes]
    assert accepted_signature
    assert document.meta["counts"]["blocked"] == len(document.blocked)
    assert all(item.context is not None for item in document.blocked)
    assert [(node.type, node.subtype, node.bbox) for node in document.nodes] == accepted_signature


def test_validation_rejects_missing_asset(tmp_path: Path) -> None:
    canvas = make_canvas(80, 80, (255, 255, 255))
    draw_circle(canvas, 40, 40, 8, (20, 20, 20))
    document = extract_m29_visual_primitive_graph(png_data=pixels_to_png(canvas), source_image="synthetic.png", output_dir=tmp_path)
    symbol = next((node for node in document.nodes if node.type == "symbol"), None)
    if symbol is not None and symbol.asset_path is not None:
        (tmp_path / symbol.asset_path).unlink()
        from app.visual_primitive_graph import validate_m29_document

        try:
            validate_m29_document(document, tmp_path)
        except ValueError as error:
            assert "missing or unreadable" in str(error)
        else:
            raise AssertionError("validation should reject missing symbol asset")


def make_canvas(width: int, height: int, fill: tuple[int, int, int]) -> PngPixels:
    return PngPixels(width=width, height=height, rows=[bytes(fill) * width for _ in range(height)])


def make_component(id_suffix: str, bbox: list[int], *, area: int, metrics: M29PrimitiveMetrics) -> M29ConnectedComponent:
    return M29ConnectedComponent(
        id=f"component_{id_suffix}",
        bbox=bbox,
        area=area,
        centroid=(bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2),
        fill_ratio=round(area / max(1, bbox_area(bbox)), 4),
        metrics=metrics,
        source="test",
    )


def draw_rect(canvas: PngPixels, x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> None:
    rows = [bytearray(row) for row in canvas.rows]
    color_bytes = bytes(color)
    for row_index in range(y, min(canvas.height, y + height)):
        for column in range(x, min(canvas.width, x + width)):
            rows[row_index][column * 3 : column * 3 + 3] = color_bytes
    canvas.rows[:] = [bytes(row) for row in rows]


def draw_line(canvas: PngPixels, x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> None:
    draw_rect(canvas, x, y, width, height, color)


def draw_circle(canvas: PngPixels, cx: int, cy: int, radius: int, color: tuple[int, int, int]) -> None:
    rows = [bytearray(row) for row in canvas.rows]
    color_bytes = bytes(color)
    for row_index in range(max(0, cy - radius), min(canvas.height, cy + radius + 1)):
        for column in range(max(0, cx - radius), min(canvas.width, cx + radius + 1)):
            if (column - cx) * (column - cx) + (row_index - cy) * (row_index - cy) <= radius * radius:
                rows[row_index][column * 3 : column * 3 + 3] = color_bytes
    canvas.rows[:] = [bytes(row) for row in rows]


def draw_noise_patch(canvas: PngPixels, x: int, y: int, width: int, height: int) -> None:
    rows = [bytearray(row) for row in canvas.rows]
    for row_index in range(y, min(canvas.height, y + height)):
        for column in range(x, min(canvas.width, x + width)):
            red = (column * 31 + row_index * 17) % 220
            green = (column * 13 + row_index * 29) % 220
            blue = (column * 7 + row_index * 11) % 220
            rows[row_index][column * 3 : column * 3 + 3] = bytes((red, green, blue))
    canvas.rows[:] = [bytes(row) for row in rows]


def pixels_to_png(canvas: PngPixels) -> bytes:
    return encode_rgb_png(canvas.width, canvas.height, canvas.rows)
