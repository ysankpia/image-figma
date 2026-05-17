from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir).expanduser().resolve()
    storage_root = Path(args.storage_root).expanduser().resolve()
    providers = [provider.strip() for provider in args.providers.split(",") if provider.strip()]
    if not input_dir.exists():
        raise SystemExit(f"Input directory does not exist: {input_dir}")

    os.environ["STORAGE_ROOT"] = str(storage_root)
    os.environ["DATABASE_PATH"] = str(storage_root / "app.db")
    os.environ["PUBLIC_BASE_URL"] = args.public_base_url.rstrip("/")
    os.environ["PERCEPTION_BENCHMARK_ENABLED"] = "true"
    os.environ["PERCEPTION_BENCHMARK_PROVIDERS"] = ",".join(providers)
    if "opencv" in providers:
        os.environ["PERCEPTION_OPENCV_ENABLED"] = "true"
    if "sam2" in providers:
        os.environ["PERCEPTION_SAM2_ENABLED"] = "true"
    if "uied" in providers and os.getenv("PERCEPTION_UIED_COMMAND"):
        os.environ["PERCEPTION_UIED_ENABLED"] = "true"

    from app.main import create_app

    rows: list[dict[str, object]] = []
    with TestClient(create_app()) as client:
        for path in sorted(input_dir.glob("*.png")):
            response = client.post("/api/upload", files={"file": (path.name, path.read_bytes(), "image/png")})
            if response.status_code != 200:
                rows.append({"file": path.name, "uploadStatus": response.status_code, "error": response.json()})
                continue
            task_id = response.json()["data"]["taskId"]
            benchmark = client.get(f"/api/tasks/{task_id}/perception-benchmark")
            if benchmark.status_code != 200:
                rows.append(
                    {
                        "file": path.name,
                        "taskId": task_id,
                        "benchmarkStatus": benchmark.status_code,
                        "error": benchmark.json(),
                    }
                )
                continue
            document = benchmark.json()["data"]
            rows.append(
                {
                    "file": path.name,
                    "taskId": task_id,
                    "status": document["status"],
                    "recommendedProvider": document["comparison"].get("recommendedProvider"),
                    "meta": document["meta"],
                    "providers": [
                        {
                            "provider": provider["provider"],
                            "status": provider["status"],
                            "elapsedMs": provider["elapsedMs"],
                            "candidateCount": provider["candidateCount"],
                            "blockedCount": provider["blockedCount"],
                            "bottomNavLikelyHitCount": provider["bottomNavLikelyHitCount"],
                            "buttonArrowLikelyHitCount": provider["buttonArrowLikelyHitCount"],
                            "cardTileLikelyHitCount": provider["cardTileLikelyHitCount"],
                            "roomStatusLikelyHitCount": provider["roomStatusLikelyHitCount"],
                            "overlayPath": provider["overlay"]["assetPath"] if provider.get("overlay") else None,
                            "warnings": provider.get("warnings", []),
                        }
                        for provider in document["providers"]
                    ],
                }
            )

    summary = {
        "storageRoot": str(storage_root),
        "inputDir": str(input_dir),
        "providers": providers,
        "fileCount": len(rows),
        "rows": rows,
    }
    storage_root.mkdir(parents=True, exist_ok=True)
    json_path = storage_root / "m26_perception_summary.json"
    md_path = storage_root / "m26_perception_summary.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown_summary(summary), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


def build_markdown_summary(summary: dict[str, object]) -> str:
    lines = [
        "# M26 Perception Smoke Summary",
        "",
        f"- Input: `{summary['inputDir']}`",
        f"- Storage: `{summary['storageRoot']}`",
        f"- Providers: `{','.join(summary['providers'])}`",
        "",
        "| File | Recommended | Provider | Status | ms | Candidates | Blocked | Bottom nav | Button | Card/tile | Room |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["rows"]:
        providers = row.get("providers", []) if isinstance(row, dict) else []
        for provider in providers:
            lines.append(
                "| {file} | {recommended} | {provider} | {status} | {elapsed} | {candidates} | {blocked} | {bottom} | {button} | {card} | {room} |".format(
                    file=row.get("file"),
                    recommended=row.get("recommendedProvider"),
                    provider=provider.get("provider"),
                    status=provider.get("status"),
                    elapsed=provider.get("elapsedMs"),
                    candidates=provider.get("candidateCount"),
                    blocked=provider.get("blockedCount"),
                    bottom=provider.get("bottomNavLikelyHitCount"),
                    button=provider.get("buttonArrowLikelyHitCount"),
                    card=provider.get("cardTileLikelyHitCount"),
                    room=provider.get("roomStatusLikelyHitCount"),
                )
            )
    lines.extend(
        [
            "",
            "## Reading",
            "",
            "- `current_rules` 是 M20/M22/M25 baseline。",
            "- `opencv` 若显示 `unavailable`，说明本地没有启用或安装 OpenCV；这不是上传失败。",
            "- `sam2` 和 `uied` 默认是 optional/offline provider，缺模型或命令时显示 `unavailable`。",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run M26 perception benchmark smoke on a PNG directory.")
    parser.add_argument(
        "--input-dir",
        default="/Users/luhui/Downloads/宿舍床位可视化选择系统_UI设计图/学生端/",
    )
    parser.add_argument("--storage-root", default="storage/m26_perception_smoke")
    parser.add_argument("--providers", default="current_rules,opencv")
    parser.add_argument("--public-base-url", default="http://localhost:8000")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
