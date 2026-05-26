from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = Path("/Users/luhui/Downloads/m29")
CANDIDATE_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
SUPPORTED_UPLOAD_SUFFIXES = {".png"}
CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir).expanduser().resolve()
    inputs = discover_inputs(input_dir, recursive=args.recursive, max_files=args.max_files)
    if not inputs:
        raise SystemExit(f"No candidate image files found under {input_dir}")
    output_dir = resolve_output_dir(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    port = args.port or find_free_port()
    storage_root = output_dir / "storage"
    database_path = storage_root / "app.db"
    log_path = output_dir / "backend.log"
    if args.enable_perception_model:
        if not args.perception_model_path.strip():
            raise SystemExit("--perception-model-path is required when --enable-perception-model is set")
        perception_model_path = Path(args.perception_model_path).expanduser().resolve()
        if not perception_model_path.is_file():
            raise SystemExit(f"Perception model file does not exist: {perception_model_path}")
    else:
        perception_model_path = None

    uv_with = normalize_uv_with(args.uv_with)
    process, log_file = start_backend(
        port=port,
        storage_root=storage_root,
        database_path=database_path,
        log_path=log_path,
        enable_perception_model=args.enable_perception_model,
        perception_model_path=perception_model_path,
        uv_with=uv_with,
    )
    base_url = f"http://127.0.0.1:{port}"
    started_at = datetime.now(UTC).isoformat()
    try:
        wait_for_health(base_url, timeout_seconds=args.startup_timeout)
        records = []
        for index, item in enumerate(inputs, start=1):
            path = item["path"]
            if not item["uploadSupported"]:
                record = unsupported_record(path, input_dir)
                records.append(record)
                print(f"[batch] {index}/{len(inputs)} unsupported_input_format {path}", flush=True)
                continue
            print(f"[batch] {index}/{len(inputs)} upload-preview {path}", flush=True)
            record = run_one(
                base_url,
                path,
                input_dir,
                storage_root,
                poll_timeout_seconds=args.poll_timeout,
                expect_perception_artifacts=args.enable_perception_model,
            )
            records.append(record)
            print(f"[batch] {index}/{len(inputs)} status={record['status']} errors={len(record['errors'])}", flush=True)
            if process.poll() is not None:
                record["errors"].append({"type": "backend_process_exited", "exitCode": process.returncode})
                record["backendProcessExitCode"] = process.returncode
                print("[batch] backend process exited; remaining supported inputs cannot be validated", flush=True)
                break
    finally:
        stop_backend(process)
        log_file.close()

    summary = build_summary(records)
    ledger = {
        "schemaName": "UploadPreviewBatchValidationLedger",
        "schemaVersion": "0.3",
        "createdAt": datetime.now(UTC).isoformat(),
        "startedAt": started_at,
        "inputDir": str(input_dir),
        "outputDir": str(output_dir),
        "backendBaseUrl": base_url,
        "backendLog": str(log_path),
        "storageRoot": str(storage_root),
        "runtimeOptions": {
            "enablePerceptionModel": bool(args.enable_perception_model),
            "perceptionModelPath": str(perception_model_path) if perception_model_path is not None else None,
            "uvWith": uv_with,
        },
        "summary": summary,
        "records": records,
    }
    ledger_path = output_dir / "upload_preview_batch_validation.json"
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ledger": str(ledger_path), "summary": summary}, ensure_ascii=False, indent=2))
    return 0 if summary["supportedFailedCount"] == 0 and summary["missingArtifactCount"] == 0 and summary["assetFetchFailedCount"] == 0 else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run real upload-preview batch validation through the HTTP API.")
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR))
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--startup-timeout", type=float, default=30.0)
    parser.add_argument("--poll-timeout", type=float, default=180.0)
    parser.add_argument("--recursive", action="store_true", help="Discover candidate images recursively under input-dir.")
    parser.add_argument("--max-files", type=int, default=0, help="Limit discovered candidate images after sorting. 0 means no limit.")
    parser.add_argument("--enable-perception-model", action="store_true", help="Enable the opt-in M29 perception model upload-preview path.")
    parser.add_argument("--perception-model-path", default="", help="Local ONNX model path used when --enable-perception-model is set.")
    parser.add_argument(
        "--uv-with",
        action="append",
        default=[],
        help="Extra dependency passed to backend startup as `uv run --with <package>`. Repeatable; comma-separated values are also accepted.",
    )
    return parser.parse_args()


def resolve_output_dir(value: str) -> Path:
    if value.strip():
        return Path(value).expanduser().resolve()
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    return (BACKEND_ROOT / "tmp" / "validation" / f"upload_preview_batch_{stamp}_{os.getpid()}").resolve()


def discover_inputs(input_dir: Path, *, recursive: bool = False, max_files: int = 0) -> list[dict[str, Any]]:
    iterator = input_dir.rglob("*") if recursive else input_dir.iterdir()
    paths = sorted(path for path in iterator if path.is_file() and path.suffix.lower() in CANDIDATE_IMAGE_SUFFIXES)
    if max_files > 0:
        paths = paths[:max_files]
    return [
        {
            "path": path,
            "normalizedInputType": normalized_input_type(path),
            "uploadSupported": path.suffix.lower() in SUPPORTED_UPLOAD_SUFFIXES,
        }
        for path in paths
    ]


def normalized_input_type(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return "jpeg" if suffix == "jpg" else suffix


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def start_backend(
    *,
    port: int,
    storage_root: Path,
    database_path: Path,
    log_path: Path,
    enable_perception_model: bool = False,
    perception_model_path: Path | None = None,
    uv_with: list[str] | None = None,
) -> tuple[subprocess.Popen[str], TextIO]:
    env = os.environ.copy()
    env.update(
        {
            "STORAGE_ROOT": str(storage_root),
            "DATABASE_PATH": str(database_path),
            "PUBLIC_BASE_URL": f"http://127.0.0.1:{port}",
            "UPLOAD_PREVIEW_PROFILE": "production",
            "IMAGE_FIGMA_LOAD_LOCAL_ENV": "true",
            "M29_PERCEPTION_MODEL_ENABLED": "true" if enable_perception_model else "false",
        }
    )
    if perception_model_path is not None:
        env["M29_PERCEPTION_MODEL_PATH"] = str(perception_model_path)
    log_file = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        build_backend_command(port=port, uv_with=uv_with or []),
        cwd=BACKEND_ROOT,
        env=env,
        text=True,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    return process, log_file


def normalize_uv_with(values: list[str]) -> list[str]:
    packages: list[str] = []
    seen: set[str] = set()
    for value in values:
        for part in str(value).split(","):
            package = part.strip()
            if not package or package in seen:
                continue
            seen.add(package)
            packages.append(package)
    return packages


def build_backend_command(*, port: int, uv_with: list[str]) -> list[str]:
    command = ["uv", "run"]
    for package in normalize_uv_with(uv_with):
        command.extend(["--with", package])
    command.extend(
        [
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ]
    )
    return command


def wait_for_health(base_url: str, *, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/api/health", timeout=2) as response:
                if response.status == 200:
                    return
        except OSError as error:
            last_error = str(error)
        time.sleep(0.25)
    raise RuntimeError(f"backend did not become healthy at {base_url}: {last_error}")


def stop_backend(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def unsupported_record(image_path: Path, input_dir: Path) -> dict[str, Any]:
    record = base_record(image_path, input_dir)
    record["status"] = "unsupported_input_format"
    record["degradedReason"] = "unsupported_input_format"
    record["errors"].append(
        {
            "type": "unsupported_input_format",
            "suffix": image_path.suffix.lower(),
            "message": "Current /api/upload-preview accepts PNG only.",
        }
    )
    return record


def base_record(image_path: Path, input_dir: Path) -> dict[str, Any]:
    return {
        "inputPath": str(image_path),
        "relativeInputPath": relative_to_or_self(image_path, input_dir),
        "filename": image_path.name,
        "normalizedInputType": normalized_input_type(image_path),
        "uploadSupported": image_path.suffix.lower() in SUPPORTED_UPLOAD_SUFFIXES,
        "contentType": CONTENT_TYPES.get(image_path.suffix.lower(), "application/octet-stream"),
        "status": "not_started",
        "taskId": None,
        "taskStage": None,
        "failedStage": None,
        "backendError": None,
        "dslPath": None,
        "sourceImagePath": None,
        "renderBackImagePath": None,
        "visualDiffImagePath": None,
        "visualGateDiffImagePath": None,
        "nodeCounts": {},
        "visibleTextCount": 0,
        "visibleShapeCount": 0,
        "visibleImageCount": 0,
        "visibleSymbolCount": 0,
        "fallbackCount": 0,
        "dslVisualNormalizedMeanAbsError": None,
        "dslVisualChangedPixelRatio10": None,
        "dslVisualGateNormalizedMeanAbsError": None,
        "dslVisualGateChangedPixelRatio10": None,
        "perceptionCandidateCount": 0,
        "compiledSourceObjectCount": 0,
        "compiledControlBackgroundCount": 0,
        "compiledRasterIconCount": 0,
        "perceptionFateTraceCount": 0,
        "perceptionFateBlockedCount": 0,
        "plannedShapeReplayCount": 0,
        "plannedIconReplayCount": 0,
        "copiedImageAssetCleanupTargetCount": 0,
        "copiedImageAssetShapeErasedCount": 0,
        "copiedImageAssetInternalErasedCount": 0,
        "materializedVisibleNodeCount": 0,
        "cleanupTargetCount": 0,
        "executedCleanupCount": 0,
        "ownershipConflictCount": 0,
        "assetFetchCount": 0,
        "assetFetchFailedCount": 0,
        "degradedReason": None,
        "humanInspectionNotes": "",
        "artifacts": {},
        "assetFetches": [],
        "summaries": {},
        "errors": [],
    }


def relative_to_or_self(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def run_one(
    base_url: str,
    image_path: Path,
    input_dir: Path,
    storage_root: Path,
    *,
    poll_timeout_seconds: float,
    expect_perception_artifacts: bool = False,
) -> dict[str, Any]:
    record: dict[str, Any] = base_record(image_path, input_dir)
    try:
        upload = upload_png(base_url, image_path)
        task_id = upload["data"]["taskId"]
        record["taskId"] = task_id
        task = wait_for_task(base_url, task_id, timeout_seconds=poll_timeout_seconds)
        record["status"] = task["data"]["status"]
        record["taskStage"] = task["data"]["stage"]
        collect_artifacts(record, storage_root, task_id, base_url=base_url, expect_perception_artifacts=expect_perception_artifacts)
        if record["status"] != "completed":
            record["failedStage"] = record["taskStage"]
            record["degradedReason"] = "task_not_completed"
            record["errors"].append({"type": "task_not_completed", "task": task})
    except Exception as error:  # noqa: BLE001 - batch ledger must keep per-file failures.
        record["status"] = "error"
        record["failedStage"] = record.get("taskStage")
        record["backendError"] = {"type": error.__class__.__name__, "message": str(error)}
        record["degradedReason"] = error.__class__.__name__
        record["errors"].append({"type": error.__class__.__name__, "message": str(error)})
    return record


def upload_png(base_url: str, image_path: Path) -> dict[str, Any]:
    boundary = f"----imagefigmabatch{int(time.time() * 1000)}"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{image_path.name}"\r\n'.encode(),
            b"Content-Type: image/png\r\n\r\n",
            image_path.read_bytes(),
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    request = urllib.request.Request(
        f"{base_url}/api/upload-preview",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"upload failed for {image_path.name}: HTTP {error.code} {detail}") from error


def wait_for_task(base_url: str, task_id: str, *, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_task: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        with urllib.request.urlopen(f"{base_url}/api/tasks/{task_id}", timeout=10) as response:
            task = json.loads(response.read().decode("utf-8"))
        last_task = task
        if task["data"]["status"] in {"completed", "failed"}:
            return task
        time.sleep(1)
    raise RuntimeError(f"task {task_id} did not finish before timeout; last={last_task}")


def collect_artifacts(record: dict[str, Any], storage_root: Path, task_id: str, *, base_url: str, expect_perception_artifacts: bool = False) -> None:
    root = storage_root / "upload_previews" / task_id
    artifact_paths = {
        "stageTimings": root / "stage_timings.json",
        "dsl": root / "materialized_design" / "design.dsl.json",
        "materializationReport": root / "materialized_design" / "materialization_report.json",
        "sourceImage": storage_root / "uploads" / task_id / "original.png",
        "m29Report": root / "m29" / "nodes.json",
        "m292Report": root / "m29_2" / "source_ui_physical_graph.json",
        "m293Report": root / "m29_3" / "region_relation_graph_report.json",
        "m294Report": root / "m29_4" / "stable_design_cluster_report.json",
        "ownershipConservationReport": root / "m29_ownership_conservation" / "ownership_conservation_report.json",
        "mediaInternalDecompositionReport": root / "m29_media_internal_decomposition" / "media_internal_decomposition_report.json",
        "transparentAssetReport": root / "m29_transparent_assets" / "transparent_asset_report.json",
        "evidenceContractReport": root / "m29_evidence_contract" / "evidence_contract_report.json",
        "internalSourcePromotionReport": root / "m29_internal_source_promotion" / "internal_source_promotion_report.json",
        "hierarchyCandidateReport": root / "m29_hierarchy_candidates" / "hierarchy_candidate_report.json",
        "siblingGroupCandidateReport": root / "m29_sibling_groups" / "sibling_group_candidate_report.json",
        "layoutEnergyReport": root / "m29_layout_energy" / "layout_energy_report.json",
        "autoLayoutPermissionReport": root / "m29_auto_layout_permission" / "auto_layout_permission_report.json",
        "designTokenReport": root / "m29_design_tokens" / "design_token_report.json",
        "bStageQualityReport": root / "m29_b_stage_quality" / "b_stage_quality_report.json",
        "dslVisualComparisonReport": root / "m29_dsl_visual_comparison" / "dsl_visual_comparison_report.json",
        "dslRenderPng": root / "m29_dsl_visual_comparison" / "dsl_render.png",
        "sourceDiffPng": root / "m29_dsl_visual_comparison" / "source_diff.png",
        "sourceGateDiffPng": root / "m29_dsl_visual_comparison" / "source_gate_diff.png",
        "replayPlan": root / "m29_5" / "replay_plan.json",
    }
    if expect_perception_artifacts:
        artifact_paths.update(
            {
                "perceptionModelReport": root / "m29_perception_model" / "perception_model_report.json",
                "perceptionSourceCompilerReport": root / "m29_perception_source_compiler" / "perception_source_compiler_report.json",
                "perceptionSourceCompilerM292": root / "m29_perception_source_compiler" / "source_ui_physical_graph.perception.json",
                "perceptionFateTraceReport": root / "m29_perception_fate_trace" / "perception_fate_trace_report.json",
            }
        )
    for key, path in artifact_paths.items():
        exists = path.exists()
        record["artifacts"][key] = {"path": str(path), "exists": exists}
        if not exists:
            record["errors"].append({"type": "missing_artifact", "artifact": key, "path": str(path)})
    record["dslPath"] = str(artifact_paths["dsl"])
    record["sourceImagePath"] = str(artifact_paths["sourceImage"])
    record["renderBackImagePath"] = str(artifact_paths["dslRenderPng"])
    record["visualDiffImagePath"] = str(artifact_paths["sourceDiffPng"])
    record["visualGateDiffImagePath"] = str(artifact_paths["sourceGateDiffPng"])
    load_summary(record, "stageTimings", artifact_paths["stageTimings"])
    load_summary(record, "dsl", artifact_paths["dsl"])
    load_summary(record, "materialization", artifact_paths["materializationReport"])
    load_summary(record, "m29", artifact_paths["m29Report"])
    load_summary(record, "m292", artifact_paths["m292Report"])
    load_summary(record, "m293", artifact_paths["m293Report"])
    load_summary(record, "m294", artifact_paths["m294Report"])
    load_summary(record, "ownershipConservation", artifact_paths["ownershipConservationReport"])
    load_summary(record, "mediaInternalDecomposition", artifact_paths["mediaInternalDecompositionReport"])
    load_summary(record, "transparentAssets", artifact_paths["transparentAssetReport"])
    load_summary(record, "evidenceContract", artifact_paths["evidenceContractReport"])
    load_summary(record, "internalSourcePromotion", artifact_paths["internalSourcePromotionReport"])
    load_summary(record, "hierarchyCandidates", artifact_paths["hierarchyCandidateReport"])
    load_summary(record, "siblingGroups", artifact_paths["siblingGroupCandidateReport"])
    load_summary(record, "layoutEnergy", artifact_paths["layoutEnergyReport"])
    load_summary(record, "autoLayoutPermission", artifact_paths["autoLayoutPermissionReport"])
    load_summary(record, "designTokens", artifact_paths["designTokenReport"])
    load_summary(record, "bStageQuality", artifact_paths["bStageQualityReport"])
    load_summary(record, "dslVisualComparison", artifact_paths["dslVisualComparisonReport"])
    load_summary(record, "replayPlan", artifact_paths["replayPlan"])
    if expect_perception_artifacts:
        load_summary(record, "perceptionModel", artifact_paths["perceptionModelReport"])
        load_summary(record, "perceptionSourceCompiler", artifact_paths["perceptionSourceCompilerReport"])
        load_summary(record, "perceptionFateTrace", artifact_paths["perceptionFateTraceReport"])
    derive_record_metrics(record)
    validate_dsl_assets(record, artifact_paths["dsl"], base_url=base_url)


def load_summary(record: dict[str, Any], key: str, path: Path) -> None:
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    if key == "dsl":
        record["summaries"][key] = {
            "assetCount": len(list_dicts(data.get("assets"))),
            "rootChildCount": len(list_dicts((data.get("root") or {}).get("children")) if isinstance(data.get("root"), dict) else []),
        }
        record["nodeCounts"] = count_dsl_nodes(data)
        record["visibleTextCount"] = sum_count(record["nodeCounts"], "text", "m29_text")
        record["visibleShapeCount"] = sum_count(record["nodeCounts"], "shape", "m29_shape")
        record["visibleImageCount"] = sum_count(record["nodeCounts"], "image", "m29_image")
        record["visibleSymbolCount"] = sum_count(record["nodeCounts"], "symbol", "m29_symbol")
        record["fallbackCount"] = int(record["nodeCounts"].get("fallback_region") or 0)
        return
    if key == "stageTimings":
        record["summaries"][key] = {
            "stages": [
                {
                    "stage": item.get("stage"),
                    "status": item.get("status"),
                    "elapsedSeconds": item.get("elapsedSeconds"),
                    "error": item.get("error"),
                }
                for item in data.get("stages", [])
                if isinstance(item, dict)
            ]
        }
        return
    record["summaries"][key] = data.get("summary", {})


def list_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def count_dsl_nodes(dsl: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}

    def visit(node: dict[str, Any]) -> None:
        role = str(node.get("role") or node.get("type") or "unknown")
        counts[role] = counts.get(role, 0) + 1
        for child in list_dicts(node.get("children")):
            visit(child)

    root = dsl.get("root")
    if isinstance(root, dict):
        visit(root)
    return dict(sorted(counts.items()))


def sum_count(counts: dict[str, int], *keys: str) -> int:
    return sum(int(counts.get(key) or 0) for key in keys)


def derive_record_metrics(record: dict[str, Any]) -> None:
    replay_summary = record.get("summaries", {}).get("replayPlan", {})
    materialization_summary = record.get("summaries", {}).get("materialization", {})
    ownership_summary = record.get("summaries", {}).get("ownershipConservation", {})
    perception_summary = record.get("summaries", {}).get("perceptionModel", {})
    compiler_summary = record.get("summaries", {}).get("perceptionSourceCompiler", {})
    fate_summary = record.get("summaries", {}).get("perceptionFateTrace", {})
    if isinstance(perception_summary, dict):
        record["perceptionCandidateCount"] = int(perception_summary.get("candidateCount") or 0)
    if isinstance(compiler_summary, dict):
        record["compiledSourceObjectCount"] = int(compiler_summary.get("compiledSourceObjectCount") or 0)
        record["compiledControlBackgroundCount"] = int(compiler_summary.get("compiledControlBackgroundCount") or 0)
        record["compiledRasterIconCount"] = int(compiler_summary.get("compiledRasterIconCount") or 0)
    if isinstance(fate_summary, dict):
        record["perceptionFateTraceCount"] = int(fate_summary.get("traceCount") or 0)
        record["perceptionFateBlockedCount"] = int(fate_summary.get("blockedCount") or 0)
    if isinstance(replay_summary, dict):
        record["plannedShapeReplayCount"] = int(replay_summary.get("plannedShapeReplayCount") or 0)
        record["plannedIconReplayCount"] = int(replay_summary.get("plannedIconReplayCount") or 0)
        record["copiedImageAssetCleanupTargetCount"] = int(replay_summary.get("copiedImageAssetCleanupTargetCount") or 0)
        record["cleanupTargetCount"] = int(replay_summary.get("fallbackCleanupTargetCount") or 0) + int(
            replay_summary.get("copiedImageAssetCleanupTargetCount") or 0
        )
    if isinstance(materialization_summary, dict):
        record["copiedImageAssetShapeErasedCount"] = int(materialization_summary.get("copiedImageAssetShapeErasedCount") or 0)
        record["copiedImageAssetInternalErasedCount"] = int(materialization_summary.get("copiedImageAssetInternalErasedCount") or 0)
        record["materializedVisibleNodeCount"] = int(materialization_summary.get("visibleNodeCount") or 0)
        record["executedCleanupCount"] = (
            int(materialization_summary.get("fallbackErasedBBoxCount") or 0)
            + int(materialization_summary.get("copiedImageAssetTextErasedCount") or 0)
            + int(materialization_summary.get("copiedImageAssetInternalErasedCount") or 0)
            + int(materialization_summary.get("copiedImageAssetShapeErasedCount") or 0)
        )
    dsl_visual_summary = record.get("summaries", {}).get("dslVisualComparison", {})
    if isinstance(dsl_visual_summary, dict):
        record["dslVisualNormalizedMeanAbsError"] = optional_float(dsl_visual_summary.get("normalizedMeanAbsError"))
        record["dslVisualChangedPixelRatio10"] = optional_float(dsl_visual_summary.get("changedPixelRatio10"))
        record["dslVisualGateNormalizedMeanAbsError"] = optional_float(
            dsl_visual_summary.get("gateNormalizedMeanAbsError", dsl_visual_summary.get("normalizedMeanAbsError"))
        )
        record["dslVisualGateChangedPixelRatio10"] = optional_float(
            dsl_visual_summary.get("gateChangedPixelRatio10", dsl_visual_summary.get("changedPixelRatio10"))
        )
    conflict_type_counts = ownership_summary.get("conflictTypeCounts", {}) if isinstance(ownership_summary, dict) else {}
    if isinstance(conflict_type_counts, dict):
        record["ownershipConflictCount"] = sum(int(value or 0) for value in conflict_type_counts.values())
    if record.get("status") == "completed" and record.get("errors"):
        record["degradedReason"] = "artifact_or_asset_validation_error"


def optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def validate_dsl_assets(record: dict[str, Any], dsl_path: Path, *, base_url: str) -> None:
    if not dsl_path.exists():
        return
    try:
        dsl = json.loads(dsl_path.read_text(encoding="utf-8"))
    except Exception as error:  # noqa: BLE001 - ledger should preserve parse failures.
        record["errors"].append({"type": "dsl_parse_error", "message": str(error)})
        return
    for asset in list_dicts(dsl.get("assets")):
        url = str(asset.get("url") or "")
        if not url:
            record["assetFetches"].append({"assetId": asset.get("assetId"), "url": url, "ok": False, "reason": "missing_url"})
            continue
        fetch = fetch_asset_head_or_get(url, base_url=base_url)
        fetch["assetId"] = asset.get("assetId")
        fetch["role"] = asset.get("role")
        record["assetFetches"].append(fetch)
    record["assetFetchCount"] = len(record["assetFetches"])
    record["assetFetchFailedCount"] = sum(1 for item in record["assetFetches"] if not item.get("ok"))
    for item in record["assetFetches"]:
        if not item.get("ok"):
            record["errors"].append({"type": "asset_fetch_failed", **item})
    if record.get("assetFetchFailedCount") and record.get("status") == "completed":
        record["degradedReason"] = "asset_fetch_failed"


def fetch_asset_head_or_get(url: str, *, base_url: str) -> dict[str, Any]:
    request_url = url
    if url.startswith(base_url):
        request_url = url
    elif url.startswith("/"):
        request_url = f"{base_url}{url}"
    elif url.startswith("http://") or url.startswith("https://"):
        request_url = url
    else:
        return {"url": url, "ok": False, "reason": "non_fetchable_relative_url"}
    try:
        request = urllib.request.Request(request_url, method="GET")
        with urllib.request.urlopen(request, timeout=10) as response:
            sample = response.read(8)
            return {
                "url": url,
                "ok": response.status == 200,
                "status": response.status,
                "pngHeader": sample.startswith(b"\x89PNG\r\n\x1a\n"),
            }
    except Exception as error:  # noqa: BLE001 - ledger should keep per-asset failures.
        return {"url": url, "ok": False, "reason": error.__class__.__name__, "message": str(error)}


def build_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    conflict_counts: dict[str, int] = {}
    failed = 0
    supported = 0
    unsupported = 0
    supported_failed = 0
    missing_artifacts = 0
    asset_fetch_failed = 0
    backend_crash = 0
    degraded = 0
    total_visible_claims = 0
    total_visible_overlap_conflicts = 0
    total_composite_media = 0
    total_internal_candidates = 0
    total_accepted_internal_candidates = 0
    total_rejected_internal_fragments = 0
    total_matched_internal_groups = 0
    total_transparent_asset_candidates = 0
    total_transparent_asset_allowed = 0
    total_transparent_asset_rejected = 0
    total_promoted_internal_source_objects = 0
    total_sibling_group_candidates = 0
    total_layout_energy_candidates = 0
    total_auto_layout_allow_candidates = 0
    total_design_token_candidates = 0
    total_b_stage_repair_cost = 0
    total_controlled_structure_groups = 0
    total_dsl_visual_mean_error = 0.0
    total_dsl_visual_gate_mean_error = 0.0
    dsl_visual_count = 0
    max_dsl_visual_changed_pixel_ratio10 = 0.0
    max_dsl_visual_gate_changed_pixel_ratio10 = 0.0
    total_perception_candidates = 0
    total_compiled_source_objects = 0
    total_compiled_controls = 0
    total_compiled_icons = 0
    total_perception_fate_traces = 0
    total_perception_fate_blocked = 0
    total_planned_shape_replay = 0
    total_planned_icon_replay = 0
    total_copied_cleanup_targets = 0
    total_copied_shape_erased = 0
    total_copied_internal_erased = 0
    total_materialized_visible_nodes = 0
    for record in records:
        if record.get("uploadSupported"):
            supported += 1
        else:
            unsupported += 1
        if record.get("status") != "completed":
            failed += 1
            if record.get("uploadSupported"):
                supported_failed += 1
        if record.get("degradedReason"):
            degraded += 1
        total_perception_candidates += int(record.get("perceptionCandidateCount") or 0)
        total_compiled_source_objects += int(record.get("compiledSourceObjectCount") or 0)
        total_compiled_controls += int(record.get("compiledControlBackgroundCount") or 0)
        total_compiled_icons += int(record.get("compiledRasterIconCount") or 0)
        total_perception_fate_traces += int(record.get("perceptionFateTraceCount") or 0)
        total_perception_fate_blocked += int(record.get("perceptionFateBlockedCount") or 0)
        total_planned_shape_replay += int(record.get("plannedShapeReplayCount") or 0)
        total_planned_icon_replay += int(record.get("plannedIconReplayCount") or 0)
        total_copied_cleanup_targets += int(record.get("copiedImageAssetCleanupTargetCount") or 0)
        total_copied_shape_erased += int(record.get("copiedImageAssetShapeErasedCount") or 0)
        total_copied_internal_erased += int(record.get("copiedImageAssetInternalErasedCount") or 0)
        total_materialized_visible_nodes += int(record.get("materializedVisibleNodeCount") or 0)
        if any(error.get("type") == "backend_process_exited" for error in record.get("errors", [])):
            backend_crash += 1
        missing_artifacts += sum(1 for error in record.get("errors", []) if error.get("type") == "missing_artifact")
        asset_fetch_failed += int(record.get("assetFetchFailedCount") or 0)
        ownership_summary = record.get("summaries", {}).get("ownershipConservation", {})
        total_visible_claims += int(ownership_summary.get("visibleReplayClaimCount") or 0)
        media_internal_summary = record.get("summaries", {}).get("mediaInternalDecomposition", {})
        total_composite_media += int(media_internal_summary.get("compositeMediaCount") or 0)
        total_internal_candidates += int(media_internal_summary.get("internalCandidateCount") or 0)
        total_accepted_internal_candidates += int(media_internal_summary.get("acceptedInternalCandidateCount") or 0)
        total_rejected_internal_fragments += int(media_internal_summary.get("rejectedFragmentCount") or 0)
        total_matched_internal_groups += int(media_internal_summary.get("matchedInternalGroupCount") or 0)
        transparent_summary = record.get("summaries", {}).get("transparentAssets", {})
        total_transparent_asset_candidates += int(transparent_summary.get("candidateCount") or 0)
        total_transparent_asset_allowed += int(transparent_summary.get("allowedCount") or 0)
        total_transparent_asset_rejected += int(transparent_summary.get("rejectedCount") or 0)
        promotion_summary = record.get("summaries", {}).get("internalSourcePromotion", {})
        total_promoted_internal_source_objects += int(promotion_summary.get("promotedSourceObjectCount") or 0)
        sibling_summary = record.get("summaries", {}).get("siblingGroups", {})
        total_sibling_group_candidates += int(sibling_summary.get("siblingGroupCandidateCount") or 0)
        layout_summary = record.get("summaries", {}).get("layoutEnergy", {})
        total_layout_energy_candidates += int(layout_summary.get("layoutEnergyCandidateCount") or 0)
        auto_layout_summary = record.get("summaries", {}).get("autoLayoutPermission", {})
        total_auto_layout_allow_candidates += int(auto_layout_summary.get("allowCandidateCount") or 0)
        design_token_summary = record.get("summaries", {}).get("designTokens", {})
        total_design_token_candidates += sum(
            int(design_token_summary.get(key) or 0)
            for key in ["colorTokenCount", "textStyleTokenCount", "radiusTokenCount", "spacingTokenCount"]
        )
        b_stage_summary = record.get("summaries", {}).get("bStageQuality", {})
        total_b_stage_repair_cost += int(b_stage_summary.get("repairCost") or 0)
        materialization_summary = record.get("summaries", {}).get("materialization", {})
        total_controlled_structure_groups += int(materialization_summary.get("controlledStructureGroupCount") or 0)
        dsl_visual_summary = record.get("summaries", {}).get("dslVisualComparison", {})
        if dsl_visual_summary:
            total_dsl_visual_mean_error += float(dsl_visual_summary.get("normalizedMeanAbsError") or 0.0)
            total_dsl_visual_gate_mean_error += float(
                dsl_visual_summary.get("gateNormalizedMeanAbsError", dsl_visual_summary.get("normalizedMeanAbsError")) or 0.0
            )
            max_dsl_visual_changed_pixel_ratio10 = max(
                max_dsl_visual_changed_pixel_ratio10,
                float(dsl_visual_summary.get("changedPixelRatio10") or 0.0),
            )
            max_dsl_visual_gate_changed_pixel_ratio10 = max(
                max_dsl_visual_gate_changed_pixel_ratio10,
                float(dsl_visual_summary.get("gateChangedPixelRatio10", dsl_visual_summary.get("changedPixelRatio10")) or 0.0),
            )
            dsl_visual_count += 1
        conflict_type_counts = ownership_summary.get("conflictTypeCounts", {})
        if isinstance(conflict_type_counts, dict):
            for key, value in conflict_type_counts.items():
                conflict_counts[str(key)] = conflict_counts.get(str(key), 0) + int(value)
        total_visible_overlap_conflicts += int(conflict_type_counts.get("visible_ownership_overlap") or 0) if isinstance(conflict_type_counts, dict) else 0
    return {
        "inputCount": len(records),
        "supportedInputCount": supported,
        "unsupportedInputCount": unsupported,
        "completedTaskCount": sum(1 for record in records if record.get("status") == "completed"),
        "supportedCompletedTaskCount": sum(1 for record in records if record.get("uploadSupported") and record.get("status") == "completed"),
        "failedTaskCount": failed,
        "supportedFailedCount": supported_failed,
        "degradedRecordCount": degraded,
        "backendCrashCount": backend_crash,
        "missingArtifactCount": missing_artifacts,
        "assetFetchFailedCount": asset_fetch_failed,
        "totalVisibleReplayClaimCount": total_visible_claims,
        "totalVisibleOwnershipOverlapConflicts": total_visible_overlap_conflicts,
        "totalCompositeMediaCount": total_composite_media,
        "totalInternalCandidateCount": total_internal_candidates,
        "totalAcceptedInternalCandidateCount": total_accepted_internal_candidates,
        "totalRejectedInternalFragmentCount": total_rejected_internal_fragments,
        "totalMatchedInternalGroupCount": total_matched_internal_groups,
        "totalTransparentAssetCandidateCount": total_transparent_asset_candidates,
        "totalTransparentAssetAllowedCount": total_transparent_asset_allowed,
        "totalTransparentAssetRejectedCount": total_transparent_asset_rejected,
        "totalPromotedInternalSourceObjectCount": total_promoted_internal_source_objects,
        "totalSiblingGroupCandidateCount": total_sibling_group_candidates,
        "totalLayoutEnergyCandidateCount": total_layout_energy_candidates,
        "totalAutoLayoutAllowCandidateCount": total_auto_layout_allow_candidates,
        "totalDesignTokenCandidateCount": total_design_token_candidates,
        "totalBStageRepairCost": total_b_stage_repair_cost,
        "totalControlledStructureGroupCount": total_controlled_structure_groups,
        "totalPerceptionCandidateCount": total_perception_candidates,
        "totalCompiledSourceObjectCount": total_compiled_source_objects,
        "totalCompiledControlBackgroundCount": total_compiled_controls,
        "totalCompiledRasterIconCount": total_compiled_icons,
        "totalPerceptionFateTraceCount": total_perception_fate_traces,
        "totalPerceptionFateBlockedCount": total_perception_fate_blocked,
        "totalPlannedShapeReplayCount": total_planned_shape_replay,
        "totalPlannedIconReplayCount": total_planned_icon_replay,
        "totalCopiedImageAssetCleanupTargetCount": total_copied_cleanup_targets,
        "totalCopiedImageAssetShapeErasedCount": total_copied_shape_erased,
        "totalCopiedImageAssetInternalErasedCount": total_copied_internal_erased,
        "totalMaterializedVisibleNodeCount": total_materialized_visible_nodes,
        "averageDslVisualNormalizedMeanAbsError": round(total_dsl_visual_mean_error / max(1, dsl_visual_count), 6),
        "maxDslVisualChangedPixelRatio10": round(max_dsl_visual_changed_pixel_ratio10, 6),
        "averageDslVisualGateNormalizedMeanAbsError": round(total_dsl_visual_gate_mean_error / max(1, dsl_visual_count), 6),
        "maxDslVisualGateChangedPixelRatio10": round(max_dsl_visual_gate_changed_pixel_ratio10, 6),
        "ownershipConflictTypeCounts": dict(sorted(conflict_counts.items())),
    }


if __name__ == "__main__":
    raise SystemExit(main())
