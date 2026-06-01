#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import shutil
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import load_config, load_dotenv_local
from app.pipeline import Pipeline


SAMPLES = [
    ("t018", REPO_ROOT / "docs/reference/codia-samples/images/腾讯动漫_018_1440.png"),
    ("t022", REPO_ROOT / "docs/reference/codia-samples/images/腾讯动漫_022_1440.png"),
    ("lizhi", REPO_ROOT / "docs/reference/codia-samples/images/荔枝_011_1440.png"),
    ("xianyu", REPO_ROOT / "docs/reference/codia-samples/images/闲鱼.png"),
]


async def main() -> None:
    load_dotenv_local()
    config = load_config()
    pipeline = Pipeline(config)
    output_root = Path("/tmp/backend_python_omni_vlm_smoke")
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    rows: list[dict] = []
    for name, image_path in SAMPLES:
        out = output_root / name
        await pipeline.run(str(image_path), str(out), f"smoke_{name}")
        summary_path = out / "report/pipeline_summary.v1.json"
        summary = json.loads(summary_path.read_text())
        rows.append({"case": name, **summary})

    print("| case | OCR | candidates | classified | text | image | shape | assets | tiny images | text-overlap images | provider errors |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        print(
            f"| {row['case']} | {row['ocr_text_count']} | {row['omni_candidate_count']} | "
            f"{row['vlm_classified_count']} | {row['emitted_text_count']} | "
            f"{row['emitted_image_count']} | {row['emitted_shape_count']} | "
            f"{row['asset_count']} | {row['tiny_image_count']} | "
            f"{row['text_overlap_image_count']} | {row['provider_error_count']} |"
        )
    print(f"\nArtifacts: {output_root}")


if __name__ == "__main__":
    asyncio.run(main())
