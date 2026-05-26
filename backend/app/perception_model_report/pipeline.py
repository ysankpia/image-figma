from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image

from .decoder import decode_yolo_like_output, preprocess_image
from .report import build_summary, normalize_candidates
from .types import PerceptionModelOptions, PerceptionModelReportResult, REPORT_ONLY_META
from .validation import validate_perception_model_report


def extract_perception_model_report(
    *,
    task_id: str,
    source_png: bytes,
    output_dir: Path,
    model_path: str | Path | None = None,
    options: PerceptionModelOptions | None = None,
    raw_output: Any | None = None,
    model_metadata: dict[str, Any] | None = None,
) -> PerceptionModelReportResult:
    options = options or PerceptionModelOptions()
    output_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    image = Image.open(bytes_to_file_like(source_png)).convert("RGB")
    tensor, transform = preprocess_image(image, input_size=options.input_size)
    output = raw_output
    metadata = dict(model_metadata or {})
    if output is None:
        if model_path is None:
            raise ValueError("perception model report requires model_path or raw_output")
        output, metadata = run_onnx_model(
            model_path=Path(model_path).expanduser().resolve(),
            tensor=tensor,
            provider=options.provider,
        )
    raw_candidates = decode_yolo_like_output(
        output,
        transform=transform,
        score_threshold=options.score_threshold,
        min_box_px=options.min_box_px,
        nms_threshold=options.nms_threshold,
        top_k=options.top_k,
    )
    candidates = normalize_candidates(raw_candidates, provider=str(metadata.get("provider") or "model_fp16_onnx"))
    report_path = output_dir / "perception_model_report.json"
    report = {
        "schemaName": "M29PerceptionModelReport",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "outputReport": str(report_path),
        "model": model_report_metadata(model_path=model_path, metadata=metadata),
        "image": {
            "width": image.width,
            "height": image.height,
            "preprocess": transform,
        },
        "options": options.to_dict(),
        "summary": build_summary(candidates=candidates, warnings=warnings),
        "candidates": candidates,
        "warnings": warnings,
        "meta": {
            "createdAt": datetime.now(UTC).isoformat(),
            "truthSource": "source_png_plus_model_object_proposals",
            **REPORT_ONLY_META,
        },
    }
    validate_perception_model_report(report)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return PerceptionModelReportResult(report=report, output_dir=output_dir)


def run_onnx_model(*, model_path: Path, tensor: Any, provider: str) -> tuple[Any, dict[str, Any]]:
    try:
        import onnxruntime as ort
    except ImportError as error:
        raise RuntimeError(
            "onnxruntime is not installed. Run with `uv run --with onnxruntime ...` "
            "or add the dependency only when model-first runtime integration is approved."
        ) from error
    if not model_path.is_file():
        raise FileNotFoundError(f"perception model file does not exist: {model_path}")
    available = set(ort.get_available_providers())
    providers = [provider] if provider in available else ["CPUExecutionProvider"]
    if "CPUExecutionProvider" not in providers:
        providers.append("CPUExecutionProvider")
    session = ort.InferenceSession(str(model_path), providers=providers)
    input_meta = session.get_inputs()[0]
    output_meta = session.get_outputs()[0]
    output = session.run([output_meta.name], {input_meta.name: tensor})[0]
    return output, {
        "provider": "model_fp16_onnx",
        "runtimeProvider": providers[0],
        "availableProviders": session.get_providers(),
        "inputName": input_meta.name,
        "inputShape": list(input_meta.shape),
        "inputType": input_meta.type,
        "outputName": output_meta.name,
        "outputShape": list(output_meta.shape),
        "outputType": output_meta.type,
    }


def model_report_metadata(*, model_path: str | Path | None, metadata: dict[str, Any]) -> dict[str, Any]:
    path = Path(model_path).expanduser().resolve() if model_path is not None else None
    result = {
        "sourceProvider": str(metadata.get("provider") or "model_fp16_onnx"),
        "runtimeProvider": metadata.get("runtimeProvider"),
        "inputName": metadata.get("inputName"),
        "inputShape": metadata.get("inputShape"),
        "inputType": metadata.get("inputType"),
        "outputName": metadata.get("outputName"),
        "outputShape": metadata.get("outputShape"),
        "outputType": metadata.get("outputType"),
        "availableProviders": metadata.get("availableProviders") or [],
    }
    if path is not None:
        result["modelPath"] = str(path)
        result["modelSha256"] = sha256_file(path) if path.is_file() else None
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bytes_to_file_like(data: bytes):
    from io import BytesIO

    return BytesIO(data)
