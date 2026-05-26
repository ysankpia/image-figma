from __future__ import annotations

from pathlib import Path

from app.m29_replay_plan import build_m295_replay_plan
from app.perception_source_compiler import extract_perception_source_compiler_report
from app.png_tools import PngPixels, encode_rgb_png
from app.region_relation_graph_report import extract_m2931_region_relation_graph_report


def test_model_text_container_candidate_compiles_to_control_shape_and_m295_cleanup(tmp_path: Path) -> None:
    source = make_png(
        240,
        160,
        fill=(248, 248, 248),
        marks=[
            ([20, 30, 180, 44], (82, 148, 76)),
            ([72, 44, 82, 14], (255, 255, 255)),
        ],
    )
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_control",
        source_png=png_bytes(source),
        ocr_document=ocr_document([ocr_block("ocr_cta", "Action", [72, 42, 82, 18])]),
        perception_model_report=perception_report([candidate("model_button", [20, 30, 200, 74], 0.86)]),
        m292_document=m292_document(
            [
                m292_object("media", [0, 0, 240, 160], "media_region", "preserve_raster", "image_replay"),
                m292_object("text", [72, 42, 82, 18], "editable_ui_text", "editable_text", "text_replay", source_evidence={"ocrBoxIds": ["ocr_cta"]}),
            ]
        ),
        output_dir=tmp_path / "compiler",
    )

    shape = only_compiled(result.report, "control_background")
    assert shape["bbox"] == [20, 30, 180, 44]
    assert shape["pixelOwner"] == "shape_geometry"
    assert shape["replayDecision"] == "shape_replay"
    assert shape["sourceEvidence"]["ocrBoxIds"] == ["ocr_cta"]
    assert shape["sourceEvidence"]["perceptionCandidateId"] == "model_button"
    assert shape["sourceEvidence"]["mediaSourceObjectId"] == "media"
    assert shape["sourceEvidence"]["foregroundClaimId"] == "model_button:foreground_claim"
    assert shape["sourceEvidence"]["shapeFillOverride"] == "#52944C"

    relation = extract_m2931_region_relation_graph_report(
        task_id="task_compiler_control",
        m292_document=result.m292_document,
        output_dir=tmp_path / "m29_3_1",
    ).report
    replay = build_m295_replay_plan(
        task_id="task_compiler_control",
        m292_document=result.m292_document,
        m2931_report=relation,
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    ).report
    shape_item = next(item for item in replay["planItems"] if item["sourceObjectId"] == shape["id"])
    assert shape_item["finalReplayAction"] == "shape_replay"
    assert {
        "target": "copied_image_asset",
        "targetSourceObjectId": "media",
        "reason": "foreground_claim_removed_from_residual_media",
        "foregroundClaimId": "model_button:foreground_claim",
        "maskKind": "rounded_rect",
    } in shape_item["cleanupTargets"]


def test_compact_non_text_candidate_compiles_to_source_crop_icon(tmp_path: Path) -> None:
    source = make_png(160, 120, fill=(248, 248, 248), marks=[([42, 32, 24, 24], (40, 90, 220)), ([88, 36, 44, 16], (20, 20, 20))])
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_icon",
        source_png=png_bytes(source),
        ocr_document=ocr_document([ocr_block("ocr_label", "Login", [88, 36, 44, 16])]),
        perception_model_report=perception_report([candidate("model_icon", [42, 32, 66, 56], 0.77)]),
        m292_document=m292_document([m292_object("media", [0, 0, 160, 120], "media_region", "preserve_raster", "image_replay")]),
        output_dir=tmp_path / "compiler",
    )

    icon = only_compiled(result.report, "raster_icon")
    assert icon["bbox"] == [42, 32, 24, 24]
    assert icon["pixelOwner"] == "raster_icon"
    assert icon["replayDecision"] == "icon_replay"
    assert icon["sourceEvidence"]["perceptionCandidateId"] == "model_icon"
    assert icon["sourceEvidence"]["controlRowSourceCropEligible"] is True

    relation = extract_m2931_region_relation_graph_report(
        task_id="task_compiler_icon",
        m292_document=result.m292_document,
        output_dir=tmp_path / "m29_3_1",
    ).report
    replay = build_m295_replay_plan(
        task_id="task_compiler_icon",
        m292_document=result.m292_document,
        m2931_report=relation,
        m294_report=None,
        output_dir=tmp_path / "m29_5",
    ).report
    assert next(item for item in replay["planItems"] if item["sourceObjectId"] == icon["id"])["finalReplayAction"] == "icon_replay"


def test_tiny_stable_circle_candidate_compiles_to_shape_not_icon(tmp_path: Path) -> None:
    source = make_png(120, 90, fill=(248, 248, 248), marks=[([40, 30, 10, 10], (45, 115, 235))])
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_circle",
        source_png=png_bytes(source),
        ocr_document=ocr_document([]),
        perception_model_report=perception_report([candidate("model_dot", [40, 30, 50, 40], 0.72)]),
        m292_document=m292_document([m292_object("media", [0, 0, 120, 90], "media_region", "preserve_raster", "image_replay")]),
        output_dir=tmp_path / "compiler",
    )

    shape = only_compiled(result.report, "control_background")
    assert shape["bbox"] == [40, 30, 10, 10]
    assert shape["pixelOwner"] == "shape_geometry"
    assert shape["replayDecision"] == "shape_replay"
    assert shape["sourceEvidence"]["internalRole"] == "internal_circle_control"
    assert shape["sourceEvidence"]["claimMaskKind"] == "circle"
    assert shape["sourceEvidence"]["shapeRadiusOverride"] == 5


def test_large_model_candidate_remains_report_only_not_source_ownership(tmp_path: Path) -> None:
    source = make_png(300, 200, fill=(30, 40, 80), marks=[([40, 50, 220, 100], (80, 120, 180))])
    result = extract_perception_source_compiler_report(
        task_id="task_compiler_hero",
        source_png=png_bytes(source),
        ocr_document=ocr_document([]),
        perception_model_report=perception_report([candidate("model_hero", [0, 0, 300, 200], 0.91)]),
        m292_document=m292_document([m292_object("media", [0, 0, 300, 200], "media_region", "preserve_raster", "image_replay")]),
        output_dir=tmp_path / "compiler",
    )

    assert result.report["summary"]["compiledSourceObjectCount"] == 0
    assert result.report["summary"]["sourceOwnershipChanged"] is False
    assert result.report["rejectedCandidates"][0]["reason"] == "large_perception_candidate_preserved_as_media_residual"
    assert len(result.m292_document["sourceObjects"]) == 1


def only_compiled(report: dict, visual_kind: str) -> dict:
    matches = [item for item in report["compiledSourceObjects"] if item["visualKind"] == visual_kind]
    assert len(matches) == 1
    return matches[0]


def perception_report(candidates: list[dict]) -> dict:
    return {
        "schemaName": "M29PerceptionModelReport",
        "schemaVersion": "0.1",
        "summary": {"candidateCount": len(candidates), "reportOnly": True},
        "candidates": candidates,
    }


def candidate(candidate_id: str, bbox: list[float], score: float) -> dict:
    return {
        "candidateId": candidate_id,
        "sourceProvider": "test_model",
        "roleHint": "unknown_ui_object",
        "bbox": bbox,
        "score": score,
        "decision": "report_only",
        "replayAuthorized": False,
        "cleanupAuthorized": False,
    }


def m292_document(objects: list[dict]) -> dict:
    return {
        "schemaName": "M292SourceUiPhysicalGraph",
        "schemaVersion": "0.1",
        "sourceObjects": objects,
        "summary": {"sourceObjectCount": len(objects)},
        "meta": {},
    }


def m292_object(
    object_id: str,
    bbox: list[int],
    visual_kind: str,
    pixel_owner: str,
    replay_decision: str,
    *,
    confidence: str = "high",
    source_evidence: dict | None = None,
) -> dict:
    return {
        "id": object_id,
        "bbox": bbox,
        "visualKind": visual_kind,
        "pixelOwner": pixel_owner,
        "replayDecision": replay_decision,
        "sourceEvidence": source_evidence or {},
        "confidence": confidence,
        "reasons": ["test"],
        "risks": [],
    }


def ocr_document(blocks: list[dict]) -> dict:
    return {"version": "0.1", "taskId": "test", "provider": "test", "model": None, "imageSize": {"width": 80, "height": 60}, "coordinateSpace": "pixel", "blocks": blocks, "warnings": []}


def ocr_block(block_id: str, text: str, bbox: list[int], *, confidence: float = 0.95) -> dict:
    return {"id": block_id, "text": text, "bbox": bbox, "confidence": confidence, "lineId": block_id, "blockId": block_id, "source": "test"}


def make_png(width: int, height: int, *, fill: tuple[int, int, int] = (250, 250, 250), marks: list[tuple[list[int], tuple[int, int, int]]] | None = None) -> PngPixels:
    rows = [bytearray(bytes(fill) * width) for _ in range(height)]
    for bbox, color in marks or []:
        x, y, w, h = bbox
        for row_index in range(y, y + h):
            for column in range(x, x + w):
                rows[row_index][column * 3 : column * 3 + 3] = bytes(color)
    return PngPixels(width=width, height=height, rows=[bytes(row) for row in rows])


def png_bytes(pixels: PngPixels) -> bytes:
    return encode_rgb_png(pixels.width, pixels.height, pixels.rows)
