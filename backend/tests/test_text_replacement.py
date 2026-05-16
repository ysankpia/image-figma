from __future__ import annotations

import importlib
from pathlib import Path
import struct
import sys
import zlib
from typing import Any

from fastapi.testclient import TestClient

from app.config import Settings
from app.ocr import OCRBlock, OCRDocument
from app.png_tools import PngMetadata
from app.text_replacement import (
    apply_text_replacements,
    build_text_replacement_document,
    build_visible_text_element,
    visible_text_font_size,
)
from conftest import PNG_BYTES, PNG_HEIGHT, PNG_WIDTH, png_chunk


def test_text_replacement_debug_creates_document_without_applying_to_dsl(
    monkeypatch,
    tmp_path,
) -> None:
    client = create_client_with_env(monkeypatch, tmp_path, {"TEXT_REPLACEMENT_MODE": "debug"})

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        replacement = client.get(f"/api/tasks/{task_id}/text-replacements")
        assert replacement.status_code == 200
        data = replacement.json()["data"]
        assert data["status"] == "completed"
        assert data["mode"] == "debug"
        assert len(data["decisions"]) == 2

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        roles = {child.get("role") for child in dsl["root"]["children"]}
        assert "visible_text_replacement" not in roles
        assert "text_replacement_cover" not in roles


def test_text_replacement_apply_adds_cover_and_visible_text(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(
        monkeypatch,
        tmp_path,
        {
            "TEXT_REPLACEMENT_MODE": "apply",
            "TEXT_REPLACEMENT_MIN_CONFIDENCE": "0.90",
        },
    )

    with client:
        png = make_text_fixture_png(
            PNG_WIDTH,
            PNG_HEIGHT,
            (247, 248, 250),
            [
                ([25, 109, 143, 36], (20, 20, 20)),
                ([25, 157, 190, 32], (20, 20, 20)),
            ],
        )
        upload = client.post("/api/upload", files={"file": ("input.png", png, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        replacement = client.get(f"/api/tasks/{task_id}/text-replacements").json()["data"]
        assert replacement["status"] == "completed"
        assert replacement["mode"] == "apply"
        assert replacement["meta"]["acceptedCount"] == 2
        assert replacement["meta"]["appliedCount"] == 2
        assert replacement["meta"]["blockedAcceptedCount"] == 0
        assert replacement["meta"]["qualityNotes"] == "text_replacement_quality_control"
        first_decision = replacement["decisions"][0]
        assert first_decision["quality"]["risk"] == "low"
        assert first_decision["quality"]["applyEligible"] is True
        assert first_decision["application"] == {"status": "applied", "reason": "quality_gate_passed"}
        second_decision = replacement["decisions"][1]
        assert second_decision["quality"]["risk"] == "medium"
        assert second_decision["quality"]["applyEligible"] is True
        assert second_decision["application"] == {"status": "applied", "reason": "quality_gate_passed"}

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        children = {child["id"]: child for child in dsl["root"]["children"]}
        assert "original_ref" in children
        assert "fallback_region_header" in children
        assert "fallback_region_content" in children
        assert "fallback_region_bottom" in children
        assert "text_ocr_text_001" in children
        assert "cover_ocr_text_001" in children
        assert "visible_text_ocr_text_001" in children
        assert "cover_ocr_text_002" in children
        assert "visible_text_ocr_text_002" in children
        assert children["cover_ocr_text_001"]["type"] == "shape"
        assert children["cover_ocr_text_001"]["role"] == "text_replacement_cover"
        assert children["visible_text_ocr_text_001"]["type"] == "text"
        assert children["visible_text_ocr_text_001"]["role"] == "visible_text_replacement"
        assert children["visible_text_ocr_text_001"]["style"]["visible"] is True
        assert children["visible_text_ocr_text_001"]["style"]["lineHeight"] >= children["visible_text_ocr_text_001"]["style"]["fontSize"]
        assert children["text_ocr_text_001"]["style"]["visible"] is False
        assert dsl["meta"]["textReplacementCount"] == 2
        assert dsl["meta"]["textReplacementAppliedCount"] == 2
        assert dsl["meta"]["textReplacementBlockedCount"] == 0
        assert "m11_visible_text_replacements" in dsl["meta"]["qualityFlags"]
        assert "m12_text_replacement_coverage_expansion" in dsl["meta"]["qualityFlags"]
        assert "m13_text_replacement_quality_control" in dsl["meta"]["qualityFlags"]


def test_text_replacement_mode_off_has_no_result(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(monkeypatch, tmp_path, {"TEXT_REPLACEMENT_MODE": "off"})

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        replacement = client.get(f"/api/tasks/{task_id}/text-replacements")
        assert replacement.status_code == 404
        assert replacement.json()["error"]["code"] == "TEXT_REPLACEMENT_NOT_FOUND"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        roles = {child.get("role") for child in dsl["root"]["children"]}
        assert "visible_text_replacement" not in roles


def test_missing_task_text_replacements_returns_task_not_found(client: TestClient) -> None:
    response = client.get("/api/tasks/task_missing/text-replacements")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TASK_NOT_FOUND"


def test_existing_task_without_text_replacements_returns_not_found(client: TestClient) -> None:
    from app.state import state

    state.database.insert_task(
        {
            "id": "task_without_replacements",
            "status": "completed",
            "stage": "completed",
            "progress": 100,
            "message": "No text replacements.",
            "original_filename": "input.png",
            "mime_type": "image/png",
            "file_size": 1,
            "upload_path": "/tmp/input.png",
            "created_at": "2026-05-16T00:00:00+00:00",
            "updated_at": "2026-05-16T00:00:00+00:00",
            "completed_at": "2026-05-16T00:00:00+00:00",
            "failed_at": None,
        }
    )

    response = client.get("/api/tasks/task_without_replacements/text-replacements")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TEXT_REPLACEMENT_NOT_FOUND"


def test_replacement_decisions_cover_rejection_reasons() -> None:
    settings = make_settings(
        text_replacement_mode="debug",
        text_replacement_max_blocks=1,
        text_replacement_min_confidence=0.95,
    )
    image = PngMetadata(100, 100, 8, 2, 0, 0, 0)
    ocr = OCRDocument(
        version="0.1",
        taskId="task_1",
        provider="fake",
        model=None,
        imageSize={"width": 100, "height": 100},
        coordinateSpace="pixel",
        blocks=[
            OCRBlock("low_conf", "Low", [10, 50, 30, 20], 0.5, "line_1", "block_1"),
            OCRBlock("status", "9:41", [10, 10, 30, 20], 0.99, "line_2", "block_2"),
            OCRBlock("small", "A", [10, 50, 4, 20], 0.99, "line_3", "block_3"),
            OCRBlock("tall", "Tall", [10, 50, 40, 80], 0.99, "line_4", "block_4"),
            OCRBlock("accepted", "Good", [10, 50, 40, 20], 0.99, "line_5", "block_5"),
            OCRBlock("maxed", "Later", [10, 50, 40, 20], 0.99, "line_6", "block_6"),
        ],
        warnings=[],
    )

    document = build_text_replacement_document(
        task_id="task_1",
        image=image,
        png_data=make_text_fixture_png(100, 100, (247, 248, 250), [([10, 50, 40, 20], (20, 20, 20))]),
        ocr_document=ocr,
        settings=settings,
    )

    reasons = {decision.ocrBlockId: decision.reason for decision in document.decisions}
    assert reasons == {
        "low_conf": "confidence_too_low",
        "status": "status_bar_or_too_small",
        "small": "bbox_too_small",
        "tall": "bbox_too_tall",
        "accepted": "solid_light_background",
        "maxed": "max_blocks_reached",
    }


def test_complex_and_dark_background_are_rejected() -> None:
    settings = make_settings(text_replacement_mode="debug")
    image = PngMetadata(100, 100, 8, 2, 0, 0, 0)
    ocr = OCRDocument(
        version="0.1",
        taskId="task_1",
        provider="fake",
        model=None,
        imageSize={"width": 100, "height": 100},
        coordinateSpace="pixel",
        blocks=[
            OCRBlock("complex", "Complex", [10, 50, 40, 20], 0.99, "line_1", "block_1"),
            OCRBlock("dark", "Dark", [10, 50, 40, 20], 0.99, "line_2", "block_2"),
        ],
        warnings=[],
    )

    complex_document = build_text_replacement_document(
        task_id="task_1",
        image=image,
        png_data=make_checker_png(100, 100),
        ocr_document=ocr,
        settings=settings,
    )
    dark_document = build_text_replacement_document(
        task_id="task_1",
        image=image,
        png_data=make_rgb_png(100, 100, (20, 20, 20)),
        ocr_document=ocr,
        settings=settings,
    )

    assert complex_document.decisions[0].reason == "complex_background"
    assert complex_document.decisions[0].quality["risk"] == "high"
    assert complex_document.decisions[0].quality["applyEligible"] is False
    assert complex_document.decisions[0].quality["reasons"] == [
        "complex_background_rejected",
        "background_sample_available",
        "foreground_sample_available",
    ]
    assert complex_document.decisions[0].application == {
        "status": "not_applicable",
        "reason": "decision_not_accepted",
    }
    assert dark_document.decisions[0].reason == "dark_background"


def test_accepted_medium_risk_region_is_reported_but_still_applied() -> None:
    settings = make_settings(text_replacement_mode="apply")
    image = PngMetadata(320, 1000, 8, 2, 0, 0, 0)
    ocr = OCRDocument(
        version="0.1",
        taskId="task_1",
        provider="fake",
        model=None,
        imageSize={"width": 320, "height": 1000},
        coordinateSpace="pixel",
        blocks=[OCRBlock("hero_text", "2026级新生", [80, 120, 120, 30], 0.99, "line_1", "block_1")],
        warnings=[],
    )

    document = build_text_replacement_document(
        task_id="task_1",
        image=image,
        png_data=make_text_fixture_png(320, 1000, (247, 248, 250), [([80, 120, 120, 30], (20, 20, 20))]),
        ocr_document=ocr,
        settings=settings,
    )

    decision = document.decisions[0]
    assert decision.decision == "accepted"
    assert decision.quality["region"] == "hero"
    assert decision.quality["risk"] == "medium"
    assert decision.quality["applyEligible"] is True
    assert "hero_region_caution" in decision.quality["reasons"]
    assert decision.application == {"status": "applied", "reason": "quality_gate_passed"}
    assert document.meta["acceptedCount"] == 1
    assert document.meta["appliedCount"] == 1
    assert document.meta["blockedAcceptedCount"] == 0

    enhanced = apply_text_replacements(
        {
            "version": "0.1",
            "taskId": "task_1",
            "assets": [],
            "root": {"id": "root", "type": "frame", "layout": {"x": 0, "y": 0, "width": 320, "height": 1000}, "children": []},
            "meta": {"qualityFlags": []},
        },
        document,
        ocr,
    )
    children = {child["id"]: child for child in enhanced["root"]["children"]}
    assert "cover_hero_text" in children
    assert "visible_text_hero_text" in children
    assert enhanced["meta"]["textReplacementAppliedCount"] == 1
    assert enhanced["meta"]["textReplacementBlockedCount"] == 0


def test_accepted_high_risk_replacement_is_reported_but_blocked_by_quality_gate() -> None:
    settings = make_settings(text_replacement_mode="apply")
    image = PngMetadata(320, 1000, 8, 2, 0, 0, 0)
    ocr = OCRDocument(
        version="0.1",
        taskId="task_1",
        provider="fake",
        model=None,
        imageSize={"width": 320, "height": 1000},
        coordinateSpace="pixel",
        blocks=[OCRBlock("tiny_safe", "A", [80, 220, 12, 10], 0.99, "line_1", "block_1")],
        warnings=[],
    )

    document = build_text_replacement_document(
        task_id="task_1",
        image=image,
        png_data=make_text_fixture_png(320, 1000, (247, 248, 250), [([80, 220, 12, 10], (20, 20, 20))]),
        ocr_document=ocr,
        settings=settings,
    )

    decision = document.decisions[0]
    assert decision.decision == "accepted"
    assert decision.quality["risk"] == "high"
    assert decision.quality["applyEligible"] is False
    assert "large_cover_area" in decision.quality["reasons"]
    assert decision.application == {"status": "blocked", "reason": "quality_gate_blocked"}
    assert document.meta["acceptedCount"] == 1
    assert document.meta["appliedCount"] == 0
    assert document.meta["blockedAcceptedCount"] == 1

    enhanced = apply_text_replacements(
        {
            "version": "0.1",
            "taskId": "task_1",
            "assets": [],
            "root": {"id": "root", "type": "frame", "layout": {"x": 0, "y": 0, "width": 320, "height": 1000}, "children": []},
            "meta": {"qualityFlags": []},
        },
        document,
        ocr,
    )
    children = {child["id"]: child for child in enhanced["root"]["children"]}
    assert "cover_tiny_safe" not in children
    assert "visible_text_tiny_safe" not in children
    assert enhanced["meta"]["textReplacementAppliedCount"] == 0
    assert enhanced["meta"]["textReplacementBlockedCount"] == 1


def test_home_like_complex_fixture_keeps_strategy_evidence_for_rejections() -> None:
    settings = make_settings(text_replacement_mode="debug")
    image = PngMetadata(941, 1672, 8, 2, 0, 0, 0)
    blocks = [
        OCRBlock("ocr_text_004", "男生", [213, 261, 55, 33], 0.999, "line_1", "block_1"),
        OCRBlock("ocr_text_005", "2026级新生", [310, 263, 128, 30], 0.998, "line_1", "block_2"),
        OCRBlock("ocr_text_026", "可视化选床，像高铁选座一样直观", [78, 1094, 377, 29], 0.994, "line_2", "block_3"),
        OCRBlock("ocr_text_029", "可选", [519, 1221, 48, 26], 0.999, "line_3", "block_4"),
        OCRBlock("ocr_text_030", "已选", [630, 1221, 46, 26], 0.999, "line_3", "block_5"),
        OCRBlock("ocr_text_031", "不可选", [739, 1221, 65, 26], 0.999, "line_3", "block_6"),
        OCRBlock("ocr_text_032", "温馨提示", [92, 1320, 129, 30], 0.996, "line_4", "block_7"),
        OCRBlock("ocr_text_034", "选床确认后将无法自行修改，如需调整请联系辅导员。", [104, 1409, 467, 17], 0.997, "line_5", "block_8"),
    ]
    ocr = OCRDocument(
        version="0.1",
        taskId="task_home",
        provider="fake",
        model=None,
        imageSize={"width": 941, "height": 1672},
        coordinateSpace="pixel",
        blocks=blocks,
        warnings=[],
    )

    document = build_text_replacement_document(
        task_id="task_home",
        image=image,
        png_data=make_checker_png(941, 1672),
        ocr_document=ocr,
        settings=settings,
    )

    decisions = {decision.ocrBlockId: decision for decision in document.decisions}
    assert set(decisions) == {block.id for block in blocks}
    for block_id in {"ocr_text_004", "ocr_text_005", "ocr_text_026", "ocr_text_029", "ocr_text_031", "ocr_text_032", "ocr_text_034"}:
        decision = decisions[block_id]
        assert decision.decision == "rejected"
        assert decision.reason == "complex_background"
        assert decision.quality["risk"] == "high"
        assert decision.quality["applyEligible"] is False
        assert "complex_background_rejected" in decision.quality["reasons"]
        assert decision.strategy is not None
        assert decision.strategy["attempts"][0]["name"] == "standard_perimeter_sample"
        assert decision.application == {"status": "not_applicable", "reason": "decision_not_accepted"}
    assert decisions["ocr_text_026"].quality["region"] == "preview_card"
    assert decisions["ocr_text_032"].quality["region"] == "tip_card"
    assert decisions["ocr_text_030"].quality["region"] == "preview_card"
    assert document.meta["reasonSummary"]["complex_background_rejected"] == 8
    assert document.meta["regionSummary"]["preview_card"]["rejected"] == 4
    assert document.meta["regionSummary"]["tip_card"]["rejected"] == 2
    assert document.meta["strategySummary"]["standard_perimeter_sample"]["rejected"] == 8


def test_ui_aware_sampling_rescues_badge_from_complex_standard_sample() -> None:
    settings = make_settings(text_replacement_mode="debug")
    image = PngMetadata(180, 120, 8, 2, 0, 0, 0)
    bbox = [52, 58, 76, 24]
    ocr = OCRDocument(
        version="0.1",
        taskId="task_badge",
        provider="fake",
        model=None,
        imageSize={"width": 180, "height": 120},
        coordinateSpace="pixel",
        blocks=[OCRBlock("badge", "2026级新生", bbox, 0.99, "line_1", "block_1")],
        warnings=[],
    )

    document = build_text_replacement_document(
        task_id="task_badge",
        image=image,
        png_data=make_noisy_expanded_text_png(180, 120, bbox, (232, 242, 255), (28, 56, 92)),
        ocr_document=ocr,
        settings=settings,
    )

    decision = document.decisions[0]
    assert decision.decision == "accepted"
    assert decision.strategy is not None
    assert decision.strategy["name"] == "pill_inner_background_sample"
    assert decision.strategy["fallbackFrom"] == "standard_perimeter_sample"
    assert decision.strategy["attempts"][0]["reason"] == "complex_background"
    assert decision.reason == "solid_light_background"
    assert document.meta["rescuedFromComplexBackgroundCount"] == 1


def test_ui_aware_sampling_rescues_colored_status_badge_with_light_text() -> None:
    settings = make_settings(text_replacement_mode="debug")
    image = PngMetadata(160, 120, 8, 2, 0, 0, 0)
    bbox = [52, 58, 56, 24]
    ocr = OCRDocument(
        version="0.1",
        taskId="task_status",
        provider="fake",
        model=None,
        imageSize={"width": 160, "height": 120},
        coordinateSpace="pixel",
        blocks=[OCRBlock("status", "进行中", bbox, 0.99, "line_1", "block_1")],
        warnings=[],
    )

    document = build_text_replacement_document(
        task_id="task_status",
        image=image,
        png_data=make_noisy_expanded_text_png(160, 120, bbox, (28, 132, 88), (255, 255, 255)),
        ocr_document=ocr,
        settings=settings,
    )

    decision = document.decisions[0]
    assert decision.decision == "accepted"
    assert decision.reason == "dark_or_colored_background_light_text"
    assert decision.strategy is not None
    assert decision.strategy["name"] == "pill_inner_background_sample"
    assert decision.foreground is not None
    assert decision.foreground["color"] == "#FFFFFF"


def test_ui_aware_sampling_rescues_legend_labels_consistently_without_covering_swatch() -> None:
    settings = make_settings(text_replacement_mode="apply")
    image = PngMetadata(260, 120, 8, 2, 0, 0, 0)
    blocks = [
        OCRBlock("available", "可选", [48, 58, 38, 22], 0.99, "line_1", "block_1"),
        OCRBlock("selected", "已选", [118, 58, 38, 22], 0.99, "line_1", "block_2"),
        OCRBlock("disabled", "不可选", [188, 58, 54, 22], 0.99, "line_1", "block_3"),
    ]
    ocr = OCRDocument(
        version="0.1",
        taskId="task_legend",
        provider="fake",
        model=None,
        imageSize={"width": 260, "height": 120},
        coordinateSpace="pixel",
        blocks=blocks,
        warnings=[],
    )

    document = build_text_replacement_document(
        task_id="task_legend",
        image=image,
        png_data=make_legend_fixture_png(260, 120, [block.bbox for block in blocks]),
        ocr_document=ocr,
        settings=settings,
    )

    assert [decision.decision for decision in document.decisions] == ["accepted", "accepted", "accepted"]
    assert {decision.strategy["name"] for decision in document.decisions if decision.strategy is not None} == {
        "legend_text_side_sample"
    }
    assert document.meta["rescuedFromComplexBackgroundCount"] == 3
    assert document.decisions[0].expandedBBox is not None
    assert document.decisions[0].expandedBBox[0] == 47


def test_ui_aware_sampling_rescues_outline_button_text() -> None:
    settings = make_settings(text_replacement_mode="debug")
    image = PngMetadata(240, 140, 8, 2, 0, 0, 0)
    bbox = [66, 70, 110, 24]
    ocr = OCRDocument(
        version="0.1",
        taskId="task_button",
        provider="fake",
        model=None,
        imageSize={"width": 240, "height": 140},
        coordinateSpace="pixel",
        blocks=[OCRBlock("preview", "预览选床界面", bbox, 0.99, "line_1", "block_1")],
        warnings=[],
    )

    document = build_text_replacement_document(
        task_id="task_button",
        image=image,
        png_data=make_noisy_expanded_text_png(240, 140, bbox, (247, 248, 250), (20, 20, 20)),
        ocr_document=ocr,
        settings=settings,
    )

    decision = document.decisions[0]
    assert decision.decision == "accepted"
    assert decision.strategy is not None
    assert decision.strategy["name"] == "outline_button_text_sample"
    assert decision.expandedBBox == [64, 68, 114, 28]


def test_ui_aware_sampling_rescues_card_tip_text() -> None:
    settings = make_settings(text_replacement_mode="debug")
    image = PngMetadata(360, 180, 8, 2, 0, 0, 0)
    bbox = [78, 92, 128, 28]
    ocr = OCRDocument(
        version="0.1",
        taskId="task_tip",
        provider="fake",
        model=None,
        imageSize={"width": 360, "height": 180},
        coordinateSpace="pixel",
        blocks=[OCRBlock("tip", "温馨提示", bbox, 0.99, "line_1", "block_1")],
        warnings=[],
    )

    document = build_text_replacement_document(
        task_id="task_tip",
        image=image,
        png_data=make_noisy_expanded_text_png(360, 180, bbox, (255, 250, 230), (40, 40, 40)),
        ocr_document=ocr,
        settings=settings,
    )

    decision = document.decisions[0]
    assert decision.decision == "accepted"
    assert decision.strategy is not None
    assert decision.strategy["name"] == "card_local_background_sample"


def test_ui_aware_sampling_rescues_bottom_nav_label_without_covering_icon() -> None:
    settings = make_settings(text_replacement_mode="apply")
    image = PngMetadata(180, 1000, 8, 2, 0, 0, 0)
    bbox = [72, 914, 36, 22]
    ocr = OCRDocument(
        version="0.1",
        taskId="task_nav",
        provider="fake",
        model=None,
        imageSize={"width": 180, "height": 1000},
        coordinateSpace="pixel",
        blocks=[OCRBlock("mine", "我的", bbox, 0.99, "line_1", "block_1")],
        warnings=[],
    )

    document = build_text_replacement_document(
        task_id="task_nav",
        image=image,
        png_data=make_noisy_expanded_text_png(180, 1000, bbox, (247, 248, 250), (80, 80, 80)),
        ocr_document=ocr,
        settings=settings,
    )

    decision = document.decisions[0]
    assert decision.decision == "accepted"
    assert decision.strategy is not None
    assert decision.strategy["name"] == "bottom_nav_label_sample"
    assert decision.expandedBBox == [70, 913, 40, 25]


def test_ui_aware_sampling_can_be_disabled() -> None:
    settings = make_settings(text_replacement_mode="debug", text_replacement_ui_aware_sampling=False)
    image = PngMetadata(180, 120, 8, 2, 0, 0, 0)
    bbox = [52, 58, 76, 24]
    ocr = OCRDocument(
        version="0.1",
        taskId="task_badge",
        provider="fake",
        model=None,
        imageSize={"width": 180, "height": 120},
        coordinateSpace="pixel",
        blocks=[OCRBlock("badge", "2026级新生", bbox, 0.99, "line_1", "block_1")],
        warnings=[],
    )

    document = build_text_replacement_document(
        task_id="task_badge",
        image=image,
        png_data=make_noisy_expanded_text_png(180, 120, bbox, (232, 242, 255), (28, 56, 92)),
        ocr_document=ocr,
        settings=settings,
    )

    decision = document.decisions[0]
    assert decision.decision == "rejected"
    assert decision.reason == "complex_background"
    assert decision.strategy is not None
    assert [attempt["name"] for attempt in decision.strategy["attempts"]] == ["standard_perimeter_sample"]


def test_home_screenshot_m14_sampling_regression_when_sample_exists() -> None:
    sample_path = Path("/Users/luhui/Downloads/宿舍床位可视化选择系统_UI设计图/学生端/01_学生端-首页选床活动.png")
    if not sample_path.exists():
        return
    settings = make_settings(text_replacement_mode="apply")
    image = PngMetadata(941, 1672, 8, 2, 0, 0, 0)
    blocks = [
        OCRBlock("ocr_text_004", "男生", [213, 261, 55, 33], 0.9999145269393921, "line_1", "block_1"),
        OCRBlock("ocr_text_005", "2026级新生", [310, 263, 128, 30], 0.9987850189208984, "line_1", "block_2"),
        OCRBlock("ocr_text_026", "可视化选床，像高铁选座一样直观", [78, 1094, 377, 29], 0.9940683841705322, "line_2", "block_3"),
        OCRBlock("ocr_text_028", "预览选床界面", [95, 1205, 139, 30], 0.9985814094543457, "line_3", "block_4"),
        OCRBlock("ocr_text_032", "温馨提示", [92, 1320, 129, 30], 0.995962381362915, "line_4", "block_5"),
        OCRBlock("ocr_text_034", "选床确认后将无法自行修改，如需调整请联系辅导员。", [104, 1409, 467, 17], 0.9966685771942139, "line_5", "block_6"),
        OCRBlock("ocr_text_038", "我的", [743, 1574, 62, 39], 0.9999213218688965, "line_6", "block_7"),
    ]
    ocr = OCRDocument(
        version="0.1",
        taskId="task_home_real",
        provider="fake",
        model=None,
        imageSize={"width": 941, "height": 1672},
        coordinateSpace="pixel",
        blocks=blocks,
        warnings=[],
    )

    document = build_text_replacement_document(
        task_id="task_home_real",
        image=image,
        png_data=sample_path.read_bytes(),
        ocr_document=ocr,
        settings=settings,
    )

    decisions = {decision.ocrBlockId: decision for decision in document.decisions}
    assert decisions["ocr_text_004"].decision == "accepted"
    assert decisions["ocr_text_004"].application["status"] == "applied"
    assert decisions["ocr_text_004"].strategy["name"] == "pill_inner_background_sample"
    assert decisions["ocr_text_005"].decision == "accepted"
    assert decisions["ocr_text_005"].application["status"] == "applied"
    assert decisions["ocr_text_005"].strategy["name"] == "pill_inner_background_sample"
    assert decisions["ocr_text_026"].application["status"] == "applied"
    assert decisions["ocr_text_028"].application["status"] == "applied"
    assert decisions["ocr_text_032"].decision == "accepted"
    assert decisions["ocr_text_032"].reason == "solid_light_background_colored_text"
    assert decisions["ocr_text_032"].application["status"] == "applied"
    assert decisions["ocr_text_034"].application["status"] == "applied"
    assert decisions["ocr_text_038"].decision == "accepted"
    assert decisions["ocr_text_038"].application["status"] == "applied"
    assert decisions["ocr_text_038"].strategy["name"] == "bottom_nav_label_sample"


def test_unsupported_png_sampling_skips_replacement() -> None:
    settings = make_settings(text_replacement_mode="debug")
    image = PngMetadata(20, 20, 8, 3, 0, 0, 0)
    ocr = OCRDocument(
        version="0.1",
        taskId="task_1",
        provider="fake",
        model=None,
        imageSize={"width": 20, "height": 20},
        coordinateSpace="pixel",
        blocks=[OCRBlock("ocr_1", "Hello", [2, 10, 12, 8], 0.99, "line_1", "block_1")],
        warnings=[],
    )
    unsupported = bytearray(make_rgb_png(20, 20, (255, 255, 255)))
    unsupported[25] = 3

    document = build_text_replacement_document(
        task_id="task_1",
        image=image,
        png_data=bytes(unsupported),
        ocr_document=ocr,
        settings=settings,
    )

    assert document.status == "skipped"
    assert document.error is not None
    assert document.error["code"] == "png_sampling_unsupported"


def test_apply_text_replacements_keeps_existing_children() -> None:
    settings = make_settings(text_replacement_mode="apply")
    image = PngMetadata(100, 100, 8, 2, 0, 0, 0)
    ocr = OCRDocument(
        version="0.1",
        taskId="task_1",
        provider="fake",
        model=None,
        imageSize={"width": 100, "height": 100},
        coordinateSpace="pixel",
        blocks=[OCRBlock("ocr_1", "Hello", [10, 50, 40, 20], 0.99, "line_1", "block_1")],
        warnings=[],
    )
    document = build_text_replacement_document(
        task_id="task_1",
        image=image,
        png_data=make_text_fixture_png(100, 100, (247, 248, 250), [([10, 50, 40, 20], (20, 20, 20))]),
        ocr_document=ocr,
        settings=settings,
    )
    base_dsl = {
        "version": "0.1",
        "taskId": "task_1",
        "assets": [],
        "root": {
            "id": "root",
            "type": "frame",
            "layout": {"x": 0, "y": 0, "width": 100, "height": 100},
            "children": [
                {"id": "original_ref", "type": "image", "layout": {"x": 0, "y": 0, "width": 100, "height": 100}},
                {"id": "fallback_region_header", "type": "image", "layout": {"x": 0, "y": 0, "width": 100, "height": 40}},
                {"id": "text_ocr_1", "type": "text", "role": "candidate_text", "layout": {"x": 10, "y": 50, "width": 40, "height": 20}, "content": {"text": "Hello"}},
            ],
        },
        "meta": {"notes": "deterministic_region_dsl", "qualityFlags": ["m9_hidden_text_candidates"]},
    }

    enhanced = apply_text_replacements(base_dsl, document, ocr)
    children = {child["id"]: child for child in enhanced["root"]["children"]}

    assert {"original_ref", "fallback_region_header", "text_ocr_1"}.issubset(children)
    assert "cover_ocr_1" in children
    assert "visible_text_ocr_1" in children
    assert enhanced["meta"]["textReplacementCount"] == 1
    assert enhanced["meta"]["textReplacementAppliedCount"] == 1
    assert enhanced["meta"]["textReplacementBlockedCount"] == 0
    assert "m13_text_replacement_quality_control" in enhanced["meta"]["qualityFlags"]


def test_colored_background_with_light_text_is_accepted() -> None:
    settings = make_settings(text_replacement_mode="debug")
    image = PngMetadata(120, 90, 8, 2, 0, 0, 0)
    ocr = OCRDocument(
        version="0.1",
        taskId="task_1",
        provider="fake",
        model=None,
        imageSize={"width": 120, "height": 90},
        coordinateSpace="pixel",
        blocks=[OCRBlock("button", "确认选床", [24, 48, 72, 22], 0.99, "line_1", "block_1")],
        warnings=[],
    )

    document = build_text_replacement_document(
        task_id="task_1",
        image=image,
        png_data=make_text_fixture_png(120, 90, (38, 132, 255), [([24, 48, 72, 22], (255, 255, 255))]),
        ocr_document=ocr,
        settings=settings,
    )

    decision = document.decisions[0]
    assert decision.decision == "accepted"
    assert decision.reason == "dark_or_colored_background_light_text"
    assert decision.background is not None
    assert decision.foreground is not None
    assert decision.background["color"] == "#2684FF"
    assert decision.foreground["color"] == "#FFFFFF"
    assert document.meta["coloredBackgroundAcceptedCount"] == 1


def test_colored_background_can_be_disabled() -> None:
    settings = make_settings(text_replacement_mode="debug", text_replacement_enable_colored_bg=False)
    image = PngMetadata(120, 90, 8, 2, 0, 0, 0)
    ocr = OCRDocument(
        version="0.1",
        taskId="task_1",
        provider="fake",
        model=None,
        imageSize={"width": 120, "height": 90},
        coordinateSpace="pixel",
        blocks=[OCRBlock("button", "确认选床", [24, 48, 72, 22], 0.99, "line_1", "block_1")],
        warnings=[],
    )

    document = build_text_replacement_document(
        task_id="task_1",
        image=image,
        png_data=make_text_fixture_png(120, 90, (38, 132, 255), [([24, 48, 72, 22], (255, 255, 255))]),
        ocr_document=ocr,
        settings=settings,
    )

    assert document.decisions[0].decision == "rejected"
    assert document.decisions[0].reason == "dark_background"


def test_low_contrast_text_is_rejected() -> None:
    settings = make_settings(text_replacement_mode="debug")
    image = PngMetadata(100, 90, 8, 2, 0, 0, 0)
    ocr = OCRDocument(
        version="0.1",
        taskId="task_1",
        provider="fake",
        model=None,
        imageSize={"width": 100, "height": 90},
        coordinateSpace="pixel",
        blocks=[OCRBlock("low", "Low", [20, 48, 40, 20], 0.99, "line_1", "block_1")],
        warnings=[],
    )

    document = build_text_replacement_document(
        task_id="task_1",
        image=image,
        png_data=make_text_fixture_png(100, 90, (247, 248, 250), [([20, 48, 40, 20], (210, 211, 212))]),
        ocr_document=ocr,
        settings=settings,
    )

    assert document.decisions[0].reason == "foreground_background_low_contrast"


def test_text_color_uncertain_when_no_foreground_pixels() -> None:
    settings = make_settings(text_replacement_mode="debug")
    image = PngMetadata(100, 90, 8, 2, 0, 0, 0)
    ocr = OCRDocument(
        version="0.1",
        taskId="task_1",
        provider="fake",
        model=None,
        imageSize={"width": 100, "height": 90},
        coordinateSpace="pixel",
        blocks=[OCRBlock("empty", "Empty", [20, 48, 40, 20], 0.99, "line_1", "block_1")],
        warnings=[],
    )

    document = build_text_replacement_document(
        task_id="task_1",
        image=image,
        png_data=make_rgb_png(100, 90, (247, 248, 250)),
        ocr_document=ocr,
        settings=settings,
    )

    assert document.decisions[0].reason == "text_color_uncertain"


def test_split_ocr_blocks_on_same_line_are_merged() -> None:
    settings = make_settings(text_replacement_mode="debug")
    image = PngMetadata(180, 90, 8, 2, 0, 0, 0)
    ocr = OCRDocument(
        version="0.1",
        taskId="task_1",
        provider="fake",
        model=None,
        imageSize={"width": 180, "height": 90},
        coordinateSpace="pixel",
        blocks=[
            OCRBlock("left", "下一步：", [30, 48, 58, 22], 0.99, "line_1", "block_1"),
            OCRBlock("right", "确认选床", [94, 48, 64, 22], 0.98, "line_1", "block_2"),
        ],
        warnings=[],
    )

    document = build_text_replacement_document(
        task_id="task_1",
        image=image,
        png_data=make_text_fixture_png(180, 90, (38, 132, 255), [([30, 48, 128, 22], (255, 255, 255))]),
        ocr_document=ocr,
        settings=settings,
    )

    assert len(document.decisions) == 1
    decision = document.decisions[0]
    assert decision.ocrBlockId == "merged_left_right"
    assert decision.sourceOcrBlockIds == ["left", "right"]
    assert decision.bbox == [30, 48, 128, 22]
    assert document.meta["mergedBlockCount"] == 1
    assert any(warning.code == "OCR_BLOCKS_MERGED" for warning in document.warnings)


def test_unrelated_short_labels_are_not_merged() -> None:
    settings = make_settings(text_replacement_mode="debug")
    image = PngMetadata(180, 90, 8, 2, 0, 0, 0)
    ocr = OCRDocument(
        version="0.1",
        taskId="task_1",
        provider="fake",
        model=None,
        imageSize={"width": 180, "height": 90},
        coordinateSpace="pixel",
        blocks=[
            OCRBlock("a", "可选", [30, 48, 34, 22], 0.99, "line_1", "block_1"),
            OCRBlock("b", "已住", [70, 48, 34, 22], 0.98, "line_1", "block_2"),
        ],
        warnings=[],
    )

    document = build_text_replacement_document(
        task_id="task_1",
        image=image,
        png_data=make_text_fixture_png(180, 90, (247, 248, 250), [([30, 48, 34, 22], (20, 20, 20)), ([70, 48, 34, 22], (20, 20, 20))]),
        ocr_document=ocr,
        settings=settings,
    )

    assert [decision.ocrBlockId for decision in document.decisions] == ["a", "b"]


def test_visible_text_font_size_respects_bbox_width_for_chinese_labels() -> None:
    block = OCRBlock("ocr_text_021", "5号上铺", [183, 877, 98, 38], 0.99, "line_1", "block_1")

    assert visible_text_font_size(block.text, block.bbox) < round(block.bbox[3] * 0.75)
    assert build_visible_text_element(block)["style"]["fontSize"] == 25
    assert build_visible_text_element(block)["style"]["lineHeight"] >= 25


def create_client_with_env(monkeypatch, tmp_path, env: dict[str, str]) -> TestClient:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    for key, value in env.items():
        if value:
            monkeypatch.setenv(key, value)
        else:
            monkeypatch.delenv(key, raising=False)

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    return TestClient(main.create_app())


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "version": "0.1.0",
        "storage_root": None,
        "database_path": None,
        "public_base_url": "http://localhost:8000",
        "max_upload_bytes": 10 * 1024 * 1024,
        "cors_allow_origins": ["*"],
        "visual_primitive_provider": "fake",
        "ocr_provider": "fake",
        "dsl_patch_mode": "debug",
        "openai_api_key": None,
        "openai_vision_model": "gpt-5.5",
        "openai_timeout_seconds": 30,
        "ocr_min_confidence": 0.70,
        "text_replacement_mode": "debug",
        "text_replacement_max_blocks": 100,
        "text_replacement_min_confidence": 0.95,
        "text_replacement_solid_bg_tolerance": 18,
        "text_replacement_max_height": 64,
        "text_replacement_min_width": 12,
        "text_replacement_min_height": 10,
        "text_replacement_enable_colored_bg": True,
        "text_replacement_min_contrast": 90,
        "text_replacement_edge_sample_padding": 4,
        "text_replacement_text_sample_inset": 1,
    }
    values.update(overrides)
    return Settings(**values)


def make_rgb_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    rows = [bytes(rgb) * width for _ in range(height)]
    return make_png_from_rows(width, height, 2, rows)


def make_text_fixture_png(
    width: int,
    height: int,
    background_rgb: tuple[int, int, int],
    text_regions: list[tuple[list[int], tuple[int, int, int]]],
) -> bytes:
    rows = [bytearray(bytes(background_rgb) * width) for _ in range(height)]
    for bbox, text_rgb in text_regions:
        x, y, region_width, region_height = bbox
        x1 = max(0, x + 2)
        y1 = max(0, y + 2)
        x2 = min(width, x + region_width - 2)
        y2 = min(height, y + region_height - 2)
        for row_index in range(y1, y2):
            row = rows[row_index]
            for column in range(x1, x2, 3):
                offset = column * 3
                row[offset : offset + 3] = bytes(text_rgb)
    return make_png_from_rows(width, height, 2, [bytes(row) for row in rows])


def make_noisy_expanded_text_png(
    width: int,
    height: int,
    bbox: list[int],
    background_rgb: tuple[int, int, int],
    text_rgb: tuple[int, int, int],
) -> bytes:
    rows = [bytearray(bytes(background_rgb) * width) for _ in range(height)]
    x, y, region_width, region_height = bbox
    expanded = [max(0, x - 4), max(0, y - 4), min(width, x + region_width + 4), min(height, y + region_height + 4)]
    for row_index in range(expanded[1], expanded[3]):
        row = rows[row_index]
        for column in range(expanded[0], expanded[2]):
            if x <= column < x + region_width and y <= row_index < y + region_height:
                continue
            value = 255 if (row_index + column) % 2 == 0 else 0
            offset = column * 3
            row[offset : offset + 3] = bytes((value, value, value))
    draw_text_pixels(rows, width, height, bbox, text_rgb)
    return make_png_from_rows(width, height, 2, [bytes(row) for row in rows])


def make_legend_fixture_png(width: int, height: int, bboxes: list[list[int]]) -> bytes:
    rows = [bytearray(bytes((247, 248, 250)) * width) for _ in range(height)]
    for bbox in bboxes:
        x, y, region_width, region_height = bbox
        for row_index in range(max(0, y - 4), min(height, y + region_height + 4)):
            row = rows[row_index]
            for column in range(max(0, x - 4), min(width, x + region_width + 4)):
                if x <= column < x + region_width and y <= row_index < y + region_height:
                    continue
                offset = column * 3
                if column < x:
                    row[offset : offset + 3] = bytes((38, 132, 255))
                else:
                    value = 255 if (row_index + column) % 2 == 0 else 0
                    row[offset : offset + 3] = bytes((value, value, value))
        draw_text_pixels(rows, width, height, bbox, (20, 20, 20))
    return make_png_from_rows(width, height, 2, [bytes(row) for row in rows])


def draw_text_pixels(
    rows: list[bytearray],
    width: int,
    height: int,
    bbox: list[int],
    text_rgb: tuple[int, int, int],
) -> None:
    x, y, region_width, region_height = bbox
    x1 = max(0, x + 2)
    y1 = max(0, y + 2)
    x2 = min(width, x + region_width - 2)
    y2 = min(height, y + region_height - 2)
    for row_index in range(y1, y2):
        row = rows[row_index]
        for column in range(x1, x2, 3):
            offset = column * 3
            row[offset : offset + 3] = bytes(text_rgb)


def make_checker_png(width: int, height: int) -> bytes:
    rows = []
    for row_index in range(height):
        row = bytearray()
        for column in range(width):
            value = 255 if (row_index + column) % 2 == 0 else 0
            row.extend([value, value, value])
        rows.append(bytes(row))
    return make_png_from_rows(width, height, 2, rows)


def make_png_from_rows(width: int, height: int, color_type: int, rows: list[bytes]) -> bytes:
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    idat_data = zlib.compress(b"".join(b"\x00" + row for row in rows))
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            png_chunk(b"IHDR", ihdr_data),
            png_chunk(b"IDAT", idat_data),
            png_chunk(b"IEND", b""),
        ]
    )
