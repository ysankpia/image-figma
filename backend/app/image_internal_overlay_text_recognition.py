from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from .png_tools import (
    PngPixels,
    PngRegion,
    UnsupportedPngCropError,
    crop_pixels_to_png,
    decode_png_pixels,
    encode_rgb_png,
    read_png_metadata,
    upscale_pixels_nearest,
)
from .visual_primitive_graph import bbox_area, bbox_clamp, bbox_iou, bbox_x2, bbox_y2, draw_rect


M294Decision = Literal[
    "promotion_ready",
    "covered_by_existing_ocr",
    "pattern_rejected",
    "ocr_unrecognized",
    "ocr_failed",
    "not_attempted",
]
M294ReprobeFn = Callable[[bytes, list[int]], dict[str, Any]]
COUNTER_TEXT_RE = re.compile(r"^[0-9]{1,2}/[0-9]{1,2}$")


@dataclass(frozen=True)
class M294Options:
    enabled: bool = True
    reprobe_enabled: bool = False
    max_items: int = 12
    crop_padding: int = 4
    upscale_factor: int = 3
    min_m292_iou: float = 0.70

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class M294DebugArtifacts:
    overlay: str | None = None

    def to_dict(self) -> dict[str, str]:
        return {key: value for key, value in {"overlay": self.overlay}.items() if value is not None}


@dataclass(frozen=True)
class M294RecognitionItem:
    id: str
    source_m293_overlay_id: str
    source_m292_candidate_id: str | None
    source_image_node_id: str
    source_m29_node_id: str | None
    source_image_bbox: list[int]
    overlay_bbox: list[int]
    local_overlay_bbox: list[int]
    recognized_text: str | None
    raw_recognized_text: str | None
    recognition_source: str | None
    recognition_confidence: float | None
    recognized_text_bbox: list[int] | None
    local_recognized_text_bbox: list[int] | None
    decision: M294Decision
    materialization_eligible: bool
    base_image_handling: str
    asset_path: str | None
    upscaled_asset_path: str | None
    reasons: list[str]
    metrics: dict[str, Any]
    recognition_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "id": self.id,
            "sourceM293OverlayId": self.source_m293_overlay_id,
            "sourceM292CandidateId": self.source_m292_candidate_id,
            "sourceImageNodeId": self.source_image_node_id,
            "sourceM29NodeId": self.source_m29_node_id,
            "sourceImageBBox": self.source_image_bbox,
            "overlayBBox": self.overlay_bbox,
            "localOverlayBBox": self.local_overlay_bbox,
            "recognizedText": self.recognized_text,
            "rawRecognizedText": self.raw_recognized_text,
            "recognitionSource": self.recognition_source,
            "recognitionConfidence": self.recognition_confidence,
            "recognizedTextBBox": self.recognized_text_bbox,
            "localRecognizedTextBBox": self.local_recognized_text_bbox,
            "decision": self.decision,
            "materializationEligible": self.materialization_eligible,
            "baseImageHandling": self.base_image_handling,
            "assetPath": self.asset_path,
            "upscaledAssetPath": self.upscaled_asset_path,
            "reasons": self.reasons,
            "metrics": self.metrics,
        }
        if self.recognition_error:
            data["recognitionError"] = self.recognition_error
        return data


@dataclass(frozen=True)
class M294Document:
    schema_name: str
    schema_version: str
    source_image: str
    source_ocr_json: str | None
    source_m292_candidates_json: str | None
    source_m293_overlays_json: str | None
    options: M294Options
    summary: dict[str, Any]
    items: list[M294RecognitionItem]
    warnings: list[str]
    debug: M294DebugArtifacts = field(default_factory=M294DebugArtifacts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaName": self.schema_name,
            "schemaVersion": self.schema_version,
            "sourceImage": self.source_image,
            "sourceOcrJson": self.source_ocr_json,
            "sourceM292CandidatesJson": self.source_m292_candidates_json,
            "sourceM293OverlaysJson": self.source_m293_overlays_json,
            "options": self.options.to_dict(),
            "summary": self.summary,
            "items": [item.to_dict() for item in self.items],
            "warnings": self.warnings,
            "debug": self.debug.to_dict(),
        }


def extract_image_internal_overlay_text_recognition(
    *,
    png_data: bytes,
    source_image: str,
    output_dir: Path,
    ocr_json_path: str | None,
    m292_document: dict[str, Any],
    m292_candidates_json_path: str | None,
    m293_document: dict[str, Any],
    m293_overlays_json_path: str | None,
    options: M294Options | None = None,
    emit_debug_artifacts: bool = True,
    reprobe_fn: M294ReprobeFn | None = None,
) -> M294Document:
    options = options or M294Options()
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)

    overlays = [overlay for overlay in m293_document.get("overlays", []) if isinstance(overlay, dict)]
    candidates = [candidate for candidate in m292_document.get("candidates", []) if isinstance(candidate, dict)]
    warnings: list[str] = []
    if len(overlays) > options.max_items:
        warnings.append("M29.4 max item limit reached.")

    items: list[M294RecognitionItem] = []
    for overlay in overlays[: max(0, options.max_items)]:
        item = build_recognition_item(
            item_index=len(items) + 1,
            overlay=overlay,
            candidates=candidates,
            pixels=pixels,
            output_dir=output_dir,
            options=options,
            emit_debug_artifacts=emit_debug_artifacts,
            reprobe_fn=reprobe_fn,
        )
        items.append(item)

    debug = M294DebugArtifacts()
    if emit_debug_artifacts:
        overlay_dir = output_dir / "overlays"
        overlay_dir.mkdir(parents=True, exist_ok=True)
        overlay_path = overlay_dir / "image_internal_overlay_text_recognition.png"
        overlay_path.write_bytes(overlay_text_recognition(pixels, items))
        debug = M294DebugArtifacts(overlay=str(overlay_path.relative_to(output_dir)))

    document = M294Document(
        schema_name="M294ImageInternalOverlayTextRecognitionDocument",
        schema_version="0.1",
        source_image=source_image,
        source_ocr_json=ocr_json_path,
        source_m292_candidates_json=m292_candidates_json_path,
        source_m293_overlays_json=m293_overlays_json_path,
        options=options,
        summary=build_summary(overlays, items),
        items=items,
        warnings=warnings,
        debug=debug,
    )
    validate_document(document, output_dir, pixels.width, pixels.height)
    write_outputs(document, output_dir)
    return document


def build_recognition_item(
    *,
    item_index: int,
    overlay: dict[str, Any],
    candidates: list[dict[str, Any]],
    pixels: PngPixels,
    output_dir: Path,
    options: M294Options,
    emit_debug_artifacts: bool,
    reprobe_fn: M294ReprobeFn | None,
) -> M294RecognitionItem:
    overlay_id = str(overlay.get("id") or f"m293_overlay_{item_index:03d}")
    overlay_bbox = parse_bbox(overlay.get("bbox")) or [0, 0, 1, 1]
    source_image_bbox = parse_bbox(overlay.get("sourceImageBBox")) or [0, 0, pixels.width, pixels.height]
    local_overlay_bbox = to_local_bbox(overlay_bbox, source_image_bbox)
    match, m292_iou = best_m292_match(overlay, overlay_bbox, candidates)
    asset_path = None
    upscaled_asset_path = None
    if emit_debug_artifacts and bbox_clamp(overlay_bbox, pixels.width, pixels.height) == overlay_bbox:
        asset_path = write_crop_asset(pixels, output_dir, overlay_bbox, item_index, options.crop_padding, 1, "crops")
        if options.reprobe_enabled:
            upscaled_asset_path = write_crop_asset(
                pixels,
                output_dir,
                overlay_bbox,
                item_index,
                options.crop_padding,
                options.upscale_factor,
                "upscaled",
            )

    base_reasons = ["parent_image_ownership_bound"]
    if overlay.get("overlayKind") == "text_like_overlay_candidate":
        base_reasons.append("text_like_overlay_candidate")

    metrics = {
        "upscaleFactor": options.upscale_factor,
        "overlayWidth": overlay_bbox[2],
        "overlayHeight": overlay_bbox[3],
        "m292IoU": round(m292_iou, 4),
        "ocrBoxCount": 0,
        "bestOcrConfidence": None,
        "counterPatternMatched": False,
        "localOverlayX": local_overlay_bbox[0],
        "localOverlayY": local_overlay_bbox[1],
    }

    decision, gate_reasons = gate_overlay(overlay, overlay_bbox, source_image_bbox, match, m292_iou, options)
    reasons = [*base_reasons, *gate_reasons]
    if decision is not None:
        return make_item(
            item_index=item_index,
            overlay=overlay,
            match=match,
            source_image_bbox=source_image_bbox,
            overlay_bbox=overlay_bbox,
            local_overlay_bbox=local_overlay_bbox,
            decision=decision,
            asset_path=asset_path,
            upscaled_asset_path=upscaled_asset_path,
            reasons=reasons,
            metrics=metrics,
        )

    if not options.reprobe_enabled:
        return make_item(
            item_index=item_index,
            overlay=overlay,
            match=match,
            source_image_bbox=source_image_bbox,
            overlay_bbox=overlay_bbox,
            local_overlay_bbox=local_overlay_bbox,
            decision="not_attempted",
            asset_path=asset_path,
            upscaled_asset_path=upscaled_asset_path,
            reasons=[*reasons, "recognition_reprobe_disabled", "audit_only_no_materialization"],
            metrics=metrics,
        )

    if reprobe_fn is None:
        return make_item(
            item_index=item_index,
            overlay=overlay,
            match=match,
            source_image_bbox=source_image_bbox,
            overlay_bbox=overlay_bbox,
            local_overlay_bbox=local_overlay_bbox,
            decision="ocr_failed",
            asset_path=asset_path,
            upscaled_asset_path=upscaled_asset_path,
            reasons=[*reasons, "recognition_reprobe_unavailable", "audit_only_no_materialization"],
            metrics=metrics,
            recognition_error="Local OCR reprobe is not configured.",
        )

    try:
        crop_png, crop_bbox = overlay_crop_png_bytes(pixels, overlay_bbox, options.crop_padding, options.upscale_factor)
        result = reprobe_fn(crop_png, overlay_bbox)
    except Exception as error:  # noqa: BLE001 - M29.4 diagnostics must not block the pipeline.
        return make_item(
            item_index=item_index,
            overlay=overlay,
            match=match,
            source_image_bbox=source_image_bbox,
            overlay_bbox=overlay_bbox,
            local_overlay_bbox=local_overlay_bbox,
            decision="ocr_failed",
            asset_path=asset_path,
            upscaled_asset_path=upscaled_asset_path,
            reasons=[*reasons, "ocr_reprobe_error", "audit_only_no_materialization"],
            metrics=metrics,
            recognition_error=str(error),
        )

    raw_text = str(result.get("text") or "").strip()
    confidence = parse_float(result.get("confidence"))
    metrics["ocrBoxCount"] = int(result.get("blockCount") or (1 if raw_text else 0))
    metrics["bestOcrConfidence"] = confidence
    recognized_bbox, bbox_reasons = recognized_bbox_from_result(
        result,
        crop_bbox,
        overlay_bbox,
        source_image_bbox,
        options.upscale_factor,
    )
    reasons.extend(bbox_reasons)
    if not raw_text:
        return make_item(
            item_index=item_index,
            overlay=overlay,
            match=match,
            source_image_bbox=source_image_bbox,
            overlay_bbox=overlay_bbox,
            local_overlay_bbox=local_overlay_bbox,
            decision="ocr_unrecognized",
            asset_path=asset_path,
            upscaled_asset_path=upscaled_asset_path,
            reasons=[*reasons, "ocr_empty_text", "audit_only_no_materialization"],
            metrics=metrics,
            raw_text=None,
            confidence=confidence,
            recognized_bbox=recognized_bbox,
        )
    if COUNTER_TEXT_RE.match(raw_text):
        metrics["counterPatternMatched"] = True
        return make_item(
            item_index=item_index,
            overlay=overlay,
            match=match,
            source_image_bbox=source_image_bbox,
            overlay_bbox=overlay_bbox,
            local_overlay_bbox=local_overlay_bbox,
            decision="promotion_ready",
            asset_path=asset_path,
            upscaled_asset_path=upscaled_asset_path,
            reasons=[*reasons, "local_crop_ocr_counter_pattern", "audit_only_no_materialization"],
            metrics=metrics,
            raw_text=raw_text,
            recognized_text=raw_text,
            confidence=confidence,
            recognized_bbox=recognized_bbox,
        )
    return make_item(
        item_index=item_index,
        overlay=overlay,
        match=match,
        source_image_bbox=source_image_bbox,
        overlay_bbox=overlay_bbox,
        local_overlay_bbox=local_overlay_bbox,
        decision="pattern_rejected",
        asset_path=asset_path,
        upscaled_asset_path=upscaled_asset_path,
        reasons=[*reasons, "recognition_pattern_rejected", "audit_only_no_materialization"],
        metrics=metrics,
        raw_text=raw_text,
        confidence=confidence,
        recognized_bbox=recognized_bbox,
    )


def gate_overlay(
    overlay: dict[str, Any],
    overlay_bbox: list[int],
    source_image_bbox: list[int],
    match: dict[str, Any] | None,
    m292_iou: float,
    options: M294Options,
) -> tuple[M294Decision | None, list[str]]:
    if overlay.get("decision") == "covered_by_existing_ocr" or bool(overlay.get("overlapsExistingOcr")):
        return "covered_by_existing_ocr", ["covered_by_existing_ocr", "audit_only_no_materialization"]
    reasons: list[str] = []
    if overlay.get("decision") != "proposal_only":
        reasons.append("m293_decision_not_proposal_only")
    if overlay.get("overlayKind") != "text_like_overlay_candidate":
        reasons.append("not_text_like_overlay_candidate")
    if bool(overlay.get("materializationEligible")):
        reasons.append("source_overlay_materialization_eligible_unexpected")
    if not bbox_contains(source_image_bbox, overlay_bbox):
        reasons.append("overlay_bbox_outside_source_image")
    if match is None or m292_iou < options.min_m292_iou:
        reasons.append("missing_m292_candidate_match")
    if reasons:
        return "not_attempted", [*reasons, "audit_only_no_materialization"]
    return None, ["matched_m292_candidate"]


def make_item(
    *,
    item_index: int,
    overlay: dict[str, Any],
    match: dict[str, Any] | None,
    source_image_bbox: list[int],
    overlay_bbox: list[int],
    local_overlay_bbox: list[int],
    decision: M294Decision,
    asset_path: str | None,
    upscaled_asset_path: str | None,
    reasons: list[str],
    metrics: dict[str, Any],
    raw_text: str | None = None,
    recognized_text: str | None = None,
    confidence: float | None = None,
    recognized_bbox: list[int] | None = None,
    recognition_error: str | None = None,
) -> M294RecognitionItem:
    return M294RecognitionItem(
        id=f"m294_overlay_text_{item_index:03d}",
        source_m293_overlay_id=str(overlay.get("id") or ""),
        source_m292_candidate_id=str(match.get("candidateId") or "") if isinstance(match, dict) else None,
        source_image_node_id=str(overlay.get("sourceImageNodeId") or ""),
        source_m29_node_id=str(overlay.get("sourceM29NodeId")) if overlay.get("sourceM29NodeId") else None,
        source_image_bbox=source_image_bbox,
        overlay_bbox=overlay_bbox,
        local_overlay_bbox=local_overlay_bbox,
        recognized_text=recognized_text,
        raw_recognized_text=raw_text,
        recognition_source="local_overlay_crop_ocr" if raw_text or decision in {"promotion_ready", "pattern_rejected", "ocr_unrecognized"} else None,
        recognition_confidence=confidence,
        recognized_text_bbox=recognized_bbox,
        local_recognized_text_bbox=to_local_bbox(recognized_bbox, source_image_bbox) if recognized_bbox else None,
        decision=decision,
        materialization_eligible=False,
        base_image_handling="clean_parent_asset_later",
        asset_path=asset_path,
        upscaled_asset_path=upscaled_asset_path,
        reasons=dedupe(reasons),
        metrics=metrics,
        recognition_error=recognition_error,
    )


def best_m292_match(
    overlay: dict[str, Any],
    overlay_bbox: list[int],
    candidates: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, float]:
    source_image_id = str(overlay.get("sourceImageNodeId") or "")
    best: dict[str, Any] | None = None
    best_iou = 0.0
    for candidate in candidates:
        if str(candidate.get("sourceImageEvidenceId") or "") != source_image_id:
            continue
        bbox = parse_bbox(candidate.get("bbox"))
        if bbox is None:
            continue
        iou = bbox_iou(overlay_bbox, bbox)
        if iou > best_iou:
            best = candidate
            best_iou = iou
    return best, best_iou


def write_crop_asset(
    pixels: PngPixels,
    output_dir: Path,
    bbox: list[int],
    index: int,
    padding: int,
    upscale_factor: int,
    folder: str,
) -> str:
    png, _crop_bbox = overlay_crop_png_bytes(pixels, bbox, padding, upscale_factor)
    target_dir = output_dir / "assets" / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"m294_overlay_text_{index:03d}.png"
    path.write_bytes(png)
    return str(path.relative_to(output_dir))


def overlay_crop_png_bytes(pixels: PngPixels, bbox: list[int], padding: int, upscale_factor: int) -> tuple[bytes, list[int]]:
    padded = bbox_clamp([bbox[0] - padding, bbox[1] - padding, bbox[2] + padding * 2, bbox[3] + padding * 2], pixels.width, pixels.height)
    if padded is None:
        raise UnsupportedPngCropError("M29.4 overlay bbox is outside image bounds.")
    crop_png = crop_pixels_to_png(pixels, PngRegion("overlay_text", padded[0], padded[1], padded[2], padded[3]))
    if upscale_factor > 1:
        crop_pixels = decode_png_pixels(crop_png)
        scaled = upscale_pixels_nearest(crop_pixels, upscale_factor)
        crop_png = encode_rgb_png(scaled.width, scaled.height, scaled.rows)
    return crop_png, padded


def recognized_bbox_from_result(
    result: dict[str, Any],
    crop_bbox: list[int],
    overlay_bbox: list[int],
    source_image_bbox: list[int],
    upscale_factor: int,
) -> tuple[list[int], list[str]]:
    local_bbox = parse_bbox(result.get("bbox"))
    if local_bbox is None:
        return overlay_bbox, ["recognized_bbox_fallback_to_overlay_bbox"]
    mapped = [
        crop_bbox[0] + round(local_bbox[0] / upscale_factor),
        crop_bbox[1] + round(local_bbox[1] / upscale_factor),
        max(1, round(local_bbox[2] / upscale_factor)),
        max(1, round(local_bbox[3] / upscale_factor)),
    ]
    if not bbox_contains(source_image_bbox, mapped):
        return overlay_bbox, ["recognized_bbox_fallback_to_overlay_bbox"]
    return mapped, ["recognized_bbox_from_local_ocr"]


def overlay_text_recognition(pixels: PngPixels, items: list[M294RecognitionItem]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    colors = {
        "promotion_ready": (0, 200, 90),
        "covered_by_existing_ocr": (120, 120, 120),
        "pattern_rejected": (238, 190, 40),
        "ocr_unrecognized": (238, 190, 40),
        "ocr_failed": (235, 64, 52),
        "not_attempted": (190, 190, 190),
    }
    for item in items:
        draw_rect(rows, pixels.width, pixels.height, item.overlay_bbox, colors[item.decision], 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def write_outputs(document: M294Document, output_dir: Path) -> None:
    payload = document.to_dict()
    (output_dir / "image_internal_overlay_text_recognition.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "image_internal_overlay_text_recognition.md").write_text(build_markdown(document), encoding="utf-8")


def build_markdown(document: M294Document) -> str:
    lines = [
        "# M29.4 Image Internal Overlay Text Recognition Audit",
        "",
        f"- Source overlays: {document.summary['sourceOverlayCount']}",
        f"- Recognition attempts: {document.summary['recognitionAttemptCount']}",
        f"- Promotion ready: {document.summary['promotionReadyCount']}",
        f"- DSL changed: `{document.summary['dslChanged']}`",
        "",
        "## Items",
        "",
    ]
    for item in document.items[:80]:
        lines.append(
            f"- `{item.id}` `{item.decision}` overlay=`{item.source_m293_overlay_id}` "
            f"parent=`{item.source_image_node_id}` bbox={item.overlay_bbox} recognized=`{item.recognized_text}` reasons={item.reasons}"
        )
    return "\n".join(lines).rstrip() + "\n"


def build_summary(overlays: list[dict[str, Any]], items: list[M294RecognitionItem]) -> dict[str, Any]:
    return {
        "sourceOverlayCount": len(overlays),
        "recognitionAttemptCount": sum(1 for item in items if "local_overlay_crop_ocr" == item.recognition_source),
        "promotionReadyCount": sum(1 for item in items if item.decision == "promotion_ready"),
        "patternRejectedCount": sum(1 for item in items if item.decision == "pattern_rejected"),
        "ocrCoveredOverlayCount": sum(1 for item in items if item.decision == "covered_by_existing_ocr"),
        "recognitionFailedCount": sum(1 for item in items if item.decision == "ocr_failed"),
        "materializedTextCount": 0,
        "createdNewBBoxCount": 0,
        "dslChanged": False,
    }


def validate_document(document: M294Document, output_dir: Path, width: int, height: int) -> None:
    if document.schema_name != "M294ImageInternalOverlayTextRecognitionDocument" or document.schema_version != "0.1":
        raise ValueError("invalid M29.4 document schema")
    seen: set[str] = set()
    for item in document.items:
        if item.id in seen:
            raise ValueError(f"duplicate M29.4 item id: {item.id}")
        seen.add(item.id)
        if bbox_clamp(item.overlay_bbox, width, height) != item.overlay_bbox:
            raise ValueError(f"M29.4 overlay bbox out of bounds: {item.id}")
        if item.materialization_eligible:
            raise ValueError(f"M29.4 item must remain audit-only: {item.id}")
        if item.asset_path:
            assert_readable_relative_png(output_dir, item.asset_path)
        if item.upscaled_asset_path:
            assert_readable_relative_png(output_dir, item.upscaled_asset_path)
    for path in document.debug.to_dict().values():
        assert_readable_relative_png(output_dir, path)


def assert_readable_relative_png(output_dir: Path, path: str) -> None:
    resolved = output_dir / path
    if not resolved.exists() or read_png_metadata(resolved.read_bytes()) is None:
        raise ValueError(f"M29.4 PNG output missing or unreadable: {path}")


def parse_bbox(value: object) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        bbox = [round(float(item)) for item in value]
    except (TypeError, ValueError):
        return None
    if bbox[2] <= 0 or bbox[3] <= 0:
        return None
    return bbox


def parse_float(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return round(parsed, 4)


def bbox_contains(outer: list[int], inner: list[int]) -> bool:
    return inner[0] >= outer[0] and inner[1] >= outer[1] and bbox_x2(inner) <= bbox_x2(outer) and bbox_y2(inner) <= bbox_y2(outer)


def to_local_bbox(bbox: list[int] | None, source_image_bbox: list[int]) -> list[int] | None:
    if bbox is None:
        return None
    return [bbox[0] - source_image_bbox[0], bbox[1] - source_image_bbox[1], bbox[2], bbox[3]]


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output
