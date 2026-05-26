from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.perception_model_report.decoder import decode_yolo_like_output, preprocess_image

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def main() -> int:
    args = parse_args()
    model_path = Path(args.model).expanduser().resolve()
    input_path = Path(args.input).expanduser().resolve()
    output_dir = resolve_output_dir(args.output_dir)
    overlays_dir = output_dir / "overlays"
    overlays_dir.mkdir(parents=True, exist_ok=True)

    ort, image_module, image_draw_module, image_font_module = import_probe_dependencies()
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
        tensor, transform = preprocess_image(image, input_size=args.input_size)
        outputs = session.run([output_meta.name], {input_meta.name: tensor})
        raw_output = outputs[0]
        candidates = decode_yolo_like_output(
            raw_output,
            transform=transform,
            score_threshold=args.score_threshold,
            min_box_px=args.min_box_px,
            nms_threshold=args.nms_threshold,
            top_k=args.top_k,
        )
        candidates = strip_raw_anchor_refs(candidates)
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


def import_probe_dependencies() -> tuple[Any, Any, Any, Any]:
    try:
        import onnxruntime as ort
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as error:
        raise SystemExit(
            "Missing probe dependency. Run with:\n"
            "  uv run --with onnxruntime --with pillow --with numpy "
            "python scripts/probe_onnx_model.py --model /path/model.onnx --input /path/images"
        ) from error
    return ort, Image, ImageDraw, ImageFont


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


def strip_raw_anchor_refs(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in candidate.items() if key != "rawAnchorIndex"} for candidate in candidates]


if __name__ == "__main__":
    raise SystemExit(main())
