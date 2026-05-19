from __future__ import annotations

import importlib
import sys
from typing import Any

from fastapi.testclient import TestClient

from app.config import Settings
from app.ocr import OCRBlock, OCRDocument
from app.png_tools import PngMetadata
from app.text_binding import build_text_binding_document
from app.text_replacement import TextReplacementDecision, build_text_replacement_document
from app.visual_primitives import VisualPrimitive, VisualPrimitiveDocument
from conftest import PNG_BYTES
from test_text_replacement import make_settings, make_text_fixture_png


def test_text_binding_default_upload_creates_report_and_dsl_meta(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(monkeypatch, tmp_path, {"TEXT_REPLACEMENT_MODE": "apply"})

    with client:
        png = make_text_fixture_png(
            317,
            2729,
            (247, 248, 250),
            [
                ([25, 109, 143, 36], (20, 20, 20)),
                ([25, 157, 190, 32], (20, 20, 20)),
            ],
        )
        upload = client.post("/api/upload", files={"file": ("input.png", png, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/text-bindings")
        assert response.status_code == 200
        binding = response.json()["data"]
        assert binding["status"] == "completed"
        assert binding["meta"]["notes"] == "text_primitive_binding_harness"
        assert binding["meta"]["boundCount"] == 1
        assert binding["meta"]["containerCount"] == 4
        assert binding["meta"]["unboundCount"] == 1

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        roles = [child.get("role") for child in dsl["root"]["children"]]
        assert roles.count("visible_text_replacement") == 1
        assert "m15_text_primitive_binding" in dsl["meta"]["qualityFlags"]
        assert dsl["meta"]["textPrimitiveBindingCount"] == binding["meta"]["boundCount"]
        assert dsl["meta"]["textPrimitiveContainerCount"] == binding["meta"]["containerCount"]
        assert dsl["meta"]["textPrimitiveUnboundCount"] == binding["meta"]["unboundCount"]


def test_text_binding_disabled_has_no_result_and_keeps_m14_dsl(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(
        monkeypatch,
        tmp_path,
        {
            "TEXT_REPLACEMENT_MODE": "apply",
            "TEXT_BINDING_ENABLED": "false",
        },
    )

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/text-bindings")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "TEXT_BINDING_NOT_FOUND"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m15_text_primitive_binding" not in dsl["meta"].get("qualityFlags", [])
        assert "textPrimitiveBindingCount" not in dsl["meta"]


def test_missing_task_text_bindings_returns_task_not_found(legacy_client: TestClient) -> None:
    response = legacy_client.get("/api/tasks/task_missing/text-bindings")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TASK_NOT_FOUND"


def test_existing_task_without_text_bindings_returns_not_found(legacy_client: TestClient) -> None:
    from app.state import state

    state.database.insert_task(
        {
            "id": "task_without_bindings",
            "status": "completed",
            "stage": "completed",
            "progress": 100,
            "message": "No text bindings.",
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

    response = legacy_client.get("/api/tasks/task_without_bindings/text-bindings")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TEXT_BINDING_NOT_FOUND"


def test_home_like_text_binding_rules_cover_m15_roles() -> None:
    image = PngMetadata(941, 1672, 8, 2, 0, 0, 0)
    blocks = [
        OCRBlock("ocr_text_002", "宿舍选床", [396, 82, 147, 42], 0.999, "line_0", "block_0"),
        OCRBlock("ocr_text_003", "你好，张同学", [195, 202, 229, 47], 0.999, "line_0", "block_0b"),
        OCRBlock("ocr_text_004", "男生", [213, 261, 55, 33], 0.999, "line_1", "block_1"),
        OCRBlock("ocr_text_005", "2026级新生", [310, 263, 128, 30], 0.998, "line_1", "block_2"),
        OCRBlock("ocr_text_006", "2026级新生宿舍选床", [71, 367, 349, 37], 0.999, "line_2", "block_2b"),
        OCRBlock("ocr_text_007", "进行中", [472, 369, 78, 32], 0.999, "line_2", "block_3"),
        OCRBlock("ocr_text_008", "2026.06.0109:00-2026.06.0818:00", [107, 430, 421, 25], 0.999, "line_2", "block_3b"),
        OCRBlock("ocr_text_009", "根据个人情况选择宿舍楼层、房间与床位", [104, 477, 422, 25], 0.999, "line_2", "block_3c"),
        OCRBlock("ocr_text_010", "可选楼层", [180, 566, 98, 31], 0.999, "line_2", "block_3d"),
        OCRBlock("ocr_text_011", "可选房间", [458, 566, 97, 31], 0.999, "line_2", "block_3e"),
        OCRBlock("ocr_text_012", "剩余床位", [737, 566, 98, 31], 0.999, "line_2", "block_3f"),
        OCRBlock("ocr_text_013", "3层", [170, 598, 86, 62], 0.999, "line_2", "block_3g"),
        OCRBlock("ocr_text_014", "18间", [452, 598, 101, 59], 0.999, "line_2", "block_3h"),
        OCRBlock("ocr_text_015", "42个", [731, 598, 106, 61], 0.999, "line_2", "block_3i"),
        OCRBlock("ocr_text_016", "开始选床", [411, 712, 143, 48], 0.999, "line_3", "block_4"),
        OCRBlock("ocr_text_018", "我的床位", [185, 831, 119, 36], 0.999, "line_4", "block_5"),
        OCRBlock("ocr_text_020", "查看我的床位信息", [187, 871, 178, 29], 0.999, "line_5", "block_6"),
        OCRBlock("ocr_text_026", "可视化选床，像高铁选座一样直观", [78, 1094, 377, 29], 0.999, "line_6", "block_7"),
        OCRBlock("ocr_text_027", "楼层→房间→床位，清晰一目了然", [78, 1141, 367, 24], 0.999, "line_7", "block_8"),
        OCRBlock("ocr_text_028", "预览选床界面", [95, 1205, 139, 30], 0.999, "line_8", "block_9"),
        OCRBlock("ocr_text_029", "可选", [519, 1221, 48, 26], 0.999, "line_9", "block_10"),
        OCRBlock("ocr_text_030", "已选", [630, 1221, 46, 26], 0.999, "line_9", "block_11"),
        OCRBlock("ocr_text_031", "不可选", [739, 1221, 65, 26], 0.999, "line_9", "block_12"),
        OCRBlock("ocr_text_032", "温馨提示", [92, 1320, 129, 30], 0.999, "line_10", "block_13"),
        OCRBlock("ocr_text_033", "请仅选择与本人性别匹配的楼层进行选床。", [102, 1367, 374, 23], 0.999, "line_11", "block_14"),
        OCRBlock("ocr_text_036", "首页", [128, 1580, 59, 33], 0.999, "line_12", "block_15"),
        OCRBlock("ocr_text_037", "选床", [429, 1578, 61, 33], 0.999, "line_12", "block_16"),
        OCRBlock("ocr_text_038", "我的", [743, 1574, 62, 39], 0.999, "line_12", "block_17"),
    ]
    ocr = ocr_document("task_home", image, blocks)
    replacement = build_text_replacement_document(
        task_id="task_home",
        image=image,
        png_data=make_text_fixture_png(941, 1672, (247, 248, 250), [(block.bbox, (20, 20, 20)) for block in blocks]),
        ocr_document=ocr,
        settings=make_settings(text_replacement_mode="apply"),
    )
    replacement.decisions = [
        with_upstream_facts(
            decision,
            reason="dark_or_colored_background_light_text",
            background="#3482F6",
            foreground="#FFFFFF",
        )
        if decision.ocrBlockId == "ocr_text_016"
        else with_upstream_facts(decision, strategy="outline_button_text_sample")
        if decision.ocrBlockId == "ocr_text_028"
        else decision
        for decision in replacement.decisions
    ]
    primitive_document = fake_primitive_document("task_home", image)

    document = build_text_binding_document(
        task_id="task_home",
        image=image,
        ocr_document=ocr,
        primitive_document=primitive_document,
        replacement_document=replacement,
        dsl={"root": {"children": []}},
        settings=make_binding_settings(),
    )

    by_text = {binding.text: binding for binding in document.bindings}
    assert by_text["宿舍选床"].containerRole == "page_header"
    assert by_text["宿舍选床"].relationship == "section_title"
    assert by_text["你好，张同学"].containerRole == "hero_profile"
    assert by_text["2026级新生宿舍选床"].containerRole == "activity_card"
    assert by_text["2026级新生宿舍选床"].relationship == "card_title"
    assert by_text["男生"].containerRole == "badge"
    assert by_text["男生"].relationship == "badge_label"
    assert by_text["2026级新生"].containerRole == "badge"
    assert by_text["进行中"].containerRole == "status_badge"
    assert by_text["进行中"].relationship == "status_label"
    assert all(by_text[text].containerRole == "activity_card" for text in ["2026.06.0109:00-2026.06.0818:00", "根据个人情况选择宿舍楼层、房间与床位"])
    assert all(by_text[text].relationship == "card_subtitle" for text in ["2026.06.0109:00-2026.06.0818:00", "根据个人情况选择宿舍楼层、房间与床位"])
    assert all(by_text[text].containerRole == "summary_stat_card" for text in ["可选楼层", "可选房间", "剩余床位", "3层", "18间", "42个"])
    assert all(by_text[text].relationship == "card_subtitle" for text in ["可选楼层", "可选房间", "剩余床位"])
    assert all(by_text[text].relationship == "card_title" for text in ["3层", "18间", "42个"])
    assert not any(by_text[text].containerRole == "primary_button" for text in ["可选楼层", "可选房间", "剩余床位", "3层", "18间", "42个"])
    assert by_text["开始选床"].containerRole == "primary_button"
    assert by_text["开始选床"].relationship == "button_label"
    assert by_text["我的床位"].containerRole == "shortcut_card"
    assert by_text["我的床位"].relationship == "card_title"
    assert by_text["查看我的床位信息"].containerRole == "shortcut_card"
    assert by_text["可视化选床，像高铁选座一样直观"].containerRole == "preview_card"
    assert by_text["可视化选床，像高铁选座一样直观"].relationship == "card_title"
    assert by_text["预览选床界面"].containerRole == "outline_button"
    assert by_text["预览选床界面"].relationship == "button_label"
    assert {by_text[text].containerId for text in ["可选", "已选", "不可选"]} == {"container_legend_group_001"}
    assert all(by_text[text].relationship == "legend_label" for text in ["可选", "已选", "不可选"])
    assert by_text["温馨提示"].containerRole == "tip_card"
    assert by_text["请仅选择与本人性别匹配的楼层进行选床。"].containerRole == "tip_card"
    assert all(by_text[text].containerRole == "bottom_nav_item" for text in ["首页", "选床", "我的"])
    assert document.meta["roleSummary"]["page_header"] == 1
    assert document.meta["roleSummary"]["hero_profile"] == 1
    assert document.meta["roleSummary"]["activity_card"] == 1
    assert document.meta["roleSummary"]["summary_stat_card"] == 3
    assert document.meta["roleSummary"]["outline_button"] == 1
    assert document.meta["roleSummary"]["legend_group"] == 1
    assert document.meta["relationshipSummary"]["nav_label"] == 3


def test_primary_button_requires_action_background_and_does_not_bind_summary_stats() -> None:
    image = PngMetadata(420, 800, 8, 2, 0, 0, 0)
    blocks = [
        OCRBlock("label_a", "Label A", [60, 220, 86, 24], 0.999, "line_1", "block_1"),
        OCRBlock("label_b", "Label B", [250, 220, 86, 24], 0.999, "line_1", "block_2"),
        OCRBlock("value_a", "12", [70, 254, 64, 54], 0.999, "line_2", "block_3"),
        OCRBlock("value_b", "34", [260, 254, 68, 54], 0.999, "line_2", "block_4"),
        OCRBlock("action", "Action", [166, 360, 90, 40], 0.999, "line_3", "block_5"),
    ]
    ocr = ocr_document("task_stats", image, blocks)
    replacement = build_text_replacement_document(
        task_id="task_stats",
        image=image,
        png_data=make_text_fixture_png(
            420,
            800,
            (247, 248, 250),
            [
                (blocks[0].bbox, (70, 70, 80)),
                (blocks[1].bbox, (70, 70, 80)),
                (blocks[2].bbox, (20, 20, 25)),
                (blocks[3].bbox, (20, 20, 25)),
                (blocks[4].bbox, (255, 255, 255)),
            ],
        ),
        ocr_document=ocr,
        settings=make_settings(text_replacement_mode="apply"),
    )
    replacement.decisions = [
        with_upstream_facts(
            decision,
            reason="dark_or_colored_background_light_text",
            background="#3482F6",
            foreground="#FFFFFF",
        )
        if decision.ocrBlockId == "action"
        else decision
        for decision in replacement.decisions
    ]

    document = build_text_binding_document(
        task_id="task_stats",
        image=image,
        ocr_document=ocr,
        primitive_document=fake_primitive_document("task_stats", image),
        replacement_document=replacement,
        dsl={"root": {"children": []}},
        settings=make_binding_settings(),
    )

    by_id = {binding.ocrBlockId: binding for binding in document.bindings}
    assert by_id["action"].containerRole == "primary_button"
    assert by_id["action"].relationship == "button_label"
    assert all(by_id[item].containerRole == "summary_stat_card" for item in ["label_a", "label_b", "value_a", "value_b"])
    assert all(by_id[item].relationship == "card_subtitle" for item in ["label_a", "label_b"])
    assert all(by_id[item].relationship == "card_title" for item in ["value_a", "value_b"])


def test_card_relationship_uses_row_order_and_relative_size_not_absolute_height() -> None:
    image = PngMetadata(360, 900, 8, 2, 0, 0, 0)
    blocks = [
        OCRBlock("title", "Card Title", [60, 470, 120, 22], 0.999, "line_1", "block_1"),
        OCRBlock("subtitle", "Card subtitle text", [60, 505, 188, 34], 0.999, "line_2", "block_2"),
    ]
    ocr = ocr_document("task_card_order", image, blocks)
    replacement = build_text_replacement_document(
        task_id="task_card_order",
        image=image,
        png_data=make_text_fixture_png(
            360,
            900,
            (247, 248, 250),
            [(blocks[0].bbox, (20, 20, 25)), (blocks[1].bbox, (90, 90, 100))],
        ),
        ocr_document=ocr,
        settings=make_settings(text_replacement_mode="apply"),
    )

    document = build_text_binding_document(
        task_id="task_card_order",
        image=image,
        ocr_document=ocr,
        primitive_document=fake_primitive_document("task_card_order", image),
        replacement_document=replacement,
        dsl={"root": {"children": []}},
        settings=make_binding_settings(),
    )

    by_id = {binding.ocrBlockId: binding for binding in document.bindings}
    assert by_id["title"].containerRole == "shortcut_card"
    assert by_id["title"].relationship == "card_title"
    assert by_id["subtitle"].containerRole == "shortcut_card"
    assert by_id["subtitle"].relationship == "card_subtitle"


def test_low_confidence_binding_candidate_is_unbound() -> None:
    image = PngMetadata(320, 1000, 8, 2, 0, 0, 0)
    blocks = [OCRBlock("button", "开始选床", [120, 500, 90, 32], 0.99, "line_1", "block_1")]
    ocr = ocr_document("task_low_binding", image, blocks)
    replacement = build_text_replacement_document(
        task_id="task_low_binding",
        image=image,
        png_data=make_text_fixture_png(320, 1000, (247, 248, 250), [([120, 500, 90, 32], (20, 20, 20))]),
        ocr_document=ocr,
        settings=make_settings(text_replacement_mode="apply"),
    )

    document = build_text_binding_document(
        task_id="task_low_binding",
        image=image,
        ocr_document=ocr,
        primitive_document=fake_primitive_document("task_low_binding", image),
        replacement_document=replacement,
        dsl={"root": {"children": []}},
        settings=make_binding_settings(text_binding_min_confidence=1.0),
    )

    assert document.bindings == []
    assert document.unboundTextIds == ["button"]


def test_text_binding_skips_when_replacement_not_completed() -> None:
    image = PngMetadata(100, 100, 8, 2, 0, 0, 0)
    ocr = ocr_document("task_skip", image, [])
    replacement = build_text_replacement_document(
        task_id="task_skip",
        image=image,
        png_data=make_text_fixture_png(100, 100, (247, 248, 250), []),
        ocr_document=ocr,
        settings=make_settings(text_replacement_mode="debug"),
    )
    replacement.status = "failed"

    document = build_text_binding_document(
        task_id="task_skip",
        image=image,
        ocr_document=ocr,
        primitive_document=fake_primitive_document("task_skip", image),
        replacement_document=replacement,
        dsl={"root": {"children": []}},
        settings=make_binding_settings(),
    )

    assert document.status == "skipped"
    assert document.error is not None
    assert document.error["code"] == "text_replacement_not_completed"


def create_client_with_env(monkeypatch, tmp_path, env: dict[str, str]) -> TestClient:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("LEGACY_PRE_M29_UPLOAD_ENABLED", "true")
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    return TestClient(main.create_app())


def ocr_document(task_id: str, image: PngMetadata, blocks: list[OCRBlock]) -> OCRDocument:
    return OCRDocument(
        version="0.1",
        taskId=task_id,
        provider="fake",
        model=None,
        imageSize={"width": image.width, "height": image.height},
        coordinateSpace="pixel",
        blocks=blocks,
        warnings=[],
    )


def fake_primitive_document(task_id: str, image: PngMetadata) -> VisualPrimitiveDocument:
    return VisualPrimitiveDocument(
        version="0.1",
        taskId=task_id,
        provider="fake",
        model=None,
        imageSize={"width": image.width, "height": image.height},
        coordinateSpace="pixel",
        primitives=[
            VisualPrimitive("vp_region_header", "region", "Header", [0, 0, image.width, 234], 1, "header"),
            VisualPrimitive("vp_region_content", "region", "Content", [0, 234, image.width, max(1, image.height - 435)], 1, "content"),
            VisualPrimitive("vp_region_bottom", "region", "Bottom", [0, max(0, image.height - 201), image.width, 201], 1, "bottom"),
        ],
        relations=[],
        warnings=[],
    )


def make_binding_settings(**overrides: Any) -> Settings:
    values = make_settings().__dict__
    values.update(
        {
            "text_binding_enabled": True,
            "text_binding_min_confidence": 0.70,
        }
    )
    values.update(overrides)
    return Settings(**values)


def with_upstream_facts(
    decision: TextReplacementDecision,
    *,
    reason: str | None = None,
    background: str | None = None,
    foreground: str | None = None,
    strategy: str | None = None,
) -> TextReplacementDecision:
    if reason is not None:
        decision.reason = reason
        decision.decision = "accepted"
    if background is not None and decision.background is not None:
        decision.background["color"] = background
    if foreground is not None and decision.foreground is not None:
        decision.foreground["color"] = foreground
        decision.foreground["brightness"] = 255
        decision.foreground["contrast"] = max(float(decision.foreground.get("contrast", 0)), 140.0)
    if strategy is not None:
        decision.strategy = {
            "name": strategy,
            "acceptedBy": "m14_ui_aware_sampling",
            "attempts": [
                {
                    "name": strategy,
                    "status": "accepted",
                    "reason": decision.reason,
                }
            ],
        }
    decision.quality["applyEligible"] = True
    decision.application = {"status": "applied", "reason": "quality_gate_passed"}
    return decision
