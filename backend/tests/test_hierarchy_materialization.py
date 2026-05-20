from __future__ import annotations

import json
from pathlib import Path

from app.hierarchy_materialization import M38Options, materialize_m38_hierarchy


def test_m38_safe_direct_match_unit_creates_container_with_zero_absolute_drift(tmp_path: Path) -> None:
    dsl_path = write_json(tmp_path / "m30.json", base_dsl())
    report_path = write_json(
        tmp_path / "m37.json",
        m37_report(
            [
                unit_report(
                    "unit_1",
                    [10, 20, 120, 40],
                    [
                        direct_match("text_1", [12, 24, 40, 16]),
                        direct_match("text_2", [70, 24, 40, 16]),
                    ],
                )
            ]
        ),
    )

    result = materialize_m38_hierarchy(
        m30_dsl_path=str(dsl_path),
        m37_report_path=str(report_path),
        output_dir=tmp_path / "m38",
        flat_dsl_output_path=str(tmp_path / "m30_flat.json"),
        final_dsl_output_path=str(tmp_path / "m30_final.json"),
    )

    summary = result.report["summary"]
    assert summary["createdContainerCount"] == 1
    assert summary["movedChildCount"] == 2
    assert summary["absolutePositionViolationCount"] == 0
    assert summary["fallbackMovedCount"] == 0
    assert summary["assetChanged"] is False

    root_children = result.dsl["root"]["children"]
    assert [child["id"] for child in root_children] == ["original_ref", "fallback_full_image", "m38_container_unit_1", "image_outside"]
    container = root_children[2]
    assert container["type"] == "group"
    assert container["role"] == "m38_container"
    assert container["style"] == {"fill": None, "clipContent": False}
    assert [child["id"] for child in container["children"]] == ["text_1", "text_2"]
    assert container["children"][0]["rawLayout"] == {"x": 12, "y": 24, "width": 40, "height": 16}
    assert container["children"][0]["layout"] == {"x": 2, "y": 4, "width": 40, "height": 16}
    assert container["children"][0]["meta"]["m38ParentContainerId"] == "m38_container_unit_1"
    assert container["children"][0]["meta"]["m38OriginalPageBBox"] == [12, 24, 40, 16]
    assert (tmp_path / "m30_flat.json").exists()
    assert (tmp_path / "m30_final.json").exists()
    assert (tmp_path / "m38" / "hierarchy_materialization_report.json").exists()


def test_m38_ignores_geometry_only_matches_and_leaves_dsl_unchanged(tmp_path: Path) -> None:
    dsl_path = write_json(tmp_path / "m30.json", base_dsl())
    report_path = write_json(
        tmp_path / "m37.json",
        m37_report(
            [
                unit_report(
                    "unit_1",
                    [10, 20, 120, 40],
                    [
                        geometry_match("text_1", [12, 24, 40, 16]),
                        geometry_match("text_2", [70, 24, 40, 16]),
                    ],
                )
            ]
        ),
    )

    result = materialize_m38_hierarchy(m30_dsl_path=str(dsl_path), m37_report_path=str(report_path), output_dir=tmp_path / "m38")

    assert result.report["summary"]["ignoredGeometryMatchCount"] == 2
    assert result.report["summary"]["createdContainerCount"] == 0
    assert result.report["summary"]["dslChanged"] is False
    assert result.dsl == base_dsl()


def test_m38_never_moves_fallback_or_original_reference(tmp_path: Path) -> None:
    dsl_path = write_json(tmp_path / "m30.json", base_dsl())
    report_path = write_json(
        tmp_path / "m37.json",
        m37_report(
            [
                unit_report(
                    "unit_1",
                    [0, 0, 200, 120],
                    [
                        direct_match("original_ref", [0, 0, 200, 120]),
                        direct_match("fallback_full_image", [0, 0, 200, 120]),
                        direct_match("text_1", [12, 24, 40, 16]),
                        direct_match("text_2", [70, 24, 40, 16]),
                    ],
                )
            ]
        ),
    )

    result = materialize_m38_hierarchy(m30_dsl_path=str(dsl_path), m37_report_path=str(report_path), output_dir=tmp_path / "m38")

    assert result.report["summary"]["createdContainerCount"] == 1
    assert result.report["summary"]["fallbackMovedCount"] == 0
    assert result.report["summary"]["originalReferenceMovedCount"] == 0
    assert [child["id"] for child in result.dsl["root"]["children"][:3]] == ["original_ref", "fallback_full_image", "m38_container_unit_1"]
    moved_ids = [child["id"] for child in result.dsl["root"]["children"][2]["children"]]
    assert moved_ids == ["text_1", "text_2"]


def test_m38_skips_interleaved_z_order_risk(tmp_path: Path) -> None:
    dsl = base_dsl()
    dsl["root"]["children"].insert(3, m30_text("text_between", [50, 24, 10, 16], "Between"))
    dsl_path = write_json(tmp_path / "m30.json", dsl)
    report_path = write_json(
        tmp_path / "m37.json",
        m37_report(
            [
                unit_report(
                    "unit_1",
                    [10, 20, 120, 40],
                    [
                        direct_match("text_1", [12, 24, 40, 16]),
                        direct_match("text_2", [70, 24, 40, 16]),
                    ],
                )
            ]
        ),
    )

    result = materialize_m38_hierarchy(m30_dsl_path=str(dsl_path), m37_report_path=str(report_path), output_dir=tmp_path / "m38")

    assert result.report["summary"]["createdContainerCount"] == 0
    assert result.report["summary"]["skipReasonCounts"]["interleaved_z_order_risk"] == 1
    assert result.dsl == dsl


def test_m38_prevents_duplicate_claims_and_honors_max_containers(tmp_path: Path) -> None:
    dsl = base_dsl()
    dsl["root"]["children"].extend([m30_text("text_3", [150, 24, 30, 16], "C"), m30_text("text_4", [185, 24, 30, 16], "D")])
    dsl_path = write_json(tmp_path / "m30.json", dsl)
    report_path = write_json(
        tmp_path / "m37.json",
        m37_report(
            [
                unit_report("unit_1", [10, 20, 120, 40], [direct_match("text_1", [12, 24, 40, 16]), direct_match("text_2", [70, 24, 40, 16])]),
                unit_report("unit_2", [10, 20, 120, 40], [direct_match("text_1", [12, 24, 40, 16]), direct_match("text_2", [70, 24, 40, 16])]),
                unit_report("unit_3", [145, 20, 90, 40], [direct_match("text_3", [150, 24, 30, 16]), direct_match("text_4", [185, 24, 30, 16])]),
            ]
        ),
    )

    result = materialize_m38_hierarchy(
        m30_dsl_path=str(dsl_path),
        m37_report_path=str(report_path),
        output_dir=tmp_path / "m38",
        options=M38Options(max_containers=1),
    )

    assert result.report["summary"]["createdContainerCount"] == 1
    assert result.report["summary"]["skipReasonCounts"]["insufficient_direct_movable_children"] == 1
    assert result.report["summary"]["skipReasonCounts"]["skipped_max_containers"] == 1


def test_m38_no_safe_candidates_reports_unchanged(tmp_path: Path) -> None:
    dsl_path = write_json(tmp_path / "m30.json", base_dsl())
    report_path = write_json(
        tmp_path / "m37.json",
        m37_report(
            [
                {
                    **unit_report("unit_1", [10, 20, 120, 40], [direct_match("text_1", [12, 24, 40, 16]), direct_match("text_2", [70, 24, 40, 16])]),
                    "safeContainerCandidate": False,
                    "unsafeReasons": ["unsupported_visual_kind"],
                }
            ]
        ),
    )

    result = materialize_m38_hierarchy(m30_dsl_path=str(dsl_path), m37_report_path=str(report_path), output_dir=tmp_path / "m38")

    assert result.report["summary"]["sourceSafeContainerCount"] == 0
    assert result.report["summary"]["dslChanged"] is False
    assert result.dsl == base_dsl()


def base_dsl() -> dict:
    return {
        "version": "0.1",
        "taskId": "task_test",
        "page": {"width": 200, "height": 120},
        "assets": [{"assetId": "asset_fallback", "type": "image", "role": "fallback_region", "url": "fallback.png", "format": "png"}],
        "root": {
            "id": "root",
            "type": "frame",
            "role": "screen",
            "layout": {"x": 0, "y": 0, "width": 200, "height": 120},
            "children": [
                {
                    "id": "original_ref",
                    "type": "image",
                    "role": "original_reference",
                    "layout": {"x": 0, "y": 0, "width": 200, "height": 120},
                    "source": {"assetId": "asset_fallback"},
                },
                {
                    "id": "fallback_full_image",
                    "type": "image",
                    "role": "fallback_region",
                    "layout": {"x": 0, "y": 0, "width": 200, "height": 120},
                    "source": {"assetId": "asset_fallback"},
                },
                m30_text("text_1", [12, 24, 40, 16], "A"),
                m30_text("text_2", [70, 24, 40, 16], "B"),
                {
                    "id": "image_outside",
                    "type": "image",
                    "role": "m30_visual_asset",
                    "layout": {"x": 10, "y": 80, "width": 20, "height": 20},
                    "source": {"assetId": "asset_fallback"},
                    "meta": {"m30Materialized": True},
                },
            ],
        },
        "meta": {"qualityFlags": ["m30_evidence_grounded_materialization"], "elementCount": 6},
    }


def m30_text(node_id: str, bbox: list[int], text: str) -> dict:
    return {
        "id": node_id,
        "type": "text",
        "role": "m30_text_member",
        "layout": {"x": bbox[0], "y": bbox[1], "width": bbox[2], "height": bbox[3]},
        "content": {"text": text},
        "meta": {"m30Materialized": True, "sourceTextBoxId": f"ocr_{node_id}"},
    }


def m37_report(unit_reports: list[dict]) -> dict:
    return {
        "schemaName": "M37HierarchyReadinessReport",
        "schemaVersion": "0.1",
        "summary": {"safeContainerUnitCount": sum(1 for item in unit_reports if item.get("safeContainerCandidate"))},
        "unitReports": unit_reports,
    }


def unit_report(unit_id: str, bbox: list[int], matches: list[dict]) -> dict:
    return {
        "unitId": unit_id,
        "kind": "reconstruction_unit",
        "unitKind": "row_unit",
        "visualKind": "text_block",
        "bbox": bbox,
        "safeContainerCandidate": True,
        "unsafeReasons": [],
        "matches": matches,
    }


def direct_match(node_id: str, bbox: list[int]) -> dict:
    return {"m30NodeId": node_id, "role": "m30_text_member", "matchKind": "direct_match", "bbox": bbox}


def geometry_match(node_id: str, bbox: list[int]) -> dict:
    return {"m30NodeId": node_id, "role": "m30_text_member", "matchKind": "geometry_text_match", "bbox": bbox}


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
