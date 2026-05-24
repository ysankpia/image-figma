from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = Path("/Users/luhui/Downloads/m29")
SUPPORTED_SUFFIXES = {".png"}


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir).expanduser().resolve()
    image_paths = discover_images(input_dir)
    if not image_paths:
        raise SystemExit(f"No supported PNG files found under {input_dir}")
    output_dir = resolve_output_dir(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    port = args.port or find_free_port()
    storage_root = output_dir / "storage"
    database_path = storage_root / "app.db"
    log_path = output_dir / "backend.log"
    process, log_file = start_backend(port=port, storage_root=storage_root, database_path=database_path, log_path=log_path)
    base_url = f"http://127.0.0.1:{port}"
    started_at = datetime.now(UTC).isoformat()
    try:
        wait_for_health(base_url, timeout_seconds=args.startup_timeout)
        records = []
        for index, path in enumerate(image_paths, start=1):
            print(f"[batch] {index}/{len(image_paths)} upload-preview {path.name}", flush=True)
            record = run_one(base_url, path, storage_root, poll_timeout_seconds=args.poll_timeout)
            records.append(record)
            print(f"[batch] {index}/{len(image_paths)} status={record['status']} errors={len(record['errors'])}", flush=True)
            if record["status"] != "completed" or record["errors"]:
                print("[batch] stopping after first failed record to keep validation serial", flush=True)
                break
    finally:
        stop_backend(process)
        log_file.close()

    summary = build_summary(records)
    ledger = {
        "schemaName": "UploadPreviewBatchValidationLedger",
        "schemaVersion": "0.1",
        "createdAt": datetime.now(UTC).isoformat(),
        "startedAt": started_at,
        "inputDir": str(input_dir),
        "outputDir": str(output_dir),
        "backendBaseUrl": base_url,
        "backendLog": str(log_path),
        "storageRoot": str(storage_root),
        "summary": summary,
        "records": records,
    }
    ledger_path = output_dir / "upload_preview_batch_validation.json"
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ledger": str(ledger_path), "summary": summary}, ensure_ascii=False, indent=2))
    return 0 if summary["failedTaskCount"] == 0 and summary["missingArtifactCount"] == 0 else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run real upload-preview batch validation through the HTTP API.")
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR))
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--startup-timeout", type=float, default=30.0)
    parser.add_argument("--poll-timeout", type=float, default=180.0)
    return parser.parse_args()


def resolve_output_dir(value: str) -> Path:
    if value.strip():
        return Path(value).expanduser().resolve()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return (BACKEND_ROOT / "tmp" / "validation" / f"upload_preview_batch_{stamp}").resolve()


def discover_images(input_dir: Path) -> list[Path]:
    return sorted(path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES)


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def start_backend(*, port: int, storage_root: Path, database_path: Path, log_path: Path) -> tuple[subprocess.Popen[str], TextIO]:
    env = os.environ.copy()
    env.update(
        {
            "STORAGE_ROOT": str(storage_root),
            "DATABASE_PATH": str(database_path),
            "PUBLIC_BASE_URL": f"http://127.0.0.1:{port}",
            "UPLOAD_PREVIEW_PROFILE": "production",
            "IMAGE_FIGMA_LOAD_LOCAL_ENV": "true",
        }
    )
    log_file = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [
            "uv",
            "run",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=BACKEND_ROOT,
        env=env,
        text=True,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    return process, log_file


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


def run_one(base_url: str, image_path: Path, storage_root: Path, *, poll_timeout_seconds: float) -> dict[str, Any]:
    record: dict[str, Any] = {
        "inputPath": str(image_path),
        "filename": image_path.name,
        "status": "not_started",
        "taskId": None,
        "taskStage": None,
        "artifacts": {},
        "summaries": {},
        "errors": [],
    }
    try:
        upload = upload_png(base_url, image_path)
        task_id = upload["data"]["taskId"]
        record["taskId"] = task_id
        task = wait_for_task(base_url, task_id, timeout_seconds=poll_timeout_seconds)
        record["status"] = task["data"]["status"]
        record["taskStage"] = task["data"]["stage"]
        collect_artifacts(record, storage_root, task_id)
        if record["status"] != "completed":
            record["errors"].append({"type": "task_not_completed", "task": task})
    except Exception as error:  # noqa: BLE001 - batch ledger must keep per-file failures.
        record["status"] = "error"
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


def collect_artifacts(record: dict[str, Any], storage_root: Path, task_id: str) -> None:
    root = storage_root / "upload_previews" / task_id
    artifact_paths = {
        "stageTimings": root / "stage_timings.json",
        "dsl": root / "materialized_design" / "design.dsl.json",
        "materializationReport": root / "materialized_design" / "materialization_report.json",
        "ownershipConservationReport": root / "m29_ownership_conservation" / "ownership_conservation_report.json",
        "hierarchyCandidateReport": root / "m29_hierarchy_candidates" / "hierarchy_candidate_report.json",
        "siblingGroupCandidateReport": root / "m29_sibling_groups" / "sibling_group_candidate_report.json",
        "layoutEnergyReport": root / "m29_layout_energy" / "layout_energy_report.json",
        "autoLayoutPermissionReport": root / "m29_auto_layout_permission" / "auto_layout_permission_report.json",
        "designTokenReport": root / "m29_design_tokens" / "design_token_report.json",
        "bStageQualityReport": root / "m29_b_stage_quality" / "b_stage_quality_report.json",
        "replayPlan": root / "m29_5" / "replay_plan.json",
    }
    for key, path in artifact_paths.items():
        exists = path.exists()
        record["artifacts"][key] = {"path": str(path), "exists": exists}
        if not exists:
            record["errors"].append({"type": "missing_artifact", "artifact": key, "path": str(path)})
    load_summary(record, "stageTimings", artifact_paths["stageTimings"])
    load_summary(record, "materialization", artifact_paths["materializationReport"])
    load_summary(record, "ownershipConservation", artifact_paths["ownershipConservationReport"])
    load_summary(record, "hierarchyCandidates", artifact_paths["hierarchyCandidateReport"])
    load_summary(record, "siblingGroups", artifact_paths["siblingGroupCandidateReport"])
    load_summary(record, "layoutEnergy", artifact_paths["layoutEnergyReport"])
    load_summary(record, "autoLayoutPermission", artifact_paths["autoLayoutPermissionReport"])
    load_summary(record, "designTokens", artifact_paths["designTokenReport"])
    load_summary(record, "bStageQuality", artifact_paths["bStageQualityReport"])
    load_summary(record, "replayPlan", artifact_paths["replayPlan"])


def load_summary(record: dict[str, Any], key: str, path: Path) -> None:
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
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


def build_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    conflict_counts: dict[str, int] = {}
    failed = 0
    missing_artifacts = 0
    total_visible_claims = 0
    total_visible_overlap_conflicts = 0
    total_sibling_group_candidates = 0
    total_layout_energy_candidates = 0
    total_auto_layout_allow_candidates = 0
    total_design_token_candidates = 0
    total_b_stage_repair_cost = 0
    for record in records:
        if record.get("status") != "completed":
            failed += 1
        missing_artifacts += sum(1 for error in record.get("errors", []) if error.get("type") == "missing_artifact")
        ownership_summary = record.get("summaries", {}).get("ownershipConservation", {})
        total_visible_claims += int(ownership_summary.get("visibleReplayClaimCount") or 0)
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
        conflict_type_counts = ownership_summary.get("conflictTypeCounts", {})
        if isinstance(conflict_type_counts, dict):
            for key, value in conflict_type_counts.items():
                conflict_counts[str(key)] = conflict_counts.get(str(key), 0) + int(value)
        total_visible_overlap_conflicts += int(conflict_type_counts.get("visible_ownership_overlap") or 0) if isinstance(conflict_type_counts, dict) else 0
    return {
        "inputCount": len(records),
        "completedTaskCount": sum(1 for record in records if record.get("status") == "completed"),
        "failedTaskCount": failed,
        "missingArtifactCount": missing_artifacts,
        "totalVisibleReplayClaimCount": total_visible_claims,
        "totalVisibleOwnershipOverlapConflicts": total_visible_overlap_conflicts,
        "totalSiblingGroupCandidateCount": total_sibling_group_candidates,
        "totalLayoutEnergyCandidateCount": total_layout_energy_candidates,
        "totalAutoLayoutAllowCandidateCount": total_auto_layout_allow_candidates,
        "totalDesignTokenCandidateCount": total_design_token_candidates,
        "totalBStageRepairCost": total_b_stage_repair_cost,
        "ownershipConflictTypeCounts": dict(sorted(conflict_counts.items())),
    }


if __name__ == "__main__":
    raise SystemExit(main())
