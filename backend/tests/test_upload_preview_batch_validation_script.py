from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_upload_preview_batch_validation.py"


def load_script():
    spec = importlib.util.spec_from_file_location("run_upload_preview_batch_validation", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_discover_inputs_defaults_to_one_directory_and_records_unsupported_formats(tmp_path: Path) -> None:
    script = load_script()
    image_dir = tmp_path / "images"
    nested_dir = image_dir / "nested"
    nested_dir.mkdir(parents=True)
    png_path = nested_dir / "sample.png"
    jpg_path = image_dir / "sample.jpg"
    txt_path = image_dir / "ignored.txt"
    png_path.write_bytes(b"png")
    jpg_path.write_bytes(b"jpg")
    txt_path.write_text("ignored", encoding="utf-8")

    inputs = script.discover_inputs(image_dir)
    records = [script.unsupported_record(item["path"], tmp_path) for item in inputs if not item["uploadSupported"]]

    by_path = {item["path"]: item for item in inputs}
    assert set(by_path) == {jpg_path}
    assert by_path[jpg_path]["normalizedInputType"] == "jpeg"
    assert by_path[jpg_path]["uploadSupported"] is False
    assert records[0]["status"] == "unsupported_input_format"
    assert records[0]["relativeInputPath"] == "images/sample.jpg"

    recursive_inputs = script.discover_inputs(image_dir, recursive=True)
    recursive_by_path = {item["path"]: item for item in recursive_inputs}
    assert set(recursive_by_path) == {jpg_path, png_path}
    assert recursive_by_path[png_path]["normalizedInputType"] == "png"
    assert recursive_by_path[png_path]["uploadSupported"] is True


def test_discover_inputs_can_limit_sorted_candidates(tmp_path: Path) -> None:
    script = load_script()
    for index in range(3):
        (tmp_path / f"{index}.png").write_bytes(b"png")

    inputs = script.discover_inputs(tmp_path, max_files=2)

    assert [item["path"].name for item in inputs] == ["0.png", "1.png"]


def test_backend_command_can_include_runtime_extras() -> None:
    script = load_script()

    command = script.build_backend_command(port=8123, uv_with=["onnxruntime,numpy", "onnxruntime", " pillow "])

    assert command == [
        "uv",
        "run",
        "--with",
        "onnxruntime",
        "--with",
        "numpy",
        "--with",
        "pillow",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8123",
    ]


def test_resolve_output_dir_uses_collision_resistant_default(monkeypatch) -> None:
    script = load_script()

    class FixedDatetime:
        @classmethod
        def now(cls, tz=None):
            class FixedNow:
                def strftime(self, fmt: str) -> str:
                    return "20260527_123456_789012"

            return FixedNow()

    monkeypatch.setattr(script, "datetime", FixedDatetime)
    monkeypatch.setattr(os, "getpid", lambda: 4242)

    output_dir = script.resolve_output_dir("")

    assert output_dir.name == "upload_preview_batch_20260527_123456_789012_4242"


def test_load_summary_extracts_dsl_counts(tmp_path: Path) -> None:
    script = load_script()
    dsl_path = tmp_path / "design.dsl.json"
    dsl_path.write_text(
        json.dumps(
            {
                "assets": [{"assetId": "asset_1", "url": "/files/assets/task/m29/asset.png"}],
                "root": {
                    "type": "frame",
                    "children": [
                        {"role": "m29_text"},
                        {"role": "m29_shape"},
                        {"role": "m29_image"},
                        {"role": "m29_symbol"},
                        {"role": "fallback_region"},
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    record = script.base_record(tmp_path / "input.png", tmp_path)

    script.load_summary(record, "dsl", dsl_path)

    assert record["summaries"]["dsl"] == {"assetCount": 1, "rootChildCount": 5}
    assert record["visibleTextCount"] == 1
    assert record["visibleShapeCount"] == 1
    assert record["visibleImageCount"] == 1
    assert record["visibleSymbolCount"] == 1
    assert record["fallbackCount"] == 1


def test_collect_artifacts_can_require_perception_model_outputs(tmp_path: Path, monkeypatch) -> None:
    script = load_script()
    storage_root = tmp_path / "storage"
    task_id = "task_model"
    root = storage_root / "upload_previews" / task_id
    write_minimal_artifacts(root, storage_root, task_id)
    (root / "m29_perception_model").mkdir()
    (root / "m29_perception_model" / "perception_model_report.json").write_text(
        json.dumps({"summary": {"candidateCount": 11}}),
        encoding="utf-8",
    )
    (root / "m29_perception_source_compiler").mkdir()
    (root / "m29_perception_source_compiler" / "perception_source_compiler_report.json").write_text(
        json.dumps(
            {
                "summary": {
                    "compiledSourceObjectCount": 5,
                    "compiledControlBackgroundCount": 2,
                    "compiledControlImageCount": 1,
                    "compiledRasterIconCount": 3,
                }
            }
        ),
        encoding="utf-8",
    )
    (root / "m29_perception_source_compiler" / "source_ui_physical_graph.perception.json").write_text("{}", encoding="utf-8")
    (root / "m29_perception_fate_trace").mkdir()
    (root / "m29_perception_fate_trace" / "perception_fate_trace_report.json").write_text(
        json.dumps({"summary": {"traceCount": 11, "blockedCount": 6}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(script, "validate_dsl_assets", lambda *args, **kwargs: None)
    record = script.base_record(tmp_path / "input.png", tmp_path)
    record["status"] = "completed"

    script.collect_artifacts(record, storage_root, task_id, base_url="http://127.0.0.1:8000", expect_perception_artifacts=True)

    assert not [error for error in record["errors"] if error["type"] == "missing_artifact"]
    assert record["artifacts"]["perceptionModelReport"]["exists"] is True
    assert record["artifacts"]["perceptionFateTraceReport"]["exists"] is True
    assert record["perceptionCandidateCount"] == 11
    assert record["compiledSourceObjectCount"] == 5
    assert record["compiledControlBackgroundCount"] == 2
    assert record["compiledControlImageCount"] == 1
    assert record["compiledRasterIconCount"] == 3
    assert record["perceptionFateTraceCount"] == 11
    assert record["perceptionFateBlockedCount"] == 6
    assert record["plannedShapeReplayCount"] == 7
    assert record["plannedIconReplayCount"] == 4
    assert record["copiedImageAssetCleanupTargetCount"] == 6
    assert record["copiedImageAssetShapeErasedCount"] == 5
    assert record["copiedImageAssetInternalErasedCount"] == 1
    assert record["materializedVisibleNodeCount"] == 30


def test_build_summary_separates_unsupported_from_supported_failures(tmp_path: Path) -> None:
    script = load_script()
    completed = script.base_record(tmp_path / "ok.png", tmp_path)
    completed["status"] = "completed"
    completed["assetFetchFailedCount"] = 1
    completed["perceptionCandidateCount"] = 11
    completed["compiledSourceObjectCount"] = 5
    completed["compiledControlBackgroundCount"] = 2
    completed["compiledControlImageCount"] = 1
    completed["compiledRasterIconCount"] = 3
    completed["perceptionFateTraceCount"] = 11
    completed["perceptionFateBlockedCount"] = 6
    completed["plannedShapeReplayCount"] = 7
    completed["plannedIconReplayCount"] = 4
    completed["copiedImageAssetCleanupTargetCount"] = 6
    completed["copiedImageAssetShapeErasedCount"] = 5
    completed["copiedImageAssetInternalErasedCount"] = 1
    completed["materializedVisibleNodeCount"] = 30
    completed["summaries"]["dslVisualComparison"] = {
        "normalizedMeanAbsError": 0.20,
        "changedPixelRatio10": 0.30,
        "gateNormalizedMeanAbsError": 0.10,
        "gateChangedPixelRatio10": 0.15,
    }
    failed = script.base_record(tmp_path / "bad.png", tmp_path)
    failed["status"] = "error"
    failed["errors"].append({"type": "missing_artifact"})
    failed["summaries"]["dslVisualComparison"] = {
        "normalizedMeanAbsError": 0.40,
        "changedPixelRatio10": 0.50,
    }
    unsupported = script.unsupported_record(tmp_path / "photo.webp", tmp_path)

    summary = script.build_summary([completed, failed, unsupported])

    assert summary["inputCount"] == 3
    assert summary["supportedInputCount"] == 2
    assert summary["unsupportedInputCount"] == 1
    assert summary["completedTaskCount"] == 1
    assert summary["supportedCompletedTaskCount"] == 1
    assert summary["failedTaskCount"] == 2
    assert summary["supportedFailedCount"] == 1
    assert summary["missingArtifactCount"] == 1
    assert summary["assetFetchFailedCount"] == 1
    assert summary["averageDslVisualNormalizedMeanAbsError"] == 0.3
    assert summary["maxDslVisualChangedPixelRatio10"] == 0.5
    assert summary["averageDslVisualGateNormalizedMeanAbsError"] == 0.25
    assert summary["maxDslVisualGateChangedPixelRatio10"] == 0.5
    assert summary["totalPerceptionCandidateCount"] == 11
    assert summary["totalCompiledSourceObjectCount"] == 5
    assert summary["totalCompiledControlBackgroundCount"] == 2
    assert summary["totalCompiledControlImageCount"] == 1
    assert summary["totalCompiledRasterIconCount"] == 3
    assert summary["totalPerceptionFateTraceCount"] == 11
    assert summary["totalPerceptionFateBlockedCount"] == 6
    assert summary["totalPlannedShapeReplayCount"] == 7
    assert summary["totalPlannedIconReplayCount"] == 4
    assert summary["totalCopiedImageAssetCleanupTargetCount"] == 6
    assert summary["totalCopiedImageAssetShapeErasedCount"] == 5
    assert summary["totalCopiedImageAssetInternalErasedCount"] == 1
    assert summary["totalMaterializedVisibleNodeCount"] == 30


def test_derive_record_metrics_promotes_visual_gate_metrics(tmp_path: Path) -> None:
    script = load_script()
    record = script.base_record(tmp_path / "input.png", tmp_path)
    record["summaries"]["dslVisualComparison"] = {
        "normalizedMeanAbsError": 0.1234567,
        "changedPixelRatio10": 0.2345678,
        "gateNormalizedMeanAbsError": 0.0123456,
        "gateChangedPixelRatio10": 0.0456789,
    }

    script.derive_record_metrics(record)

    assert record["dslVisualNormalizedMeanAbsError"] == 0.123457
    assert record["dslVisualChangedPixelRatio10"] == 0.234568
    assert record["dslVisualGateNormalizedMeanAbsError"] == 0.012346
    assert record["dslVisualGateChangedPixelRatio10"] == 0.045679


def write_minimal_artifacts(root: Path, storage_root: Path, task_id: str) -> None:
    artifact_summaries = {
        "stage_timings.json": {"stages": []},
        "m29/nodes.json": {"summary": {}},
        "m29_2/source_ui_physical_graph.json": {"summary": {}},
        "m29_3/region_relation_graph_report.json": {"summary": {}},
        "m29_4/stable_design_cluster_report.json": {"summary": {}},
        "m29_ownership_conservation/ownership_conservation_report.json": {"summary": {"conflictTypeCounts": {}}},
        "m29_media_internal_decomposition/media_internal_decomposition_report.json": {"summary": {}},
        "m29_transparent_assets/transparent_asset_report.json": {"summary": {}},
        "m29_evidence_contract/evidence_contract_report.json": {"summary": {}},
        "m29_internal_source_promotion/internal_source_promotion_report.json": {"summary": {}},
        "m29_hierarchy_candidates/hierarchy_candidate_report.json": {"summary": {}},
        "m29_sibling_groups/sibling_group_candidate_report.json": {"summary": {}},
        "m29_layout_energy/layout_energy_report.json": {"summary": {}},
        "m29_auto_layout_permission/auto_layout_permission_report.json": {"summary": {}},
        "m29_design_tokens/design_token_report.json": {"summary": {}},
        "m29_b_stage_quality/b_stage_quality_report.json": {"summary": {}},
        "m29_dsl_visual_comparison/dsl_visual_comparison_report.json": {"summary": {}},
        "m29_5/replay_plan.json": {
            "summary": {
                "plannedShapeReplayCount": 7,
                "plannedIconReplayCount": 4,
                "fallbackCleanupTargetCount": 8,
                "copiedImageAssetCleanupTargetCount": 6,
            }
        },
        "materialized_design/materialization_report.json": {
            "summary": {
                "fallbackErasedBBoxCount": 8,
                "copiedImageAssetTextErasedCount": 2,
                "copiedImageAssetInternalErasedCount": 1,
                "copiedImageAssetShapeErasedCount": 5,
                "visibleNodeCount": 30,
            }
        },
        "materialized_design/design.dsl.json": {"assets": [], "root": {"type": "frame", "children": []}},
    }
    for relative_path, data in artifact_summaries.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    for relative_path in [
        "m29_dsl_visual_comparison/dsl_render.png",
        "m29_dsl_visual_comparison/source_diff.png",
        "m29_dsl_visual_comparison/source_gate_diff.png",
    ]:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"png")
    upload_path = storage_root / "uploads" / task_id / "original.png"
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(b"png")
