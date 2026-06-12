#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image


KNOWN_CLASSES = {
    0: "View",
    1: "ImageView",
    2: "Text",
    3: "Line",
}


def export_deki_yolo(model_path: Path, image_path: Path, output_path: Path, confidence: float) -> dict[str, Any]:
    if not model_path.exists():
        raise FileNotFoundError(f"Deki YOLO model not found: {model_path}")
    if not image_path.exists():
        raise FileNotFoundError(f"source image not found: {image_path}")

    from ultralytics import YOLO

    with Image.open(image_path) as image:
        width, height = image.size

    model = YOLO(str(model_path))
    results = model(str(image_path), conf=confidence, verbose=False)
    candidates: list[dict[str, Any]] = []
    index = 1
    for result in results:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue
        for box in boxes:
            coords = box.xyxy[0].tolist()
            x1 = max(0, min(width, int(round(coords[0]))))
            y1 = max(0, min(height, int(round(coords[1]))))
            x2 = max(0, min(width, int(round(coords[2]))))
            y2 = max(0, min(height, int(round(coords[3]))))
            if x2 <= x1 or y2 <= y1:
                continue
            class_id = int(box.cls[0].item())
            class_name = str(getattr(model, "names", {}).get(class_id, KNOWN_CLASSES.get(class_id, f"class_{class_id}")))
            candidates.append(
                {
                    "id": f"yolo_{index:04d}",
                    "classId": class_id,
                    "className": class_name,
                    "bbox": {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1},
                    "confidence": float(box.conf[0].item()),
                }
            )
            index += 1

    artifact = {
        "version": "deki_yolo_candidates.v1",
        "modelPath": str(model_path),
        "sourceImage": str(image_path),
        "canvas": {"width": width, "height": height},
        "candidates": candidates,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return artifact


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Deki YOLO boxes to deki_yolo_candidates.v1 JSON.")
    parser.add_argument("--model", required=True, help="Path to deki-yolo.pt.")
    parser.add_argument("--image", required=True, help="Source image path.")
    parser.add_argument("--out", required=True, help="Output JSON path.")
    parser.add_argument("--confidence", type=float, default=0.25, help="YOLO inference confidence threshold.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifact = export_deki_yolo(
        model_path=Path(args.model).expanduser().resolve(),
        image_path=Path(args.image).expanduser().resolve(),
        output_path=Path(args.out).expanduser().resolve(),
        confidence=float(args.confidence),
    )
    print(
        "deki_yolo_export: "
        f"boxes={len(artifact['candidates'])} "
        f"out={Path(args.out).expanduser().resolve()}"
    )


if __name__ == "__main__":
    main()
