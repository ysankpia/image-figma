from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def main() -> int:
    args = parse_args()
    model_path = Path(args.model).expanduser().resolve()
    input_path = Path(args.input).expanduser().resolve()
    output_dir = resolve_output_dir(args.output_dir)
    overlays_dir = output_dir / "overlays"
    overlays_dir.mkdir(parents=True, exist_ok=True)

    np, ort, image_module, image_draw_module, image_font_module = import_probe_dependencies()
    inputs = discover_inputs(input_path, recursive=args.recursive, max_files=args.max_files)
    if not inputs:
        raise SystemExit(f"No supported images found: {input_path}")
    if not model_path.is_file():
        raise SystemExit(f"Model file does not exist: {model_path}")

    session = create_session(ort, model_path, args.provider)
    input_meta = session.get_inputs()[0]
    output_meta = session.get_outputs()[0]
    records: list[dict[str, Any]] = []

    for index, image_path in enumerate(inputs, start=1):
        print(f"[probe] {index}/{len(inputs)} {image_path}", flush=True)
        image = image_module.open(image_path).convert("RGB")
        tensor, transform = preprocess_image(np, image_module, image, input_size=args.input_size)
        outputs = session.run([output_meta.name], {input_meta.name: tensor})
        raw_output = outputs[0]
        candidates = decode_yolo_like_output(
            np,
            raw_output,
            transform=transform,
            score_threshold=args.score_threshold,
            min_box_px=args.min_box_px,
        )
        candidates = nms_candidates(candidates, iou_threshold=args.nms_threshold)
        candidates = candidates[: args.top_k]
        overlay_path = overlays_dir / f"{safe_stem(image_path)}_probe.png"
        draw_overlay(
            image=image,
            candidates=candidates,
            output_path=overlay_path,
            image_draw_module=image_draw_module,
            image_font_module=image_font_module,
        )
        records.append(
            {
                "image": str(image_path),
                "size": [image.width, image.height],
                "rawOutputShape": list(raw_output.shape),
                "candidateCount": len(candidates),
                "top": candidates,
                "overlay": str(overlay_path),
            }
        )

    report = {
        "schemaName": "OnnxModelProbeReport",
        "schemaVersion": "0.1",
        "createdAt": datetime.now(UTC).isoformat(),
        "modelPath": str(model_path),
        "modelSha256": sha256_file(model_path),
        "input": str(input_path),
        "outputDir": str(output_dir),
        "inputSize": args.input_size,
        "scoreThreshold": args.score_threshold,
        "nmsThreshold": args.nms_threshold,
        "topK": args.top_k,
        "provider": args.provider,
        "model": {
            "inputName": input_meta.name,
            "inputShape": list(input_meta.shape),
            "inputType": input_meta.type,
            "outputName": output_meta.name,
            "outputShape": list(output_meta.shape),
            "outputType": output_meta.type,
            "providers": session.get_providers(),
        },
        "summary": {
            "imageCount": len(records),
            "candidateCount": sum(record["candidateCount"] for record in records),
        },
        "records": records,
    }
    report_path = output_dir / "probe_results.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(report_path), "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a standalone ONNX object-proposal probe on local images. "
            "This does not integrate with upload-preview or M29 runtime."
        )
    )
    parser.add_argument("--model", required=True, help="Path to an ONNX model file.")
    parser.add_argument("--input", required=True, help="Image file or directory to probe.")
    parser.add_argument(
        "--output-dir",
        default="",
        help="Output directory for probe_results.json and overlay images. Defaults to backend/tmp/model_probe_<timestamp>.",
    )
    parser.add_argument("--input-size", type=int, default=960, help="Square letterbox input size.")
    parser.add_argument("--score-threshold", type=float, default=0.05)
    parser.add_argument("--nms-threshold", type=float, default=0.45)
    parser.add_argument("--top-k", type=int, default=60)
    parser.add_argument("--min-box-px", type=float, default=3.0)
    parser.add_argument("--provider", default="CPUExecutionProvider")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--max-files", type=int, default=0, help="Limit sorted inputs. 0 means no limit.")
    return parser.parse_args()


def import_probe_dependencies() -> tuple[Any, Any, Any, Any, Any]:
    try:
        import numpy as np
        import onnxruntime as ort
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as error:
        raise SystemExit(
            "Missing probe dependency. Run with:\n"
            "  uv run --with onnxruntime --with pillow --with numpy "
            "python scripts/probe_onnx_model.py --model /path/model.onnx --input /path/images"
        ) from error
    return np, ort, Image, ImageDraw, ImageFont


def resolve_output_dir(value: str) -> Path:
    if value.strip():
        return Path(value).expanduser().resolve()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return (BACKEND_ROOT / "tmp" / f"model_probe_{stamp}").resolve()


def discover_inputs(input_path: Path, *, recursive: bool, max_files: int) -> list[Path]:
    if input_path.is_file():
        paths = [input_path] if input_path.suffix.lower() in IMAGE_SUFFIXES else []
    else:
        iterator = input_path.rglob("*") if recursive else input_path.iterdir()
        paths = sorted(path for path in iterator if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)
    if max_files > 0:
        return paths[:max_files]
    return paths


def create_session(ort: Any, model_path: Path, provider: str) -> Any:
    available = set(ort.get_available_providers())
    providers = [provider] if provider in available else ["CPUExecutionProvider"]
    if "CPUExecutionProvider" not in providers:
        providers.append("CPUExecutionProvider")
    return ort.InferenceSession(str(model_path), providers=providers)


def preprocess_image(np: Any, image_module: Any, image: Any, *, input_size: int) -> tuple[Any, dict[str, float]]:
    width, height = image.size
    scale = min(input_size / width, input_size / height)
    resized_width = max(1, round(width * scale))
    resized_height = max(1, round(height * scale))
    pad_x = (input_size - resized_width) / 2.0
    pad_y = (input_size - resized_height) / 2.0

    canvas = image_module.new("RGB", (input_size, input_size), (114, 114, 114))
    resized = image.resize((resized_width, resized_height))
    canvas.paste(resized, (round(pad_x), round(pad_y)))
    array = np.asarray(canvas).astype("float32") / 255.0
    tensor = np.transpose(array, (2, 0, 1))[None, :, :, :]
    return tensor, {
        "scale": float(scale),
        "padX": float(pad_x),
        "padY": float(pad_y),
        "imageWidth": float(width),
        "imageHeight": float(height),
    }


def decode_yolo_like_output(
    np: Any,
    raw_output: Any,
    *,
    transform: dict[str, float],
    score_threshold: float,
    min_box_px: float,
) -> list[dict[str, Any]]:
    data = np.asarray(raw_output)
    if data.ndim != 3 or data.shape[0] != 1:
        raise RuntimeError(f"Unsupported output shape {list(data.shape)}; expected [1, 5, anchors] or [1, anchors, 5].")
    if data.shape[1] == 5:
        rows = data[0].T
    elif data.shape[2] == 5:
        rows = data[0]
    else:
        raise RuntimeError(f"Unsupported output shape {list(data.shape)}; expected one dimension of size 5.")

    scale = transform["scale"]
    pad_x = transform["padX"]
    pad_y = transform["padY"]
    image_width = transform["imageWidth"]
    image_height = transform["imageHeight"]
    candidates: list[dict[str, Any]] = []
    scores = rows[:, 4]
    if float(scores.min(initial=0.0)) < 0.0 or float(scores.max(initial=0.0)) > 1.0:
        scores = 1.0 / (1.0 + np.exp(-scores))

    for row, score_value in zip(rows, scores, strict=False):
        score = float(score_value)
        if score < score_threshold:
            continue
        cx, cy, width, height = [float(value) for value in row[:4]]
        x1 = (cx - width / 2.0 - pad_x) / scale
        y1 = (cy - height / 2.0 - pad_y) / scale
        x2 = (cx + width / 2.0 - pad_x) / scale
        y2 = (cy + height / 2.0 - pad_y) / scale
        x1 = clamp(x1, 0.0, image_width)
        y1 = clamp(y1, 0.0, image_height)
        x2 = clamp(x2, 0.0, image_width)
        y2 = clamp(y2, 0.0, image_height)
        box_width = x2 - x1
        box_height = y2 - y1
        if box_width < min_box_px or box_height < min_box_px:
            continue
        area_ratio = (box_width * box_height) / max(1.0, image_width * image_height)
        candidates.append(
            {
                "bbox": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                "score": round(score, 6),
                "areaRatio": round(area_ratio, 6),
            }
        )
    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates


def nms_candidates(candidates: list[dict[str, Any]], *, iou_threshold: float) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for candidate in candidates:
        if all(iou(candidate["bbox"], kept_candidate["bbox"]) < iou_threshold for kept_candidate in kept):
            kept.append(candidate)
    return kept


def iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if intersection <= 0.0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return intersection / max(1e-6, area_a + area_b - intersection)


def draw_overlay(
    *,
    image: Any,
    candidates: list[dict[str, Any]],
    output_path: Path,
    image_draw_module: Any,
    image_font_module: Any,
) -> None:
    overlay = image.copy()
    draw = image_draw_module.Draw(overlay)
    try:
        font = image_font_module.truetype("Arial.ttf", 16)
    except OSError:
        font = image_font_module.load_default()
    colors = ["#ff3b30", "#007aff", "#34c759", "#ff9500", "#af52de", "#00c7be"]
    for index, candidate in enumerate(candidates, start=1):
        x1, y1, x2, y2 = candidate["bbox"]
        color = colors[(index - 1) % len(colors)]
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
        label = f"{index}:{candidate['score']:.2f}"
        label_bbox = draw.textbbox((x1, y1), label, font=font)
        label_width = label_bbox[2] - label_bbox[0] + 6
        label_height = label_bbox[3] - label_bbox[1] + 4
        label_y = max(0, y1 - label_height)
        draw.rectangle([x1, label_y, x1 + label_width, label_y + label_height], fill=color)
        draw.text((x1 + 3, label_y + 2), label, fill="#ffffff", font=font)
    overlay.save(output_path)


def safe_stem(path: Path) -> str:
    value = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in path.stem)
    return value[:120] or "image"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clamp(value: float, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)


if __name__ == "__main__":
    raise SystemExit(main())
