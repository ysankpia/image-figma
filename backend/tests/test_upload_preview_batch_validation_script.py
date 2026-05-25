from __future__ import annotations

import importlib.util
import json
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


def test_build_summary_separates_unsupported_from_supported_failures(tmp_path: Path) -> None:
    script = load_script()
    completed = script.base_record(tmp_path / "ok.png", tmp_path)
    completed["status"] = "completed"
    completed["assetFetchFailedCount"] = 1
    failed = script.base_record(tmp_path / "bad.png", tmp_path)
    failed["status"] = "error"
    failed["errors"].append({"type": "missing_artifact"})
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
