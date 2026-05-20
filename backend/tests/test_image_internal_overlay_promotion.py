from __future__ import annotations

import copy
import json
from pathlib import Path

from app.image_internal_overlay_promotion import M305Options, promote_image_internal_overlay_text
from app.png_tools import PngPixels, decode_png_pixels, encode_rgb_png


def test_promotion_ready_creates_cleaned_parent_asset_and_text_node(tmp_path: Path) -> None:
    m30_dir = tmp_path / "m30"
    m2905_dir = tmp_path / "m29_0_5"
    parent_asset = m2905_dir / "assets" / "visual_assets" / "visual_asset_0023.png"
    write_parent_asset(parent_asset)
    original_bytes = parent_asset.read_bytes()
    dsl = base_dsl()

    document = promote_image_internal_overlay_text(
        dsl=dsl,
        output_dir=tmp_path / "m30_5",
        m30_dir=m30_dir,
        m294_document=m294_document([promotion_item()]),
        m294_json_path="/tmp/m29_4/image_internal_overlay_text_recognition.json",
        m2905_document=m2905_document(asset_path="assets/visual_assets/visual_asset_0023.png"),
        m2905_json_path=str(m2905_dir / "refined_visual_objects.json"),
        m2902_document=m2902_document(),
        m2902_json_path=str(tmp_path / "m29_0_2" / "text_masked_media_audit.json"),
    )

    assert document.summary["promotedTextCount"] == 1
    assert document.summary["dslChanged"] is True
    assert parent_asset.read_bytes() == original_bytes
    assert has_role(dsl, "m30_image_internal_overlay_parent")
    text_nodes = [child for child in dsl["root"]["children"] if child.get("role") == "m30_image_internal_overlay_text"]
    assert len(text_nodes) == 1
    assert text_nodes[0]["content"]["text"] == "1/6"
    assert text_nodes[0]["layout"] == {"x": 34, "y": 24, "width": 30, "height": 20}
    assert text_nodes[0]["style"]["color"].upper() == "#F8F8F8"

    item = document.items[0]
    assert item.cleaned_parent_asset_path
    cleaned = decode_png_pixels((m30_dir / item.cleaned_parent_asset_path).read_bytes())
    assert pixel(cleaned, 38, 30) == (25, 25, 25)
    assert pixel(cleaned, 31, 23) == (25, 25, 25)
    assert pixel(cleaned, 28, 20) == (25, 25, 25)


def test_existing_parent_image_node_is_retargeted_without_duplicate_parent(tmp_path: Path) -> None:
    m30_dir = tmp_path / "m30"
    existing_asset = m30_dir / "assets" / "m30_visual_assets" / "parent.png"
    write_parent_asset(existing_asset)
    dsl = base_dsl()
    dsl["assets"].append(
        {
            "assetId": "m30_visual_asset_parent",
            "type": "image",
            "role": "m30_visual_asset",
            "url": "assets/m30_visual_assets/parent.png",
            "format": "png",
            "width": 100,
            "height": 60,
            "storage": "local",
        }
    )
    dsl["root"]["children"].append(
        {
            "id": "m30_image_parent",
            "type": "image",
            "role": "m30_visual_asset",
            "layout": {"x": 10, "y": 10, "width": 100, "height": 60},
            "source": {"assetId": "m30_visual_asset_parent"},
            "meta": {"m30Materialized": True, "sourceBBox": [10, 10, 100, 60]},
        }
    )

    document = promote_image_internal_overlay_text(
        dsl=dsl,
        output_dir=tmp_path / "m30_5",
        m30_dir=m30_dir,
        m294_document=m294_document([promotion_item()]),
        m294_json_path=None,
        m2905_document=m2905_document(asset_path="missing.png"),
        m2905_json_path=str(tmp_path / "m29_0_5" / "refined_visual_objects.json"),
        m2902_document=m2902_document(),
        m2902_json_path=str(tmp_path / "m29_0_2" / "text_masked_media_audit.json"),
    )

    assert document.summary["promotedTextCount"] == 1
    assert len([child for child in dsl["root"]["children"] if child.get("role") == "m30_image_internal_overlay_parent"]) == 0
    parent = next(child for child in dsl["root"]["children"] if child.get("id") == "m30_image_parent")
    assert parent["source"]["assetId"].startswith("m30_image_internal_overlay_cleaned_")


def test_missing_tight_ocr_bbox_is_skipped(tmp_path: Path) -> None:
    item = promotion_item()
    item.pop("recognizedTextBBox")
    document = run_basic(tmp_path, [item])

    assert document.summary["promotedTextCount"] == 0
    assert document.items[0].decision == "skipped"
    assert "missing_tight_recognized_text_bbox" in document.items[0].reasons


def test_ambiguous_parent_is_skipped(tmp_path: Path) -> None:
    m30_dir = tmp_path / "m30"
    m2905_dir = tmp_path / "m29_0_5"
    path_a = m2905_dir / "assets" / "visual_assets" / "a.png"
    path_b = m2905_dir / "assets" / "visual_assets" / "b.png"
    write_parent_asset(path_a)
    write_parent_asset(path_b)

    document = promote_image_internal_overlay_text(
        dsl=base_dsl(),
        output_dir=tmp_path / "m30_5",
        m30_dir=m30_dir,
        m294_document=m294_document([promotion_item()]),
        m294_json_path=None,
        m2905_document={
            "visualAssets": [
                visual_asset("visual_asset_a", "assets/visual_assets/a.png"),
                visual_asset("visual_asset_b", "assets/visual_assets/b.png"),
            ]
        },
        m2905_json_path=str(m2905_dir / "refined_visual_objects.json"),
        m2902_document=m2902_document(),
        m2902_json_path=str(tmp_path / "m29_0_2" / "text_masked_media_audit.json"),
    )

    assert document.summary["promotedTextCount"] == 0
    assert "ambiguous_m2905_parent_visual_asset" in document.items[0].reasons


def test_max_promotions_skips_extra_items(tmp_path: Path) -> None:
    first = promotion_item()
    second = copy.deepcopy(first)
    second["id"] = "m294_overlay_text_010"
    document = run_basic(tmp_path, [first, second], options=M305Options(max_promotions=1))

    assert document.summary["promotedTextCount"] == 1
    assert len(document.items) == 2
    assert document.items[1].decision == "skipped"
    assert "skipped_max_promotions" in document.items[1].reasons


def test_coordinate_scaling_maps_page_bbox_to_parent_asset_pixels(tmp_path: Path) -> None:
    m30_dir = tmp_path / "m30"
    m2905_dir = tmp_path / "m29_0_5"
    parent_asset = m2905_dir / "assets" / "visual_assets" / "scaled.png"
    write_parent_asset(parent_asset, width=200, height=120)

    document = promote_image_internal_overlay_text(
        dsl=base_dsl(),
        output_dir=tmp_path / "m30_5",
        m30_dir=m30_dir,
        m294_document=m294_document([promotion_item()]),
        m294_json_path=None,
        m2905_document=m2905_document(asset_path="assets/visual_assets/scaled.png"),
        m2905_json_path=str(m2905_dir / "refined_visual_objects.json"),
        m2902_document=m2902_document(),
        m2902_json_path=str(tmp_path / "m29_0_2" / "text_masked_media_audit.json"),
    )

    assert document.items[0].metrics["scaleX"] == 2.0
    assert document.items[0].metrics["scaleY"] == 2.0
    assert document.items[0].metrics["localRecognizedTextBBox"] == [48, 28, 60, 40]


def run_basic(tmp_path: Path, items: list[dict], options: M305Options | None = None):
    m30_dir = tmp_path / "m30"
    m2905_dir = tmp_path / "m29_0_5"
    parent_asset = m2905_dir / "assets" / "visual_assets" / "visual_asset_0023.png"
    write_parent_asset(parent_asset)
    return promote_image_internal_overlay_text(
        dsl=base_dsl(),
        output_dir=tmp_path / "m30_5",
        m30_dir=m30_dir,
        m294_document=m294_document(items),
        m294_json_path=None,
        m2905_document=m2905_document(asset_path="assets/visual_assets/visual_asset_0023.png"),
        m2905_json_path=str(m2905_dir / "refined_visual_objects.json"),
        m2902_document=m2902_document(),
        m2902_json_path=str(tmp_path / "m29_0_2" / "text_masked_media_audit.json"),
        options=options,
    )


def write_parent_asset(path: Path, width: int = 100, height: int = 60) -> None:
    rows = [bytearray(bytes((110, 140, 170)) * width) for _ in range(height)]
    scale_x = width / 100
    scale_y = height / 60
    pill = [20, 12, 54, 30]
    text = [24, 14, 30, 20]
    for row_idx in range(round(pill[1] * scale_y), round((pill[1] + pill[3]) * scale_y)):
        for col_idx in range(round(pill[0] * scale_x), round((pill[0] + pill[2]) * scale_x)):
            set_pixel(rows, col_idx, row_idx, (25, 25, 25))
    for row_idx in range(round(text[1] * scale_y), round((text[1] + text[3]) * scale_y)):
        for col_idx in range(round(text[0] * scale_x), round((text[0] + text[2]) * scale_x)):
            if (col_idx + row_idx) % 3 != 0:
                set_pixel(rows, col_idx, row_idx, (248, 248, 248))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode_rgb_png(width, height, [bytes(row) for row in rows]))


def set_pixel(rows: list[bytearray], x: int, y: int, rgb: tuple[int, int, int]) -> None:
    offset = x * 3
    rows[y][offset : offset + 3] = bytes(rgb)


def pixel(pixels: PngPixels, x: int, y: int) -> tuple[int, int, int]:
    row = pixels.rows[y]
    offset = x * 3
    return row[offset], row[offset + 1], row[offset + 2]


def base_dsl() -> dict:
    return {
        "version": "0.1",
        "assets": [
            {
                "assetId": "asset_banner",
                "type": "image",
                "role": "fallback_region",
                "url": "assets/fallback.png",
                "format": "png",
                "width": 200,
                "height": 120,
                "storage": "local",
            }
        ],
        "root": {
            "id": "root",
            "type": "frame",
            "role": "screen",
            "children": [
                {
                    "id": "fallback_full_image",
                    "type": "image",
                    "role": "fallback_region",
                    "layout": {"x": 0, "y": 0, "width": 200, "height": 120},
                    "source": {"assetId": "asset_banner"},
                },
                {
                    "id": "existing_text",
                    "type": "text",
                    "role": "m30_text_member",
                    "layout": {"x": 1, "y": 1, "width": 10, "height": 10},
                    "content": {"text": "x"},
                    "meta": {"m30Materialized": True},
                },
            ],
        },
        "meta": {"qualityFlags": ["m30_evidence_grounded_materialization"]},
    }


def promotion_item() -> dict:
    return {
        "id": "m294_overlay_text_009",
        "sourceM293OverlayId": "m293_overlay_009",
        "sourceM292CandidateId": "m292_overlay_text_009",
        "sourceImageNodeId": "m29_image_003",
        "sourceM29NodeId": "image_003",
        "sourceImageBBox": [10, 10, 100, 60],
        "overlayBBox": [30, 20, 54, 30],
        "recognizedText": "1/6",
        "rawRecognizedText": "1/6",
        "recognitionConfidence": 0.98,
        "recognizedTextBBox": [34, 24, 30, 20],
        "decision": "promotion_ready",
        "materializationEligible": False,
        "reasons": ["recognized_bbox_from_local_ocr", "local_crop_ocr_counter_pattern"],
        "metrics": {},
    }


def m294_document(items: list[dict]) -> dict:
    return {"schemaName": "M294ImageInternalOverlayTextRecognitionDocument", "schemaVersion": "0.1", "items": items}


def visual_asset(asset_id: str, asset_path: str) -> dict:
    return {
        "id": asset_id,
        "bbox": [10, 10, 100, 60],
        "assetPath": asset_path,
        "sourceEvidenceNodeIds": ["evidence_0004"],
        "sourceObjectId": "voc_0024",
        "decision": "candidate",
        "assetUse": "image_asset",
        "risks": [],
        "textOverlapRatio": 0.02,
    }


def m2905_document(asset_path: str) -> dict:
    return {"visualAssets": [visual_asset("visual_asset_0023", asset_path)]}


def m2902_document() -> dict:
    return {
        "mediaEvidence": [
            {
                "id": "m29_image_003",
                "source": "m29_image",
                "bbox": [10, 10, 100, 60],
                "decision": "accepted_image",
                "suggestedNextAction": "keep_accepted_image",
                "assetPath": "assets/accepted_images/m29_image_003.png",
            }
        ]
    }


def has_role(dsl: dict, role: str) -> bool:
    return any(child.get("role") == role for child in dsl["root"]["children"] if isinstance(child, dict))
