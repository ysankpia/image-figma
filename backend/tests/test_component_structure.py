from __future__ import annotations

import importlib
import sys
from typing import Any

from fastapi.testclient import TestClient

from app.component_structure import (
    apply_component_structure_metadata,
    build_component_structure_document,
    build_failed_component_structure_document,
)
from app.png_tools import PngMetadata
from test_text_binding import (
    fake_primitive_document,
    make_binding_settings,
    ocr_document,
    with_upstream_facts,
)
from test_text_replacement import make_text_fixture_png
from app.ocr import OCRBlock
from app.text_binding import build_text_binding_document
from app.text_replacement import build_text_replacement_document
from conftest import PNG_BYTES


def test_component_structure_default_upload_creates_report_and_dsl_meta(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(monkeypatch, tmp_path, {"TEXT_REPLACEMENT_MODE": "apply"})

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/component-structures")
        assert response.status_code == 200
        structure = response.json()["data"]
        assert structure["status"] == "completed"
        assert structure["meta"]["notes"] == "component_structure_harness"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m16_component_structure_harness" in dsl["meta"]["qualityFlags"]
        assert dsl["meta"]["componentStructureCount"] == structure["meta"]["componentCount"]
        assert dsl["meta"]["componentStructureGroupCount"] == structure["meta"]["groupCount"]
        assert dsl["meta"]["componentStructureUnstructuredCount"] == structure["meta"]["unstructuredCount"]


def test_component_structure_disabled_has_no_result_and_keeps_m15_dsl(monkeypatch, tmp_path) -> None:
    client = create_client_with_env(
        monkeypatch,
        tmp_path,
        {
            "TEXT_REPLACEMENT_MODE": "apply",
            "COMPONENT_STRUCTURE_ENABLED": "false",
        },
    )

    with client:
        upload = client.post("/api/upload", files={"file": ("input.png", PNG_BYTES, "image/png")})
        assert upload.status_code == 200
        task_id = upload.json()["data"]["taskId"]

        response = client.get(f"/api/tasks/{task_id}/component-structures")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "COMPONENT_STRUCTURE_NOT_FOUND"

        dsl = client.get(f"/api/tasks/{task_id}/dsl").json()["data"]["dsl"]
        assert "m15_text_primitive_binding" in dsl["meta"]["qualityFlags"]
        assert "m16_component_structure_harness" not in dsl["meta"]["qualityFlags"]
        assert "componentStructureCount" not in dsl["meta"]


def test_component_structure_endpoint_errors(client: TestClient) -> None:
    missing = client.get("/api/tasks/task_missing/component-structures")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "TASK_NOT_FOUND"

    from app.state import state

    state.database.insert_task(
        {
            "id": "task_without_structure",
            "status": "completed",
            "stage": "completed",
            "progress": 100,
            "message": "No component structure.",
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
    not_found = client.get("/api/tasks/task_without_structure/component-structures")
    assert not_found.status_code == 404
    assert not_found.json()["error"]["code"] == "COMPONENT_STRUCTURE_NOT_FOUND"

    state.database.insert_component_structure_result(
        {
            "task_id": "task_without_structure",
            "status": "completed",
            "structure_path": "/tmp/does-not-exist.json",
            "component_count": 0,
            "group_count": 0,
            "unstructured_count": 0,
            "warning_count": 0,
            "error_code": None,
            "error_message": None,
            "created_at": "2026-05-16T00:00:00+00:00",
        }
    )
    missing_file = client.get("/api/tasks/task_without_structure/component-structures")
    assert missing_file.status_code == 404
    assert missing_file.json()["error"]["code"] == "COMPONENT_STRUCTURE_NOT_FOUND"


def test_home_like_component_structure_rules_cover_m16_components_and_groups() -> None:
    image, ocr, replacement, binding = home_like_binding_document()
    document = build_component_structure_document(
        task_id="task_home",
        image=image,
        ocr_document=ocr,
        primitive_document=fake_primitive_document("task_home", image),
        replacement_document=replacement,
        binding_document=binding,
        dsl={"root": {"children": []}},
        settings=make_component_settings(),
    )

    assert document.status == "completed"
    by_role = {component.role: [] for component in document.components}
    for component in document.components:
        by_role.setdefault(component.role, []).append(component)

    assert len(by_role["page_header"]) == 1
    assert len(by_role["hero_profile"]) == 1
    assert len(by_role["activity_card"]) == 1
    assert len(by_role["summary_stat_card"]) == 3
    assert len(by_role["primary_button"]) == 1
    assert len(by_role["outline_button"]) == 1
    assert len(by_role["shortcut_card"]) == 4
    assert len(by_role["preview_card"]) == 1
    assert len(by_role["legend_group"]) == 1
    assert len(by_role["tip_card"]) == 1
    assert len(by_role["bottom_nav_item"]) == 3

    hero = by_role["hero_profile"][0]
    assert any(container_id.startswith("container_badge_") for container_id in hero.containerIds)
    activity = by_role["activity_card"][0]
    assert any("status_badge" in container_id for container_id in activity.containerIds)
    assert activity.relationships["card_title"]
    assert activity.relationships["card_subtitle"]

    groups = {group.role: group for group in document.groups}
    assert groups["summary_stat_group"].layout["pattern"] == "three_column_row"
    assert len(groups["summary_stat_group"].componentIds) == 3
    assert groups["shortcut_grid"].layout["pattern"] == "grid_2x2"
    assert len(groups["shortcut_grid"].componentIds) == 4
    assert groups["preview_section"].layout["pattern"] == "vertical_stack"
    assert groups["bottom_nav_group"].layout["pattern"] == "bottom_nav_row"
    assert len(groups["bottom_nav_group"].componentIds) == 3
    assert groups["page_structure"].layout["pattern"] == "vertical_stack"

    assert document.meta["componentCount"] == len(document.components)
    assert document.meta["groupCount"] == len(document.groups)
    assert document.meta["roleSummary"]["summary_stat_card"] == 3
    assert document.meta["groupRoleSummary"]["shortcut_grid"] == 1
    assert document.meta["layoutSummary"]["grid_2x2"] == 1


def test_low_confidence_component_container_is_unstructured() -> None:
    image, ocr, replacement, binding = home_like_binding_document()
    document = build_component_structure_document(
        task_id="task_home",
        image=image,
        ocr_document=ocr,
        primitive_document=fake_primitive_document("task_home", image),
        replacement_document=replacement,
        binding_document=binding,
        dsl={"root": {"children": []}},
        settings=make_component_settings(component_structure_min_confidence=1.0),
    )

    assert document.components == []
    assert document.groups == []
    assert document.unstructuredContainerIds


def test_component_structure_skips_when_binding_not_completed() -> None:
    image, ocr, replacement, binding = home_like_binding_document()
    binding.status = "failed"
    document = build_component_structure_document(
        task_id="task_home",
        image=image,
        ocr_document=ocr,
        primitive_document=fake_primitive_document("task_home", image),
        replacement_document=replacement,
        binding_document=binding,
        dsl={"root": {"children": []}},
        settings=make_component_settings(),
    )

    assert document.status == "skipped"
    assert document.error is not None
    assert document.error["code"] == "text_binding_not_completed"


def test_component_structure_failed_document_does_not_change_dsl_meta() -> None:
    image = PngMetadata(100, 100, 8, 2, 0, 0, 0)
    document = build_failed_component_structure_document(
        task_id="task_failed",
        image=image,
        code="COMPONENT_STRUCTURE_VALIDATION_FAILED",
        message="Component structure validation failed.",
    )
    dsl = {"meta": {"qualityFlags": ["m15_text_primitive_binding"]}, "root": {"children": []}}

    next_dsl = apply_component_structure_metadata(dsl, document)

    assert next_dsl == dsl


def home_like_binding_document():
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
        OCRBlock("ocr_text_019", "选床规则", [602, 831, 118, 36], 0.999, "line_4", "block_5b"),
        OCRBlock("ocr_text_020", "查看我的床位信息", [187, 871, 178, 29], 0.999, "line_5", "block_6"),
        OCRBlock("ocr_text_021", "了解选床规则与说明", [605, 871, 199, 29], 0.999, "line_5", "block_6b"),
        OCRBlock("ocr_text_022", "楼层分布", [187, 947, 117, 37], 0.999, "line_5", "block_6c"),
        OCRBlock("ocr_text_023", "选床记录", [602, 947, 118, 37], 0.999, "line_5", "block_6d"),
        OCRBlock("ocr_text_024", "查看楼层与房间分布", [187, 989, 200, 30], 0.999, "line_5", "block_6e"),
        OCRBlock("ocr_text_025", "查看我的选床记录", [602, 988, 180, 29], 0.999, "line_5", "block_6f"),
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
        settings=make_component_settings(text_replacement_mode="apply"),
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
    binding = build_text_binding_document(
        task_id="task_home",
        image=image,
        ocr_document=ocr,
        primitive_document=primitive_document,
        replacement_document=replacement,
        dsl={"root": {"children": []}},
        settings=make_component_settings(),
    )
    return image, ocr, replacement, binding


def create_client_with_env(monkeypatch, tmp_path, env: dict[str, str]) -> TestClient:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("DATABASE_PATH", str(storage_root / "app.db"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    main = importlib.import_module("app.main")
    return TestClient(main.create_app())


def make_component_settings(**overrides: Any):
    values = {
        "component_structure_enabled": True,
        "component_structure_min_confidence": 0.70,
    }
    values.update(overrides)
    return make_binding_settings(**values)
