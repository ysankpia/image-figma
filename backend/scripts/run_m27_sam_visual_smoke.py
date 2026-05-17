from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir).expanduser().resolve()
    storage_root = unique_output_dir(Path(args.output_dir).expanduser().resolve())
    checkpoint = Path(args.checkpoint or os.getenv("SAM_VISUAL_CANDIDATE_CHECKPOINT", "")).expanduser()
    if not input_dir.exists():
        raise SystemExit(f"Input directory does not exist: {input_dir}")
    if not checkpoint.exists():
        raise SystemExit(f"SAM2 checkpoint does not exist: {checkpoint}")

    os.environ["STORAGE_ROOT"] = str(storage_root)
    os.environ["DATABASE_PATH"] = str(storage_root / "app.db")
    os.environ["PUBLIC_BASE_URL"] = args.public_base_url.rstrip("/")
    os.environ["SAM_VISUAL_CANDIDATE_ENABLED"] = "true"
    os.environ["SAM_VISUAL_CANDIDATE_CHECKPOINT"] = str(checkpoint)
    if args.model_cfg:
        os.environ["SAM_VISUAL_CANDIDATE_MODEL_CFG"] = args.model_cfg
    if args.device:
        os.environ["SAM_VISUAL_CANDIDATE_DEVICE"] = args.device
    if args.max_image_edge:
        os.environ["SAM_VISUAL_CANDIDATE_MAX_IMAGE_EDGE"] = str(args.max_image_edge)

    from app.main import create_app

    rows: list[dict[str, object]] = []
    with TestClient(create_app()) as client:
        for path in sorted(input_dir.glob("*.png")):
            response = client.post("/api/upload", files={"file": (path.name, path.read_bytes(), "image/png")})
            if response.status_code != 200:
                rows.append({"file": path.name, "uploadStatus": response.status_code, "error": response.json()})
                continue
            task_id = response.json()["data"]["taskId"]
            result = client.get(f"/api/tasks/{task_id}/sam-visual-candidates")
            if result.status_code != 200:
                rows.append({"file": path.name, "taskId": task_id, "resultStatus": result.status_code, "error": result.json()})
                continue
            document = result.json()["data"]
            rows.append(
                {
                    "file": path.name,
                    "taskId": task_id,
                    "status": document["status"],
                    "sam": document.get("sam", {}),
                    "meta": document.get("meta", {}),
                    "candidateKinds": document.get("meta", {}).get("kindSummary", {}),
                    "blockedReasons": document.get("meta", {}).get("blockedReasonSummary", {}),
                    "overlayPath": document["overlay"]["assetPath"] if document.get("overlay") else None,
                    "warnings": document.get("warnings", []),
                }
            )

    summary = {
        "storageRoot": str(storage_root),
        "inputDir": str(input_dir),
        "checkpoint": str(checkpoint),
        "fileCount": len(rows),
        "rows": rows,
    }
    storage_root.mkdir(parents=True, exist_ok=True)
    json_path = storage_root / "m27_sam_visual_summary.json"
    md_path = storage_root / "m27_sam_visual_summary.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown_summary(summary), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


def unique_output_dir(path: Path) -> Path:
    if not path.exists():
        return path
    suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    return path.with_name(f"{path.name}_{suffix}")


def build_markdown_summary(summary: dict[str, object]) -> str:
    lines = [
        "# M27 SAM Visual Candidate Smoke Summary",
        "",
        f"- Input: `{summary['inputDir']}`",
        f"- Storage: `{summary['storageRoot']}`",
        f"- Checkpoint: `{summary['checkpoint']}`",
        "",
        "| File | Status | ms | Raw masks | Candidates | Blocked | Overlay |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in summary["rows"]:
        sam = row.get("sam", {}) if isinstance(row, dict) else {}
        meta = row.get("meta", {}) if isinstance(row, dict) else {}
        lines.append(
            "| {file} | {status} | {elapsed} | {raw} | {candidates} | {blocked} | {overlay} |".format(
                file=row.get("file"),
                status=row.get("status"),
                elapsed=sam.get("elapsedMs"),
                raw=meta.get("rawMaskCount"),
                candidates=meta.get("candidateCount"),
                blocked=meta.get("blockedCount"),
                overlay=row.get("overlayPath"),
            )
        )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- `candidateCount` 是通过 M27 text/cover/existing-icon/exclusion 过滤后的 SAM2 visual candidates。",
            "- `blockedReasons` 里如果主要是 text/line/border/exclusion，说明 SAM2 的碎片被正确挡住。",
            "- M27 输出只用于 M28 pool merge，不改变 DSL/Figma 可见输出。",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run M27 SAM visual candidate smoke on a PNG directory.")
    parser.add_argument("--input-dir", default="/Users/luhui/Downloads/宿舍床位可视化选择系统_UI设计图/学生端/")
    parser.add_argument("--output-dir", default="storage/m27_sam_visual_smoke")
    parser.add_argument("--checkpoint", default="/Volumes/WorkDrive/Models/sam2/sam2.1_hiera_tiny.pt")
    parser.add_argument("--model-cfg", default="")
    parser.add_argument("--device", default="")
    parser.add_argument("--max-image-edge", type=int, default=1280)
    parser.add_argument("--public-base-url", default="http://localhost:8000")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
