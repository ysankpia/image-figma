from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .config import Settings
from .ocr import OCRBlock, OCRDocument
from .png_tools import (
    BackgroundSample,
    PngMetadata,
    UnsupportedPngCropError,
    decode_png_pixels,
    sample_region_background,
)


ReplacementStatus = Literal["completed", "failed", "skipped"]
ReplacementDecisionValue = Literal["accepted", "rejected", "skipped"]


@dataclass
class TextReplacementWarning:
    code: str
    message: str
    ocrBlockId: str | None = None


@dataclass
class TextReplacementDecision:
    ocrBlockId: str
    decision: ReplacementDecisionValue
    reason: str
    bbox: list[int]
    expandedBBox: list[int] | None = None
    background: dict[str, Any] | None = None
    patches: list[str] = field(default_factory=list)


@dataclass
class TextReplacementDocument:
    version: str
    taskId: str
    mode: str
    status: ReplacementStatus
    imageSize: dict[str, int]
    decisions: list[TextReplacementDecision]
    warnings: list[TextReplacementWarning]
    meta: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_replacement_mode(mode: str) -> str:
    normalized = mode.strip().lower()
    if normalized in {"off", "debug", "apply"}:
        return normalized
    return "debug"


def build_text_replacement_document(
    *,
    task_id: str,
    image: PngMetadata,
    png_data: bytes,
    ocr_document: OCRDocument,
    settings: Settings,
) -> TextReplacementDocument:
    mode = normalize_replacement_mode(settings.text_replacement_mode)
    if ocr_document.status != "completed":
        return build_skipped_document(
            task_id=task_id,
            image=image,
            mode=mode,
            code="ocr_not_completed",
            message="Text replacement skipped because OCR did not complete.",
        )

    try:
        pixels = decode_png_pixels(png_data)
    except UnsupportedPngCropError as error:
        return build_skipped_document(
            task_id=task_id,
            image=image,
            mode=mode,
            code="png_sampling_unsupported",
            message=str(error),
        )

    decisions: list[TextReplacementDecision] = []
    accepted_count = 0
    for block in ocr_document.blocks:
        decision = evaluate_block(block, pixels, accepted_count, settings)
        if decision.decision == "accepted":
            accepted_count += 1
        decisions.append(decision)

    accepted = sum(1 for decision in decisions if decision.decision == "accepted")
    rejected = sum(1 for decision in decisions if decision.decision == "rejected")
    return TextReplacementDocument(
        version="0.1",
        taskId=task_id,
        mode=mode,
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        decisions=decisions,
        warnings=[],
        meta={
            "notes": "low_risk_text_replacement_harness",
            "acceptedCount": accepted,
            "rejectedCount": rejected,
        },
    )


def build_skipped_document(
    *,
    task_id: str,
    image: PngMetadata,
    mode: str,
    code: str,
    message: str,
) -> TextReplacementDocument:
    return TextReplacementDocument(
        version="0.1",
        taskId=task_id,
        mode=mode,
        status="skipped",
        imageSize={"width": image.width, "height": image.height},
        decisions=[],
        warnings=[TextReplacementWarning(code=code, message=message)],
        meta={
            "notes": "low_risk_text_replacement_harness",
            "acceptedCount": 0,
            "rejectedCount": 0,
        },
        error={"code": code, "message": message},
    )


def build_failed_text_replacement_document(
    *,
    task_id: str,
    image: PngMetadata,
    mode: str,
    code: str,
    message: str,
) -> TextReplacementDocument:
    return TextReplacementDocument(
        version="0.1",
        taskId=task_id,
        mode=normalize_replacement_mode(mode),
        status="failed",
        imageSize={"width": image.width, "height": image.height},
        decisions=[],
        warnings=[TextReplacementWarning(code=code, message=message)],
        meta={
            "notes": "low_risk_text_replacement_harness",
            "acceptedCount": 0,
            "rejectedCount": 0,
        },
        error={"code": code, "message": message},
    )


def evaluate_block(
    block: OCRBlock,
    pixels,
    accepted_count: int,
    settings: Settings,
) -> TextReplacementDecision:
    if accepted_count >= settings.text_replacement_max_blocks:
        return reject(block, "max_blocks_reached")
    if not block.text.strip():
        return reject(block, "empty_text")
    if block.confidence < settings.text_replacement_min_confidence:
        return reject(block, "confidence_too_low")
    width = block.bbox[2]
    height = block.bbox[3]
    if width < settings.text_replacement_min_width or height < settings.text_replacement_min_height:
        return reject(block, "bbox_too_small")
    if height > settings.text_replacement_max_height:
        return reject(block, "bbox_too_tall")
    if block.bbox[1] < 44:
        return reject(block, "status_bar_or_too_small")

    expanded_bbox = expand_bbox(block.bbox, pixels.width, pixels.height, 4)
    try:
        background = sample_region_background(
            pixels,
            expanded_bbox,
            settings.text_replacement_solid_bg_tolerance,
        )
    except UnsupportedPngCropError:
        return reject(block, "png_sampling_unsupported", expanded_bbox)

    if background.max_channel_delta > settings.text_replacement_solid_bg_tolerance:
        return reject(block, "complex_background", expanded_bbox, background)
    if background.brightness < 180:
        return reject(block, "dark_background", expanded_bbox, background)

    return TextReplacementDecision(
        ocrBlockId=block.id,
        decision="accepted",
        reason="solid_light_background",
        bbox=list(block.bbox),
        expandedBBox=expanded_bbox,
        background=background_to_dict(background),
        patches=[f"cover_{block.id}", f"visible_text_{block.id}"],
    )


def reject(
    block: OCRBlock,
    reason: str,
    expanded_bbox: list[int] | None = None,
    background: BackgroundSample | None = None,
) -> TextReplacementDecision:
    return TextReplacementDecision(
        ocrBlockId=block.id,
        decision="rejected",
        reason=reason,
        bbox=list(block.bbox),
        expandedBBox=expanded_bbox,
        background=background_to_dict(background) if background else None,
        patches=[],
    )


def expand_bbox(bbox: list[int], image_width: int, image_height: int, padding: int) -> list[int]:
    x, y, width, height = bbox
    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(image_width, x + width + padding)
    y2 = min(image_height, y + height + padding)
    return [x1, y1, max(1, x2 - x1), max(1, y2 - y1)]


def background_to_dict(background: BackgroundSample) -> dict[str, Any]:
    return {
        "color": background.color,
        "meanRgb": background.mean_rgb,
        "maxChannelDelta": background.max_channel_delta,
        "brightness": background.brightness,
        "confidence": background.confidence,
    }


def apply_text_replacements(
    dsl: dict[str, Any],
    document: TextReplacementDocument,
    ocr_document: OCRDocument,
) -> dict[str, Any]:
    if document.mode != "apply" or document.status != "completed":
        return deepcopy(dsl)

    blocks = {block.id: block for block in ocr_document.blocks}
    next_dsl = deepcopy(dsl)
    root = next_dsl.setdefault("root", {})
    children = root.setdefault("children", [])
    added_count = 0
    for decision in document.decisions:
        if decision.decision != "accepted":
            continue
        block = blocks.get(decision.ocrBlockId)
        if block is None or decision.expandedBBox is None or decision.background is None:
            continue
        children.append(build_cover_element(decision))
        children.append(build_visible_text_element(block))
        added_count += 1

    if added_count:
        meta = next_dsl.setdefault("meta", {})
        notes = str(meta.get("notes") or "")
        if "m11_text_replacement_apply" not in notes:
            meta["notes"] = f"{notes}+m11_text_replacement_apply" if notes else "m11_text_replacement_apply"
        quality_flags = list(meta.get("qualityFlags") or [])
        if "m11_visible_text_replacements" not in quality_flags:
            quality_flags.append("m11_visible_text_replacements")
        meta["qualityFlags"] = quality_flags
        meta["textReplacementCount"] = added_count
        meta["elementCount"] = len(children)
    return next_dsl


def build_cover_element(decision: TextReplacementDecision) -> dict[str, Any]:
    assert decision.expandedBBox is not None
    assert decision.background is not None
    return {
        "id": f"cover_{decision.ocrBlockId}",
        "type": "shape",
        "role": "text_replacement_cover",
        "name": f"Text Replacement Cover / {decision.ocrBlockId}",
        "layout": {
            "x": decision.expandedBBox[0],
            "y": decision.expandedBBox[1],
            "width": decision.expandedBBox[2],
            "height": decision.expandedBBox[3],
        },
        "style": {
            "visible": True,
            "opacity": 1,
            "fill": decision.background["color"],
            "radius": 0,
        },
        "meta": {
            "source": "text_replacement",
            "sourceBoxId": decision.ocrBlockId,
            "reason": "m11_cover_original_text",
            "backgroundConfidence": decision.background["confidence"],
        },
    }


def build_visible_text_element(block: OCRBlock) -> dict[str, Any]:
    return {
        "id": f"visible_text_{block.id}",
        "type": "text",
        "role": "visible_text_replacement",
        "name": f"Visible Text Replacement / {block.id}",
        "layout": {
            "x": block.bbox[0],
            "y": block.bbox[1],
            "width": block.bbox[2],
            "height": block.bbox[3],
        },
        "style": {
            "visible": True,
            "opacity": 1,
            "color": "#111111",
            "fontSize": max(10, min(round(block.bbox[3] * 0.75), 32)),
            "fontWeight": 400,
        },
        "content": {
            "text": block.text,
        },
        "meta": {
            "source": "text_replacement",
            "sourceBoxId": block.id,
            "ocrConfidence": block.confidence,
            "reason": "m11_low_risk_visible_text",
        },
    }
