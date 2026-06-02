from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .schema import BBox, OCRBlock, clamp_box, ioa, iou


CONTROL_CLASSES = frozenset(
    {
        "TextButton",
        "EditText",
        "Spinner",
        "Switch",
        "CheckedTextView",
        "Multi_Tab",
        "Bottom_Navigation",
    }
)
MEDIA_CLASSES = frozenset({"Image", "Icon", "BackgroundImage", "Map"})
STRUCTURE_CLASSES = frozenset({"Card", "Toolbar", "Modal", "Drawer", "UpperTaskBar", "Bottom_Navigation"})
DANGEROUS_TEXT_CLASSES = frozenset({"Text", "TextButton", "EditText", "CheckedTextView"})

TAG_DECISIONS = frozenset({"control_semantic_tag", "media_semantic_tag", "structure_semantic_tag"})


@dataclass(frozen=True)
class ModelDetection:
    id: str
    class_id: int | None
    class_name: str
    confidence: float
    bbox: BBox

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "className": self.class_name,
            "confidence": round(self.confidence, 4),
            "bbox": self.bbox.to_dict(),
        }
        if self.class_id is not None:
            payload["classId"] = self.class_id
        return payload


def apply_model_evidence(
    layer_stack: dict[str, Any],
    model_evidence_path: Path | None,
    ocr_blocks: list[OCRBlock],
    output_path: Path,
) -> Path | None:
    if model_evidence_path is None:
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics = layer_stack.setdefault("diagnostics", {})
    try:
        payload = json.loads(model_evidence_path.read_text(encoding="utf-8"))
        detections = normalize_model_evidence(payload, layer_stack["canvas"])
    except Exception as exc:  # noqa: BLE001 - malformed external evidence must not break physical output.
        summary = ignored_summary(model_evidence_path, type(exc).__name__, str(exc))
        diagnostics.update(summary["diagnostics"])
        layer_stack["semanticEvidence"] = summary
        output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return output_path

    result = match_model_evidence(
        detections=detections,
        layers=layer_stack.get("layers", []),
        ocr_blocks=ocr_blocks,
        source_path=model_evidence_path,
    )
    attach_semantic_tags(layer_stack.get("layers", []), result["layerTags"])
    summary = result["summary"]
    diagnostics.update(summary["diagnostics"])
    layer_stack["semanticEvidence"] = summary
    output_path.write_text(json.dumps(result["artifact"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def normalize_model_evidence(payload: dict[str, Any], canvas: dict[str, Any]) -> list[ModelDetection]:
    if payload.get("version") != "model_evidence.v1":
        raise ValueError("version_not_model_evidence_v1")

    payload_canvas = payload.get("canvas") or {}
    width = int(canvas.get("width", 0))
    height = int(canvas.get("height", 0))
    if int(payload_canvas.get("width", 0)) != width or int(payload_canvas.get("height", 0)) != height:
        raise ValueError("canvas_mismatch")

    detections: list[ModelDetection] = []
    for index, item in enumerate(payload.get("detections", []), start=1):
        bbox_data = item.get("bbox", {})
        if isinstance(bbox_data, list):
            if len(bbox_data) < 4:
                continue
            raw_box = BBox(
                int(round(float(bbox_data[0]))),
                int(round(float(bbox_data[1]))),
                int(round(float(bbox_data[2]))),
                int(round(float(bbox_data[3]))),
            )
        else:
            raw_box = BBox(
                int(round(float(bbox_data.get("x", 0)))),
                int(round(float(bbox_data.get("y", 0)))),
                int(round(float(bbox_data.get("width", 0)))),
                int(round(float(bbox_data.get("height", 0)))),
            )
        box = clamp_box(raw_box, width, height)
        if box is None or box.area <= 0:
            continue

        raw_class_id = item.get("classId")
        class_id = int(raw_class_id) if raw_class_id is not None else None
        detections.append(
            ModelDetection(
                id=str(item.get("id") or f"det_{index:04d}"),
                class_id=class_id,
                class_name=str(item.get("className") or ""),
                confidence=float(item.get("confidence", 0.0)),
                bbox=box,
            )
        )
    return detections


def match_model_evidence(
    detections: list[ModelDetection],
    layers: list[dict[str, Any]],
    ocr_blocks: list[OCRBlock],
    source_path: Path,
) -> dict[str, Any]:
    layer_tags: dict[str, list[dict[str, Any]]] = {}
    matches: list[dict[str, Any]] = []
    decisions: Counter[str] = Counter()
    ocr_risk_count = 0

    for det in detections:
        best_by_type = best_layer_matches(det, layers)
        for layer_type in ("shape", "raster", "text"):
            best = best_by_type.get(layer_type)
            if best is None:
                continue
            score, iou_score, det_coverage, layer_coverage, layer = best
            if score < 0.2:
                continue
            decision = match_decision(det, layer, score, iou_score, det_coverage, layer_coverage)
            match = {
                "detectionId": det.id,
                "className": det.class_name,
                "layerId": layer.get("id", ""),
                "layerKind": layer_type,
                "layerReason": layer.get("reason", ""),
                "iou": round(iou_score, 4),
                "detectionCoverageByLayer": round(det_coverage, 4),
                "layerCoverageByDetection": round(layer_coverage, 4),
                "score": round(score, 4),
                "decision": decision,
            }
            matches.append(match)
            decisions[decision] += 1
            if decision == "ocr_overlap_risk":
                ocr_risk_count += 1
            tag = semantic_tag_for_match(det, match)
            if tag is not None:
                layer_tags.setdefault(str(layer.get("id", "")), []).append(tag)

        for risk in ocr_search_window_risks(det, ocr_blocks):
            matches.append(risk)
            decisions[str(risk.get("decision", ""))] += 1

    semantic_tag_count = sum(len(tags) for tags in layer_tags.values())
    class_counts = Counter(det.class_name for det in detections)
    summary = {
        "version": "semantic_evidence_summary.v1",
        "source": str(source_path),
        "diagnostics": {
            "modelEvidencePresent": True,
            "modelDetectionCount": len(detections),
            "modelControlDetectionCount": sum(1 for det in detections if det.class_name in CONTROL_CLASSES),
            "modelMediaDetectionCount": sum(1 for det in detections if det.class_name in MEDIA_CLASSES),
            "modelStructureDetectionCount": sum(1 for det in detections if det.class_name in STRUCTURE_CLASSES),
            "semanticTagCount": semantic_tag_count,
            "modelOcrOverlapRiskCount": ocr_risk_count,
            "modelEvidenceIgnoredReason": "",
        },
        "classCounts": dict(sorted(class_counts.items())),
        "decisionCounts": dict(sorted(decisions.items())),
    }
    artifact = {
        "version": "semantic_evidence.v1",
        "source": str(source_path),
        "summary": summary,
        "detections": [det.to_dict() for det in detections],
        "matches": matches,
        "layerTags": layer_tags,
    }
    return {"summary": summary, "artifact": artifact, "layerTags": layer_tags}


def best_layer_matches(
    det: ModelDetection,
    layers: list[dict[str, Any]],
) -> dict[str, tuple[float, float, float, float, dict[str, Any]]]:
    best_by_type: dict[str, tuple[float, float, float, float, dict[str, Any]]] = {}
    for layer in layers:
        layer_type = str(layer.get("type", ""))
        if layer_type not in {"shape", "raster", "text"}:
            continue
        box = layer_bbox(layer)
        iou_score = iou(det.bbox, box)
        det_coverage = ioa(det.bbox, box)
        layer_coverage = ioa(box, det.bbox)
        score = max(iou_score, det_coverage * 0.85, layer_coverage * 0.75)
        current = best_by_type.get(layer_type)
        if current is None or score > current[0]:
            best_by_type[layer_type] = (score, iou_score, det_coverage, layer_coverage, layer)
    return best_by_type


def layer_bbox(layer: dict[str, Any]) -> BBox:
    bbox = layer.get("bbox") or {}
    return BBox(
        int(bbox.get("x", 0)),
        int(bbox.get("y", 0)),
        int(bbox.get("width", 0)),
        int(bbox.get("height", 0)),
    )


def match_decision(
    det: ModelDetection,
    layer: dict[str, Any],
    score: float,
    iou_score: float,
    det_coverage: float,
    layer_coverage: float,
) -> str:
    class_name = det.class_name
    layer_type = str(layer.get("type", ""))

    if class_name in CONTROL_CLASSES:
        if layer_type == "shape" and score >= 0.35:
            return "control_semantic_tag"
        if layer_type == "text" and layer_coverage >= 0.65:
            return "control_search_window_candidate"
    if class_name in MEDIA_CLASSES and layer_type == "raster" and score >= 0.30:
        return "media_semantic_tag"
    if class_name in STRUCTURE_CLASSES and score >= 0.30:
        return "structure_semantic_tag"
    if class_name in DANGEROUS_TEXT_CLASSES and layer_type == "raster" and det_coverage >= 0.35:
        return "ocr_overlap_risk"
    if iou_score >= 0.50:
        return "bbox_aligned"
    return "weak_match"


def semantic_tag_for_match(det: ModelDetection, match: dict[str, Any]) -> dict[str, Any] | None:
    decision = str(match.get("decision", ""))
    if decision not in TAG_DECISIONS:
        return None
    authority = "audit" if decision == "structure_semantic_tag" else "hint"
    return {
        "tag": det.class_name,
        "source": "model_evidence",
        "detectionId": det.id,
        "confidence": round(det.confidence, 4),
        "authority": authority,
        "decision": decision,
        "match": {
            "iou": match["iou"],
            "detectionCoverageByLayer": match["detectionCoverageByLayer"],
            "layerCoverageByDetection": match["layerCoverageByDetection"],
        },
    }


def ocr_search_window_risks(det: ModelDetection, ocr_blocks: list[OCRBlock]) -> list[dict[str, Any]]:
    if det.class_name not in CONTROL_CLASSES:
        return []
    risks: list[dict[str, Any]] = []
    for block in ocr_blocks:
        coverage = ioa(block.bbox, det.bbox)
        if coverage < 0.65:
            continue
        risks.append(
            {
                "detectionId": det.id,
                "className": det.class_name,
                "ocrBlockId": block.id,
                "layerKind": "ocr",
                "ocrCoverageByDetection": round(coverage, 4),
                "decision": "control_search_window_candidate",
            }
        )
    return risks


def attach_semantic_tags(layers: list[dict[str, Any]], layer_tags: dict[str, list[dict[str, Any]]]) -> None:
    for layer in layers:
        tags = layer_tags.get(str(layer.get("id", "")))
        if not tags:
            continue
        layer["semanticTags"] = stable_tags([*layer.get("semanticTags", []), *tags])


def stable_tags(tags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for tag in tags:
        key = (
            str(tag.get("tag", "")),
            str(tag.get("detectionId", "")),
            str(tag.get("decision", "")),
        )
        current = deduped.get(key)
        if current is None or float(tag.get("confidence", 0.0)) > float(current.get("confidence", 0.0)):
            deduped[key] = tag
    return sorted(deduped.values(), key=lambda item: (str(item.get("tag", "")), str(item.get("detectionId", ""))))


def ignored_summary(path: Path, error_type: str, message: str) -> dict[str, Any]:
    reason = f"{error_type}: {message}"
    return {
        "version": "semantic_evidence_summary.v1",
        "source": str(path),
        "ignored": True,
        "diagnostics": {
            "modelEvidencePresent": False,
            "modelDetectionCount": 0,
            "modelControlDetectionCount": 0,
            "modelMediaDetectionCount": 0,
            "modelStructureDetectionCount": 0,
            "semanticTagCount": 0,
            "modelOcrOverlapRiskCount": 0,
            "modelEvidenceIgnoredReason": reason,
        },
        "classCounts": {},
        "decisionCounts": {},
    }
