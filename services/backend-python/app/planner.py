from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from .config import PlannerConfig
from .schema import (
    BBox,
    CandidateClassification,
    DraftElement,
    ObjectCandidate,
    PromotionDecision,
    TextBlock,
)
from .spatial import intersection_area, ioa
from .style import sample_fill, sample_text_color

IMAGE_ROLES = {"icon", "avatar", "thumbnail", "photo", "logo", "illustration"}
RASTER_ROLES_WITH_INTERNAL_TEXT = {"thumbnail", "photo", "illustration", "logo"}
EDGE_CLIPPABLE_IMAGE_ROLES = {"icon", "avatar", "thumbnail", "logo"}
SHAPE_ROLES = {"card_bg", "button_bg", "bar_bg"}
SUPPRESS_ROLES = {"noise", "text", "unknown"}
INTERNAL_TEXT_MAX_OVERLAP_RATIO = 0.20
INTERNAL_TEXT_MIN_AREA = 8_000
EDGE_TEXT_CLIP_MAX_OVERLAP_RATIO = 0.45
EDGE_TEXT_CLIP_MIN_RETAINED_RATIO = 0.20
COMPACT_UNKNOWN_IMAGE_MAX_AREA = 24_000
COMPACT_UNKNOWN_IMAGE_MAX_TEXT_BLOCKS = 2
COMPACT_UNKNOWN_IMAGE_MAX_OVERLAP_RATIO = 0.45


@dataclass
class PromotionResult:
    elements: list[DraftElement]
    decisions: list[PromotionDecision]


def promote_elements(
    image: Image.Image,
    texts: list[TextBlock],
    candidates: list[ObjectCandidate],
    classifications: list[CandidateClassification],
    config: PlannerConfig,
    vlm_available: bool,
) -> PromotionResult:
    elements: list[DraftElement] = []
    decisions: list[PromotionDecision] = []

    for index, text in enumerate(texts, start=1):
        elements.append(
            DraftElement(
                id=f"node_text_{index:04d}",
                type="text",
                role="TextView",
                bbox=text.bbox,
                z=30_000 + index,
                confidence=text.confidence,
                source_ids=[text.id],
                decision_reason="emit_text",
                text=text.text,
                style={
                    "fontSize": max(8, min(96, round(text.bbox.height * 0.8))),
                    "color": sample_text_color(image, text.bbox),
                },
            )
        )

    classification_by_candidate = {item.candidate_id: item for item in classifications}
    accepted_images: list[DraftElement] = []
    visual_index = 1
    page_area = image.width * image.height

    for candidate in sorted(candidates, key=lambda item: (item.bbox.y, item.bbox.x, item.id)):
        classification = classification_by_candidate.get(candidate.id)
        if classification is None:
            reason = "suppress_provider_missing" if not vlm_available else "suppress_unclassified"
            decisions.append(PromotionDecision(candidate.id, "suppress", reason))
            continue

        decision, reason, emit_bbox = candidate_decision(candidate, classification, config, page_area, texts)
        if decision == "emit_image" and covered_by_accepted_image(emit_bbox, accepted_images):
            decision, reason = "suppress", "suppress_duplicate"

        if decision == "emit_image":
            element_id = f"node_image_{visual_index:04d}"
            element = DraftElement(
                id=element_id,
                type="image",
                role=classification.role,
                bbox=emit_bbox,
                z=20_000 + visual_index,
                confidence=classification.confidence,
                source_ids=[candidate.id],
                decision_reason=reason,
            )
            elements.append(element)
            accepted_images.append(element)
            decisions.append(to_decision(candidate, classification, "emit_image", reason, element_id))
            visual_index += 1
            continue

        if decision == "emit_shape":
            element_id = f"node_shape_{visual_index:04d}"
            elements.append(
                DraftElement(
                    id=element_id,
                    type="shape",
                    role=classification.role,
                    bbox=candidate.bbox,
                    z=10_000 + visual_index,
                    confidence=classification.confidence,
                    source_ids=[candidate.id],
                    decision_reason=reason,
                    style={"fill": sample_fill(image, candidate.bbox), "opacity": 1},
                )
            )
            decisions.append(to_decision(candidate, classification, "emit_shape", reason, element_id))
            visual_index += 1
            continue

        decisions.append(to_decision(candidate, classification, "suppress", reason))

    elements.sort(key=lambda item: (item.z, item.bbox.y, item.bbox.x, item.id))
    return PromotionResult(elements=elements, decisions=decisions)


def candidate_decision(
    candidate: ObjectCandidate,
    classification: CandidateClassification,
    config: PlannerConfig,
    page_area: int,
    texts: list[TextBlock],
) -> tuple[str, str, BBox]:
    if classification.confidence < 0.65:
        return "suppress", "suppress_low_confidence", candidate.bbox
    if classification.role in {"noise", "text"}:
        return "suppress", "suppress_unknown_role", candidate.bbox
    if classification.role == "unknown" and classification.kind == "suppress":
        clipped = clipped_image_bbox(candidate, texts, config)
        if clipped is not None and is_compact_unknown_image_candidate(candidate):
            return "emit_image", "emit_image_unknown_text_clipped", clipped
        if is_compact_unknown_image_candidate(candidate):
            return "emit_image", "emit_image_compact_unknown", candidate.bbox
        return "suppress", "suppress_unknown_role", candidate.bbox

    if classification.role in IMAGE_ROLES and classification.kind in {"image", "shape"}:
        if candidate.area < config.image_min_area or candidate.bbox.width < 10 or candidate.bbox.height < 10:
            return "suppress", "suppress_too_small", candidate.bbox
        if page_area > 0 and candidate.area > page_area * 0.40:
            return "suppress", "suppress_too_large", candidate.bbox

        clipped = None
        if classification.role in EDGE_CLIPPABLE_IMAGE_ROLES:
            clipped = clipped_image_bbox(candidate, texts, config)
        if classification.decision != "emit":
            if classification.kind == "image" and clipped is not None:
                return "emit_image", "emit_image_text_clipped", clipped
            return "suppress", "suppress_classifier", candidate.bbox

        if candidate.text_overlap_ratio > config.text_overlap_suppress_ratio or candidate.text_block_count >= 2:
            if clipped is not None:
                return "emit_image", "emit_image_text_clipped", clipped
            if allows_internal_text(candidate, classification):
                return "emit_image", "emit_image_with_internal_text", candidate.bbox
            if candidate.text_block_count >= 2:
                return "suppress", "suppress_contains_text", candidate.bbox
            return "suppress", "suppress_text_overlap", candidate.bbox

        if classification.kind == "shape":
            return "emit_image", "emit_image_kind_repaired", candidate.bbox
        return "emit_image", "emit_image", candidate.bbox

    if classification.decision != "emit" or classification.kind == "suppress":
        return "suppress", "suppress_classifier", candidate.bbox

    if classification.role in SHAPE_ROLES and classification.kind == "shape":
        if candidate.area < config.shape_min_area or candidate.bbox.width < 16 or candidate.bbox.height < 8:
            return "suppress", "suppress_too_small", candidate.bbox
        if page_area > 0 and candidate.area > page_area * 0.60:
            return "suppress", "suppress_full_page_backing", candidate.bbox
        return "emit_shape", "emit_shape", candidate.bbox

    if classification.role == "divider" and classification.kind == "shape":
        if min(candidate.bbox.width, candidate.bbox.height) <= 4 and max(candidate.bbox.width, candidate.bbox.height) >= 24:
            return "emit_shape", "emit_divider", candidate.bbox
        return "suppress", "suppress_bad_divider_geometry", candidate.bbox

    return "suppress", "suppress_unknown_role", candidate.bbox


def allows_internal_text(candidate: ObjectCandidate, classification: CandidateClassification) -> bool:
    if classification.role not in RASTER_ROLES_WITH_INTERNAL_TEXT:
        return False
    if candidate.area < INTERNAL_TEXT_MIN_AREA:
        return False
    return candidate.text_overlap_ratio <= INTERNAL_TEXT_MAX_OVERLAP_RATIO


def is_compact_unknown_image_candidate(candidate: ObjectCandidate) -> bool:
    if candidate.area < 400 or candidate.area > COMPACT_UNKNOWN_IMAGE_MAX_AREA:
        return False
    if candidate.bbox.width < 10 or candidate.bbox.height < 10:
        return False
    aspect = candidate.bbox.width / candidate.bbox.height
    if aspect < 0.33 or aspect > 3.0:
        return False
    if candidate.text_block_count > COMPACT_UNKNOWN_IMAGE_MAX_TEXT_BLOCKS:
        return False
    return candidate.text_overlap_ratio <= COMPACT_UNKNOWN_IMAGE_MAX_OVERLAP_RATIO


def clipped_image_bbox(
    candidate: ObjectCandidate,
    texts: list[TextBlock],
    config: PlannerConfig,
) -> BBox | None:
    if candidate.text_overlap_ratio <= config.text_overlap_suppress_ratio:
        return None
    if candidate.text_overlap_ratio > EDGE_TEXT_CLIP_MAX_OVERLAP_RATIO:
        return None
    if candidate.bbox.area <= 0:
        return None

    overlaps = [text.bbox for text in texts if intersection_area(candidate.bbox, text.bbox) > 0]
    if not overlaps:
        return None

    box = candidate.bbox
    mid_x = box.x + box.width / 2
    mid_y = box.y + box.height / 2
    proposals: list[BBox] = []

    bottom_texts = [text for text in overlaps if text.y + text.height / 2 >= mid_y]
    if bottom_texts:
        y2 = min(text.y for text in bottom_texts)
        proposals.append(BBox(box.x, box.y, box.width, max(0, y2 - box.y)))

    top_texts = [text for text in overlaps if text.y + text.height / 2 <= mid_y]
    if top_texts:
        y1 = max(text.y2 for text in top_texts)
        proposals.append(BBox(box.x, y1, box.width, max(0, box.y2 - y1)))

    right_texts = [text for text in overlaps if text.x + text.width / 2 >= mid_x]
    if right_texts:
        x2 = min(text.x for text in right_texts)
        proposals.append(BBox(box.x, box.y, max(0, x2 - box.x), box.height))

    left_texts = [text for text in overlaps if text.x + text.width / 2 <= mid_x]
    if left_texts:
        x1 = max(text.x2 for text in left_texts)
        proposals.append(BBox(x1, box.y, max(0, box.x2 - x1), box.height))

    valid = [
        proposal
        for proposal in proposals
        if is_valid_clipped_image_bbox(proposal, box, texts, config)
    ]
    if not valid:
        return None
    return max(valid, key=lambda item: item.area)


def is_valid_clipped_image_bbox(
    proposal: BBox,
    original: BBox,
    texts: list[TextBlock],
    config: PlannerConfig,
) -> bool:
    if proposal.width < 10 or proposal.height < 10 or proposal.area < config.image_min_area:
        return False
    if proposal.area < original.area * EDGE_TEXT_CLIP_MIN_RETAINED_RATIO:
        return False
    if text_overlap_ratio(proposal, texts) > config.text_overlap_suppress_ratio:
        return False
    return True


def text_overlap_ratio(box: BBox, texts: list[TextBlock]) -> float:
    if box.area <= 0:
        return 0.0
    overlap = sum(intersection_area(box, text.bbox) for text in texts)
    return overlap / box.area


def covered_by_accepted_image(bbox: BBox, accepted_images: list[DraftElement]) -> bool:
    for image in accepted_images:
        if image.bbox.area <= bbox.area:
            continue
        if ioa(bbox, image.bbox) >= 0.85:
            return True
    return False


def to_decision(
    candidate: ObjectCandidate,
    classification: CandidateClassification,
    decision: str,
    reason: str,
    element_id: str = "",
) -> PromotionDecision:
    return PromotionDecision(
        candidate_id=candidate.id,
        decision=decision,
        reason=reason,
        emitted_element_id=element_id,
        role=classification.role,
        kind=classification.kind,
        confidence=classification.confidence,
    )
