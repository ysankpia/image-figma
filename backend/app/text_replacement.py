from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .config import Settings
from .ocr import OCRBlock, OCRDocument
from .png_tools import (
    BackgroundSample,
    PngMetadata,
    PngPixels,
    UnsupportedPngCropError,
    clamp_int,
    decode_png_pixels,
    rgb_to_hex,
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
    foreground: dict[str, Any] | None = None
    sourceOcrBlockIds: list[str] = field(default_factory=list)
    patches: list[str] = field(default_factory=list)
    quality: dict[str, Any] = field(default_factory=dict)
    application: dict[str, str] = field(default_factory=dict)


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


@dataclass
class ForegroundSample:
    bbox: list[int]
    color: str
    mean_rgb: list[int]
    brightness: float
    contrast: float
    confidence: float
    sample_count: int


@dataclass
class ReplacementCandidate:
    id: str
    text: str
    bbox: list[int]
    confidence: float
    lineId: str
    blockId: str
    source: str
    source_ids: list[str]


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

    candidates, merge_warnings = build_replacement_candidates(ocr_document.blocks)
    decisions: list[TextReplacementDecision] = []
    accepted_count = 0
    for candidate in candidates:
        decision = evaluate_candidate(candidate, pixels, accepted_count, settings)
        if decision.decision == "accepted":
            accepted_count += 1
        decisions.append(decision)

    decisions = add_quality_control(decisions, image)
    accepted = sum(1 for decision in decisions if decision.decision == "accepted")
    rejected = sum(1 for decision in decisions if decision.decision == "rejected")
    applied = sum(1 for decision in decisions if decision.application.get("status") == "applied")
    blocked = sum(1 for decision in decisions if decision.application.get("status") == "blocked")
    low_risk = sum(1 for decision in decisions if decision.quality.get("risk") == "low")
    medium_risk = sum(1 for decision in decisions if decision.quality.get("risk") == "medium")
    high_risk = sum(1 for decision in decisions if decision.quality.get("risk") == "high")
    colored = sum(
        1
        for decision in decisions
        if decision.decision == "accepted"
        and decision.reason in {"solid_colored_background", "dark_or_colored_background_light_text"}
    )
    text_color_estimated = sum(1 for decision in decisions if decision.foreground is not None)
    merged = sum(1 for decision in decisions if len(decision.sourceOcrBlockIds) > 1)
    return TextReplacementDocument(
        version="0.1",
        taskId=task_id,
        mode=mode,
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        decisions=decisions,
        warnings=merge_warnings,
        meta={
            "notes": "text_replacement_coverage_expansion",
            "qualityNotes": "text_replacement_quality_control",
            "acceptedCount": accepted,
            "rejectedCount": rejected,
            "appliedCount": applied,
            "blockedAcceptedCount": blocked,
            "lowRiskCount": low_risk,
            "mediumRiskCount": medium_risk,
            "highRiskCount": high_risk,
            "regionSummary": summarize_quality_regions(decisions),
            "reasonSummary": summarize_quality_reasons(decisions),
            "coloredBackgroundAcceptedCount": colored,
            "mergedBlockCount": merged,
            "textColorEstimatedCount": text_color_estimated,
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
            "notes": "text_replacement_coverage_expansion",
            "qualityNotes": "text_replacement_quality_control",
            "acceptedCount": 0,
            "rejectedCount": 0,
            "appliedCount": 0,
            "blockedAcceptedCount": 0,
            "lowRiskCount": 0,
            "mediumRiskCount": 0,
            "highRiskCount": 0,
            "regionSummary": {},
            "reasonSummary": {},
            "coloredBackgroundAcceptedCount": 0,
            "mergedBlockCount": 0,
            "textColorEstimatedCount": 0,
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
            "notes": "text_replacement_coverage_expansion",
            "qualityNotes": "text_replacement_quality_control",
            "acceptedCount": 0,
            "rejectedCount": 0,
            "appliedCount": 0,
            "blockedAcceptedCount": 0,
            "lowRiskCount": 0,
            "mediumRiskCount": 0,
            "highRiskCount": 0,
            "regionSummary": {},
            "reasonSummary": {},
            "coloredBackgroundAcceptedCount": 0,
            "mergedBlockCount": 0,
            "textColorEstimatedCount": 0,
        },
        error={"code": code, "message": message},
    )


def build_replacement_candidates(blocks: list[OCRBlock]) -> tuple[list[ReplacementCandidate], list[TextReplacementWarning]]:
    sorted_blocks = sorted(blocks, key=lambda block: (block.bbox[1], block.bbox[0]))
    candidates: list[ReplacementCandidate] = []
    warnings: list[TextReplacementWarning] = []
    index = 0
    while index < len(sorted_blocks):
        current = block_to_candidate(sorted_blocks[index])
        index += 1
        while index < len(sorted_blocks) and should_merge_candidate(current, sorted_blocks[index]):
            current = merge_candidate_with_block(current, sorted_blocks[index])
            index += 1
        if len(current.source_ids) > 1:
            warnings.append(
                TextReplacementWarning(
                    code="OCR_BLOCKS_MERGED",
                    message=f"Merged OCR blocks into replacement candidate: {current.id}.",
                    ocrBlockId=current.id,
                )
            )
        candidates.append(current)
    return candidates, warnings


def block_to_candidate(block: OCRBlock) -> ReplacementCandidate:
    return ReplacementCandidate(
        id=block.id,
        text=block.text,
        bbox=list(block.bbox),
        confidence=block.confidence,
        lineId=block.lineId,
        blockId=block.blockId,
        source=block.source,
        source_ids=[block.id],
    )


def should_merge_candidate(candidate: ReplacementCandidate, block: OCRBlock) -> bool:
    if candidate.bbox[1] < 44 or block.bbox[1] < 44:
        return False
    c_height = candidate.bbox[3]
    b_height = block.bbox[3]
    avg_height = (c_height + b_height) / 2
    if avg_height <= 0 or abs(c_height - b_height) > avg_height * 0.35:
        return False
    c_center_y = candidate.bbox[1] + c_height / 2
    b_center_y = block.bbox[1] + b_height / 2
    same_line = candidate.lineId == block.lineId or abs(c_center_y - b_center_y) <= max(4, avg_height * 0.28)
    if not same_line:
        return False
    gap = block.bbox[0] - (candidate.bbox[0] + candidate.bbox[2])
    if gap < 0 or gap > max(12, avg_height * 0.6):
        return False
    return is_mergeable_text_pair(candidate.text, block.text)


def is_mergeable_text_pair(left: str, right: str) -> bool:
    left = left.strip()
    right = right.strip()
    if not left or not right:
        return False
    if left.endswith(("：", ":", "-", "/")):
        return True
    if right.startswith(("：", ":", "-", "/")):
        return True
    if len(left) <= 3 and len(right) <= 3:
        return False
    return not (is_short_label(left) and is_short_label(right))


def is_short_label(text: str) -> bool:
    return len(text.strip()) <= 4


def merge_candidate_with_block(candidate: ReplacementCandidate, block: OCRBlock) -> ReplacementCandidate:
    x1 = min(candidate.bbox[0], block.bbox[0])
    y1 = min(candidate.bbox[1], block.bbox[1])
    x2 = max(candidate.bbox[0] + candidate.bbox[2], block.bbox[0] + block.bbox[2])
    y2 = max(candidate.bbox[1] + candidate.bbox[3], block.bbox[1] + block.bbox[3])
    return ReplacementCandidate(
        id=f"merged_{candidate.source_ids[0]}_{block.id}",
        text=f"{candidate.text}{block.text}",
        bbox=[x1, y1, x2 - x1, y2 - y1],
        confidence=min(candidate.confidence, block.confidence),
        lineId=candidate.lineId,
        blockId=candidate.blockId,
        source=candidate.source,
        source_ids=[*candidate.source_ids, block.id],
    )


def evaluate_candidate(
    candidate: ReplacementCandidate,
    pixels: PngPixels,
    accepted_count: int,
    settings: Settings,
) -> TextReplacementDecision:
    if accepted_count >= settings.text_replacement_max_blocks:
        return reject(candidate, "max_blocks_reached")
    if not candidate.text.strip():
        return reject(candidate, "empty_text")
    if "\n" in candidate.text or "\r" in candidate.text:
        return reject(candidate, "multiline_not_supported")
    if candidate.confidence < settings.text_replacement_min_confidence:
        return reject(candidate, "confidence_too_low")
    width = candidate.bbox[2]
    height = candidate.bbox[3]
    if width < settings.text_replacement_min_width or height < settings.text_replacement_min_height:
        return reject(candidate, "bbox_too_small")
    if height > settings.text_replacement_max_height:
        return reject(candidate, "bbox_too_tall")
    if candidate.bbox[1] < 44:
        return reject(candidate, "status_bar_or_too_small")

    expanded_bbox = expand_bbox(
        candidate.bbox,
        pixels.width,
        pixels.height,
        max(0, settings.text_replacement_edge_sample_padding),
    )
    if not replacement_box_is_safe(candidate.bbox, expanded_bbox):
        return reject(candidate, "replacement_box_unsafe", expanded_bbox)

    try:
        background = sample_region_background(
            pixels,
            expanded_bbox,
            settings.text_replacement_solid_bg_tolerance,
        )
        foreground = sample_text_foreground(
            pixels,
            candidate.bbox,
            background.mean_rgb,
            max(0, settings.text_replacement_text_sample_inset),
        )
    except UnsupportedPngCropError:
        return reject(candidate, "png_sampling_unsupported", expanded_bbox)

    if background.max_channel_delta > settings.text_replacement_solid_bg_tolerance:
        return reject(candidate, "complex_background", expanded_bbox, background, foreground)
    if foreground is None:
        if background.brightness < 180:
            return reject(candidate, "dark_background", expanded_bbox, background)
        return reject(candidate, "text_color_uncertain", expanded_bbox, background)
    if foreground.contrast < settings.text_replacement_min_contrast:
        return reject(candidate, "foreground_background_low_contrast", expanded_bbox, background, foreground)

    if background.brightness >= 180 and foreground.brightness <= 140:
        return accept(candidate, "solid_light_background", expanded_bbox, background, foreground)
    if settings.text_replacement_enable_colored_bg and foreground.brightness >= 170:
        if background.brightness < 180:
            return accept(candidate, "dark_or_colored_background_light_text", expanded_bbox, background, foreground)
        if saturation(background.mean_rgb) >= 35:
            return accept(candidate, "solid_colored_background", expanded_bbox, background, foreground)
    if background.brightness < 180:
        return reject(candidate, "dark_background", expanded_bbox, background, foreground)
    return reject(candidate, "text_color_uncertain", expanded_bbox, background, foreground)


def replacement_box_is_safe(bbox: list[int], expanded_bbox: list[int]) -> bool:
    return expanded_bbox[2] <= bbox[2] + 16 and expanded_bbox[3] <= bbox[3] + 16


def accept(
    candidate: ReplacementCandidate,
    reason: str,
    expanded_bbox: list[int],
    background: BackgroundSample,
    foreground: ForegroundSample,
) -> TextReplacementDecision:
    return TextReplacementDecision(
        ocrBlockId=candidate.id,
        decision="accepted",
        reason=reason,
        bbox=list(candidate.bbox),
        expandedBBox=expanded_bbox,
        background=background_to_dict(background),
        foreground=foreground_to_dict(foreground),
        sourceOcrBlockIds=list(candidate.source_ids),
        patches=[f"cover_{candidate.id}", f"visible_text_{candidate.id}"],
    )


def reject(
    candidate: ReplacementCandidate | OCRBlock,
    reason: str,
    expanded_bbox: list[int] | None = None,
    background: BackgroundSample | None = None,
    foreground: ForegroundSample | None = None,
) -> TextReplacementDecision:
    source_ids = list(candidate.source_ids) if isinstance(candidate, ReplacementCandidate) else [candidate.id]
    return TextReplacementDecision(
        ocrBlockId=candidate.id,
        decision="rejected",
        reason=reason,
        bbox=list(candidate.bbox),
        expandedBBox=expanded_bbox,
        background=background_to_dict(background) if background else None,
        foreground=foreground_to_dict(foreground) if foreground else None,
        sourceOcrBlockIds=source_ids,
        patches=[],
    )


def add_quality_control(decisions: list[TextReplacementDecision], image: PngMetadata) -> list[TextReplacementDecision]:
    return [with_quality_control(decision, image) for decision in decisions]


def with_quality_control(decision: TextReplacementDecision, image: PngMetadata) -> TextReplacementDecision:
    quality = evaluate_replacement_quality(decision, image)
    decision.quality = quality
    if decision.decision != "accepted":
        decision.application = {"status": "not_applicable", "reason": "decision_not_accepted"}
    elif quality["applyEligible"]:
        decision.application = {"status": "applied", "reason": "quality_gate_passed"}
    else:
        decision.application = {"status": "blocked", "reason": "quality_gate_blocked"}
    return decision


def evaluate_replacement_quality(decision: TextReplacementDecision, image: PngMetadata) -> dict[str, Any]:
    region = classify_replacement_region(decision.bbox, image)
    reasons = quality_reason_codes(decision, region)
    score = quality_score(decision, reasons)
    risk = quality_risk(decision, score, reasons)
    return {
        "score": score,
        "risk": risk,
        "applyEligible": decision.decision == "accepted" and risk == "low",
        "reasons": reasons,
        "region": region,
    }


def quality_reason_codes(decision: TextReplacementDecision, region: str) -> list[str]:
    reasons: list[str] = []
    if decision.decision != "accepted":
        reasons.append(f"{decision.reason}_rejected")
        if decision.background is not None:
            reasons.append("background_sample_available")
        if decision.foreground is not None:
            reasons.append("foreground_sample_available")
        return reasons

    if decision.background is None or decision.foreground is None:
        return ["missing_quality_samples"]

    background_confidence = float(decision.background.get("confidence", 0))
    foreground_contrast = float(decision.foreground.get("contrast", 0))
    foreground_sample_count = int(decision.foreground.get("sampleCount", 0))
    contrast_margin = foreground_contrast - 90
    cover_ratio = replacement_cover_area_ratio(decision)

    if background_confidence >= 0.72:
        reasons.append("stable_background")
    else:
        reasons.append("borderline_background_confidence")
    if contrast_margin >= 45:
        reasons.append("strong_contrast_margin")
    elif contrast_margin >= 20:
        reasons.append("moderate_contrast_margin")
    else:
        reasons.append("low_contrast_margin")
    if foreground_sample_count >= 12:
        reasons.append("foreground_sample_sufficient")
    else:
        reasons.append("foreground_sample_sparse")
    if cover_ratio <= 1.9:
        reasons.append("cover_area_safe")
    else:
        reasons.append("large_cover_area")
    if region in {"hero", "preview_card", "tip_card"}:
        reasons.append(f"{region}_region_caution")
    if decision.bbox[1] < 44:
        reasons.append("near_status_bar")

    if all(
        reason not in reasons
        for reason in {
            "borderline_background_confidence",
            "low_contrast_margin",
            "foreground_sample_sparse",
            "large_cover_area",
            "hero_region_caution",
            "preview_card_region_caution",
            "tip_card_region_caution",
            "near_status_bar",
        }
    ):
        reasons.append("accepted_low_risk")
    return reasons


def quality_score(decision: TextReplacementDecision, reasons: list[str]) -> int:
    if decision.decision != "accepted":
        return 0
    score = 100
    penalties = {
        "missing_quality_samples": 100,
        "borderline_background_confidence": 30,
        "low_contrast_margin": 30,
        "moderate_contrast_margin": 10,
        "foreground_sample_sparse": 20,
        "large_cover_area": 25,
        "hero_region_caution": 20,
        "preview_card_region_caution": 20,
        "tip_card_region_caution": 20,
        "near_status_bar": 30,
    }
    for reason in reasons:
        score -= penalties.get(reason, 0)
    return max(0, min(100, score))


def quality_risk(decision: TextReplacementDecision, score: int, reasons: list[str]) -> str:
    if decision.decision != "accepted":
        return "high"
    high_risk_reasons = {"missing_quality_samples", "low_contrast_margin", "large_cover_area", "near_status_bar"}
    if any(reason in high_risk_reasons for reason in reasons) or score < 55:
        return "high"
    medium_risk_reasons = {
        "borderline_background_confidence",
        "foreground_sample_sparse",
        "hero_region_caution",
        "preview_card_region_caution",
        "tip_card_region_caution",
    }
    if any(reason in medium_risk_reasons for reason in reasons) or score < 80:
        return "medium"
    return "low"


def replacement_cover_area_ratio(decision: TextReplacementDecision) -> float:
    if decision.expandedBBox is None or decision.bbox[2] <= 0 or decision.bbox[3] <= 0:
        return 999
    bbox_area = decision.bbox[2] * decision.bbox[3]
    cover_area = decision.expandedBBox[2] * decision.expandedBBox[3]
    return cover_area / max(1, bbox_area)


def classify_replacement_region(bbox: list[int], image: PngMetadata) -> str:
    center_y = bbox[1] + (bbox[3] / 2)
    ratio = center_y / max(1, image.height)
    if ratio < 0.06:
        return "header"
    if ratio < 0.18:
        return "hero"
    if ratio < 0.42:
        return "summary"
    if ratio < 0.62:
        return "card_grid"
    if ratio < 0.78:
        return "preview_card"
    if ratio < 0.88:
        return "tip_card"
    if ratio >= 0.88:
        return "bottom_nav"
    return "unknown"


def summarize_quality_regions(decisions: list[TextReplacementDecision]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for decision in decisions:
        region = str(decision.quality.get("region", "unknown"))
        item = summary.setdefault(region, {"total": 0, "accepted": 0, "applied": 0, "blocked": 0, "rejected": 0})
        item["total"] += 1
        if decision.decision == "accepted":
            item["accepted"] += 1
        if decision.decision == "rejected":
            item["rejected"] += 1
        status = decision.application.get("status")
        if status == "applied":
            item["applied"] += 1
        elif status == "blocked":
            item["blocked"] += 1
    return summary


def summarize_quality_reasons(decisions: list[TextReplacementDecision]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for decision in decisions:
        for reason in decision.quality.get("reasons", []):
            summary[str(reason)] = summary.get(str(reason), 0) + 1
    return summary


def expand_bbox(bbox: list[int], image_width: int, image_height: int, padding: int) -> list[int]:
    x, y, width, height = bbox
    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(image_width, x + width + padding)
    y2 = min(image_height, y + height + padding)
    return [x1, y1, max(1, x2 - x1), max(1, y2 - y1)]


def sample_text_foreground(
    pixels: PngPixels,
    bbox: list[int],
    background_rgb: list[int],
    inset: int,
) -> ForegroundSample | None:
    x, y, width, height = [round(value) for value in bbox]
    x1 = clamp_int(x + inset, 0, pixels.width)
    y1 = clamp_int(y + inset, 0, pixels.height)
    x2 = clamp_int(x + width - inset, 0, pixels.width)
    y2 = clamp_int(y + height - inset, 0, pixels.height)
    if x2 <= x1 or y2 <= y1:
        raise UnsupportedPngCropError("Text foreground sample bbox does not intersect image bounds.")

    candidates: list[tuple[int, int, int]] = []
    for row_index in range(y1, y2):
        row = pixels.rows[row_index]
        for column in range(x1, x2):
            offset = column * 3
            rgb = (row[offset], row[offset + 1], row[offset + 2])
            if rgb_distance(rgb, background_rgb) >= 35:
                candidates.append(rgb)
    if not candidates:
        return None

    candidates.sort(key=lambda rgb: rgb_distance(rgb, background_rgb), reverse=True)
    selected = candidates[: max(3, min(len(candidates), max(12, len(candidates) // 4)))]
    mean_rgb = [round(sum(rgb[channel] for rgb in selected) / len(selected)) for channel in range(3)]
    brightness = luminance(mean_rgb)
    contrast = abs(brightness - luminance(background_rgb))
    confidence = max(0, min(1, contrast / 180))
    return ForegroundSample(
        bbox=[x1, y1, x2 - x1, y2 - y1],
        color=rgb_to_hex(mean_rgb),
        mean_rgb=mean_rgb,
        brightness=round(brightness, 3),
        contrast=round(contrast, 3),
        confidence=round(confidence, 3),
        sample_count=len(selected),
    )


def background_to_dict(background: BackgroundSample) -> dict[str, Any]:
    return {
        "color": background.color,
        "meanRgb": background.mean_rgb,
        "maxChannelDelta": background.max_channel_delta,
        "brightness": background.brightness,
        "confidence": background.confidence,
    }


def foreground_to_dict(foreground: ForegroundSample) -> dict[str, Any]:
    return {
        "color": foreground.color,
        "meanRgb": foreground.mean_rgb,
        "brightness": foreground.brightness,
        "contrast": foreground.contrast,
        "confidence": foreground.confidence,
        "sampleCount": foreground.sample_count,
    }


def apply_text_replacements(
    dsl: dict[str, Any],
    document: TextReplacementDocument,
    ocr_document: OCRDocument,
) -> dict[str, Any]:
    if document.mode != "apply" or document.status != "completed":
        return deepcopy(dsl)

    candidates = build_candidates_from_document(document, ocr_document)
    next_dsl = deepcopy(dsl)
    root = next_dsl.setdefault("root", {})
    children = root.setdefault("children", [])
    added_count = 0
    blocked_count = 0
    for decision in document.decisions:
        if decision.decision != "accepted":
            continue
        if not decision.quality.get("applyEligible", True):
            blocked_count += 1
            continue
        candidate = candidates.get(decision.ocrBlockId)
        if candidate is None or decision.expandedBBox is None or decision.background is None or decision.foreground is None:
            continue
        children.append(build_cover_element(decision))
        children.append(build_visible_text_element(candidate, decision))
        added_count += 1

    if added_count:
        meta = next_dsl.setdefault("meta", {})
        notes = str(meta.get("notes") or "")
        if "m12_text_replacement_apply" not in notes:
            meta["notes"] = f"{notes}+m12_text_replacement_apply" if notes else "m12_text_replacement_apply"
        quality_flags = list(meta.get("qualityFlags") or [])
        if "m11_visible_text_replacements" not in quality_flags:
            quality_flags.append("m11_visible_text_replacements")
        if "m12_text_replacement_coverage_expansion" not in quality_flags:
            quality_flags.append("m12_text_replacement_coverage_expansion")
        if "m13_text_replacement_quality_control" not in quality_flags:
            quality_flags.append("m13_text_replacement_quality_control")
        meta["qualityFlags"] = quality_flags
        meta["textReplacementCount"] = added_count
        meta["textReplacementAppliedCount"] = added_count
        meta["textReplacementBlockedCount"] = blocked_count
        meta["elementCount"] = len(children)
    elif blocked_count:
        meta = next_dsl.setdefault("meta", {})
        quality_flags = list(meta.get("qualityFlags") or [])
        if "m13_text_replacement_quality_control" not in quality_flags:
            quality_flags.append("m13_text_replacement_quality_control")
        meta["qualityFlags"] = quality_flags
        meta["textReplacementAppliedCount"] = 0
        meta["textReplacementBlockedCount"] = blocked_count
    return next_dsl


def build_candidates_from_document(
    document: TextReplacementDocument,
    ocr_document: OCRDocument,
) -> dict[str, ReplacementCandidate]:
    by_id = {block.id: block for block in ocr_document.blocks}
    candidates: dict[str, ReplacementCandidate] = {}
    for decision in document.decisions:
        source_ids = decision.sourceOcrBlockIds or [decision.ocrBlockId]
        source_blocks = [by_id[source_id] for source_id in source_ids if source_id in by_id]
        if len(source_blocks) == len(source_ids) and source_blocks:
            candidate = block_to_candidate(source_blocks[0])
            for block in source_blocks[1:]:
                candidate = merge_candidate_with_block(candidate, block)
            candidate.id = decision.ocrBlockId
            candidate.bbox = list(decision.bbox)
            candidates[decision.ocrBlockId] = candidate
    return candidates


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
            "sourceOcrBlockIds": decision.sourceOcrBlockIds,
            "reason": "m12_cover_original_text",
            "backgroundConfidence": decision.background["confidence"],
        },
    }


def build_visible_text_element(
    candidate: ReplacementCandidate | OCRBlock,
    decision: TextReplacementDecision | None = None,
) -> dict[str, Any]:
    bbox = list(candidate.bbox)
    font_size = visible_text_font_size(candidate.text, bbox)
    line_height = max(bbox[3], round(font_size * 1.15))
    color = "#111111"
    source_ids = [candidate.id]
    reason = "m12_text_replacement_visible_text"
    if decision is not None:
        source_ids = decision.sourceOcrBlockIds or [decision.ocrBlockId]
        if decision.foreground is not None:
            color = decision.foreground["color"]
        reason = "m12_low_risk_visible_text"
    return {
        "id": f"visible_text_{candidate.id}",
        "type": "text",
        "role": "visible_text_replacement",
        "name": f"Visible Text Replacement / {candidate.id}",
        "layout": {
            "x": bbox[0],
            "y": bbox[1],
            "width": max(bbox[2], round(estimate_text_width_units(candidate.text) * font_size)),
            "height": max(bbox[3], line_height),
        },
        "style": {
            "visible": True,
            "opacity": 1,
            "color": color,
            "fontFamily": "PingFang SC",
            "fontSize": font_size,
            "fontWeight": 400,
            "lineHeight": line_height,
            "textAlign": "left",
        },
        "content": {
            "text": candidate.text,
        },
        "meta": {
            "source": "text_replacement",
            "sourceBoxId": candidate.id,
            "sourceOcrBlockIds": source_ids,
            "ocrConfidence": candidate.confidence,
            "reason": reason,
        },
    }


def visible_text_font_size(text: str, bbox: list[int]) -> int:
    height_size = max(10, min(round(bbox[3] * 0.75), 32))
    text_width = estimate_text_width_units(text)
    if text_width <= 0:
        return height_size
    width_size = int((bbox[2] * 0.92) / text_width)
    return max(10, min(height_size, width_size))


def estimate_text_width_units(text: str) -> float:
    width = 0.0
    for char in text.strip():
        codepoint = ord(char)
        if char.isspace():
            width += 0.33
        elif codepoint < 128:
            width += 0.56 if char.isdigit() else 0.62
        elif char in {"·", "・", ".", ",", "，", "。", ":", "：", "-", "_", "/"}:
            width += 0.35
        else:
            width += 1.0
    return width


def rgb_distance(rgb: tuple[int, int, int] | list[int], other: tuple[int, int, int] | list[int]) -> float:
    return max(abs(rgb[0] - other[0]), abs(rgb[1] - other[1]), abs(rgb[2] - other[2]))


def luminance(rgb: tuple[int, int, int] | list[int]) -> float:
    return (rgb[0] * 0.299) + (rgb[1] * 0.587) + (rgb[2] * 0.114)


def saturation(rgb: list[int]) -> int:
    return max(rgb) - min(rgb)
