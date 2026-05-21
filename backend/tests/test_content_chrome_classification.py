from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import numpy as np

# Imported dynamically inside tests to avoid module reload pollution
from app.hierarchy_readiness import extract_m37_hierarchy_readiness
from app.hierarchy_materialization import materialize_m38_hierarchy, M38Options
from app.m30_upload_pipeline import run_pipeline, pipeline_paths, M30PipelinePaths


def test_classify_content_chrome_rules() -> None:
    # Set up a dummy DSL
    dsl = {
        "version": "0.1",
        "page": {"width": 1000, "height": 1000},
        "root": {
            "id": "root",
            "type": "frame",
            "children": [
                # 1. Top 12% vertical bounds with width >= 60%
                {
                    "id": "node_top_chrome",
                    "role": "m30_text_member",
                    "layout": {"x": 100, "y": 10, "width": 800, "height": 50},
                    "meta": {"m30Materialized": True},
                },
                # 2. Bottom 12% vertical bounds with width >= 60%
                {
                    "id": "node_bottom_chrome",
                    "role": "m30_shape_candidate",
                    "layout": {"x": 100, "y": 900, "width": 800, "height": 50},
                    "meta": {"m30Materialized": True},
                },
                # 3. Floating items on right edge
                {
                    "id": "node_right_float_chrome",
                    "role": "m30_visual_asset",
                    "layout": {"x": 850, "y": 200, "width": 50, "height": 50},
                    "meta": {"m30Materialized": True},
                },
                # 4. Standard content item (center of screen, not matching any rule)
                {
                    "id": "node_center_content",
                    "role": "m30_text_member",
                    "layout": {"x": 400, "y": 400, "width": 200, "height": 100},
                    "meta": {"m30Materialized": True},
                },
                # 5. Non-M30 node (should be skipped or default to content)
                {
                    "id": "node_non_m30",
                    "role": "some_other_role",
                    "layout": {"x": 100, "y": 10, "width": 800, "height": 50},
                    "meta": {"m30Materialized": False},
                },
            ],
        },
    }

    import app.content_chrome_classification
    report = app.content_chrome_classification.classify_content_chrome(dsl, "task_dummy", Path("/tmp"))
    
    nodes_by_id = {n["id"]: n for n in dsl["root"]["children"]}
    
    # Assert classifications
    assert nodes_by_id["node_top_chrome"]["meta"]["boundaryClassification"] == "chrome"
    assert nodes_by_id["node_bottom_chrome"]["meta"]["boundaryClassification"] == "chrome"
    assert nodes_by_id["node_right_float_chrome"]["meta"]["boundaryClassification"] == "chrome"
    assert nodes_by_id["node_center_content"]["meta"]["boundaryClassification"] == "content"
    assert nodes_by_id["node_non_m30"]["meta"].get("boundaryClassification") is None


def test_classify_content_chrome_model_proposer_and_override() -> None:
    dsl = {
        "version": "0.1",
        "page": {"width": 1000, "height": 1000},
        "root": {
            "id": "root",
            "type": "frame",
            "children": [
                # Node overlapping > 80% with a proposed box in a safe zone (top area, not center)
                {
                    "id": "node_overlap_chrome",
                    "role": "m30_text_member",
                    "layout": {"x": 10, "y": 10, "width": 100, "height": 100},
                    "meta": {"m30Materialized": True},
                },
                # Node overlapping > 80% with a proposed box in the center 60% (violates center safety, should remain content)
                {
                    "id": "node_overlap_center_protected",
                    "role": "m30_text_member",
                    "layout": {"x": 450, "y": 450, "width": 100, "height": 100},
                    "meta": {"m30Materialized": True},
                },
            ],
        },
    }

    # Mock proposed boxes
    proposed_boxes = [
        {"bbox": [5, 5, 110, 110], "score": 0.9},        # Overlaps with node_overlap_chrome
        {"bbox": [440, 440, 120, 120], "score": 0.85},   # Overlaps with node_overlap_center_protected
    ]

    with patch("app.content_chrome_classification.onnxruntime") as mock_ort, \
         patch("app.content_chrome_classification.load_onnx_model") as mock_load, \
         patch("app.content_chrome_classification.run_model_inference") as mock_run:
        
        mock_load.return_value = MagicMock()
        mock_run.return_value = proposed_boxes
        
        # Test with source image path
        img_path = Path("/tmp/dummy.png")
        img_path.touch()
        
        try:
            import app.content_chrome_classification
            report = app.content_chrome_classification.classify_content_chrome(dsl, "task_dummy", Path("/tmp"), source_image_path=img_path)
            
            nodes_by_id = {n["id"]: n for n in dsl["root"]["children"]}
            
            assert nodes_by_id["node_overlap_chrome"]["meta"]["boundaryClassification"] == "chrome"
            assert nodes_by_id["node_overlap_center_protected"]["meta"]["boundaryClassification"] == "content"
        finally:
            if img_path.exists():
                img_path.unlink()


def test_m37_m38_boundary_enforcement(tmp_path: Path) -> None:
    # 1. Prepare M30 DSL with classification labels
    m30_dsl = {
        "version": "0.1",
        "page": {"width": 1000, "height": 1000},
        "assets": [],
        "root": {
            "id": "root",
            "type": "frame",
            "children": [
                {
                    "id": "m30_node_1",
                    "type": "text",
                    "role": "m30_text_member",
                    "layout": {"x": 10, "y": 10, "width": 100, "height": 30},
                    "content": {"text": "Header Title"},
                    "meta": {
                        "m30Materialized": True,
                        "boundaryClassification": "chrome",
                        "sourceKind": "m2905_text_member",
                        "sourceTextMemberId": "text_member_1",
                        "sourceTextBoxId": "ocr_1",
                    },
                },
                {
                    "id": "m30_node_2",
                    "type": "text",
                    "role": "m30_text_member",
                    "layout": {"x": 120, "y": 10, "width": 200, "height": 30},
                    "content": {"text": "Content Body"},
                    "meta": {
                        "m30Materialized": True,
                        "boundaryClassification": "content",
                        "sourceKind": "m2905_text_member",
                        "sourceTextMemberId": "text_member_2",
                        "sourceTextBoxId": "ocr_2",
                    },
                },
            ],
        },
    }

    # 2. Prepare M31 Tree with a reconstruction unit grouping BOTH node 1 (chrome) and node 2 (content)
    m31_tree = {
        "schemaName": "M31ReconstructionUiTree",
        "schemaVersion": "0.1",
        "imageSize": {"width": 1000, "height": 1000},
        "root": {"id": "page", "kind": "page", "bbox": [0, 0, 1000, 1000], "children": ["unit_conflict"]},
        "nodes": [
            {
                "id": "unit_conflict",
                "kind": "reconstruction_unit",
                "unitKind": "row_unit",
                "visualKind": "text_block",
                "bbox": [0, 0, 400, 50],
                "children": ["prim_1", "prim_2"],
            }
        ],
        "primitiveRefs": [
            {
                "id": "prim_1",
                "sourceId": "text_member_1",
                "primitiveType": "text",
                "bbox": [10, 10, 100, 30],
                "ownerUnitId": "unit_conflict",
            },
            {
                "id": "prim_2",
                "sourceId": "text_member_2",
                "primitiveType": "text",
                "bbox": [120, 10, 200, 30],
                "ownerUnitId": "unit_conflict",
            },
        ],
    }

    m31_report = {"schemaName": "M31ReconstructionUiTreeReport", "summary": {}}
    m30_report = {"schemaName": "M30EvidenceGroundedDslMaterializationReport", "summary": {}}

    tree_path = tmp_path / "m31_reconstruction_tree.json"
    m31_report_path = tmp_path / "m31_reconstruction_tree_report.json"
    dsl_path = tmp_path / "m30_materialized_dsl.json"
    m30_report_path = tmp_path / "m30_materialization_report.json"

    tree_path.write_text(json.dumps(m31_tree))
    m31_report_path.write_text(json.dumps(m31_report))
    dsl_path.write_text(json.dumps(m30_dsl))
    m30_report_path.write_text(json.dumps(m30_report))

    # 3. Run M37 Audit
    m37_output_dir = tmp_path / "m37"
    m37_result = extract_m37_hierarchy_readiness(
        m31_tree_path=str(tree_path),
        m31_report_path=str(m31_report_path),
        m30_dsl_path=str(dsl_path),
        m30_report_path=str(m30_report_path),
        output_dir=m37_output_dir,
    )

    report_data = m37_result.report
    assert report_data["summary"]["safeContainerUnitCount"] == 0
    assert report_data["summary"]["unsafeContainerUnitCount"] == 1
    
    conflict_unit = report_data["unitReports"][0]
    assert "boundary_classification_conflict" in conflict_unit["unsafeReasons"]
    assert conflict_unit["safeContainerCandidate"] is False

    # 4. Run M38 Hierarchy Materialization
    m38_output_dir = tmp_path / "m38"
    m38_result = materialize_m38_hierarchy(
        m30_dsl_path=str(dsl_path),
        m37_report_path=str(m37_output_dir / "m37_hierarchy_readiness_report.json"),
        output_dir=m38_output_dir,
        flat_dsl_output_path=str(tmp_path / "flat_dsl.json"),
        final_dsl_output_path=str(tmp_path / "final_dsl.json"),
        options=M38Options(max_containers=8),
    )

    # Since unit_conflict is unsafe, no containers should be created
    assert len(m38_result.report["containers"]) == 0
    assert m38_result.report["summary"]["createdContainerCount"] == 0
    assert len(m38_result.report["skippedContainers"]) == 0
    assert m38_result.report["summary"]["skippedContainerCount"] == 0
    assert m38_result.report["summary"]["sourceSafeContainerCount"] == 0
