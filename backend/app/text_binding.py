from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .config import Settings
from .ocr import OCRDocument
from .png_tools import PngMetadata
from .text_replacement import TextReplacementDecision, TextReplacementDocument
from .visual_primitives import VisualPrimitiveDocument


BindingStatus = Literal["completed", "failed", "skipped"]

CONTAINER_ROLES = {
    "unknown",
    "page_header",
    "hero_profile",
    "badge",
    "status_badge",
    "primary_button",
    "shortcut_card",
    "preview_card",
    "legend_group",
    "legend_item",
    "tip_card",
    "bottom_nav",
    "bottom_nav_item",
}


@dataclass
class TextBindingWarning:
    code: str
    message: str
    ocrBlockId: str | None = None


@dataclass
class TextBindingContainer:
    id: str
    role: str
    source: str
    bbox: list[int]
    confidence: float
    reason: str
    primitiveId: str | None = None


@dataclass
class TextPrimitiveBinding:
    id: str
    ocrBlockId: str
    text: str
    replacementElementId: str
    containerId: str
    containerRole: str
    relationship: str
    confidence: float
    reason: str
    bbox: list[int]
    containerBBox: list[int]
    source: str = "m15_inferred_binding"


@dataclass
class TextPrimitiveBindingDocument:
    version: str
    taskId: str
    status: BindingStatus
    imageSize: dict[str, int]
    containers: list[TextBindingContainer]
    bindings: list[TextPrimitiveBinding]
    unboundTextIds: list[str]
    warnings: list[TextBindingWarning]
    meta: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BindingCandidate:
    id: str
    text: str
    bbox: list[int]
    replacement_element_id: str
    region: str
    strategy_name: str | None
    decision: TextReplacementDecision


def build_text_binding_document(
    *,
    task_id: str,
    image: PngMetadata,
    ocr_document: OCRDocument,
    primitive_document: VisualPrimitiveDocument,
    replacement_document: TextReplacementDocument,
    dsl: dict[str, Any],
    settings: Settings,
) -> TextPrimitiveBindingDocument:
    if not settings.text_binding_enabled:
        return build_skipped_text_binding_document(
            task_id=task_id,
            image=image,
            code="text_binding_disabled",
            message="Text binding is disabled.",
        )
    if ocr_document.status != "completed":
        return build_skipped_text_binding_document(
            task_id=task_id,
            image=image,
            code="ocr_not_completed",
            message="Text binding skipped because OCR did not complete.",
        )
    if replacement_document.status != "completed":
        return build_skipped_text_binding_document(
            task_id=task_id,
            image=image,
            code="text_replacement_not_completed",
            message="Text binding skipped because text replacement did not complete.",
        )

    candidates = binding_candidates(ocr_document, replacement_document)
    containers = infer_text_containers(candidates, image, primitive_document)
    bindings, unbound = bind_candidates_to_containers(candidates, containers, settings.text_binding_min_confidence)
    unbound = merge_unbound_text_ids(replacement_document, bindings, unbound)

    document = TextPrimitiveBindingDocument(
        version="0.1",
        taskId=task_id,
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        containers=containers,
        bindings=bindings,
        unboundTextIds=unbound,
        warnings=[],
        meta={
            "notes": "text_primitive_binding_harness",
            "boundCount": len(bindings),
            "unboundCount": len(unbound),
            "containerCount": len(containers),
            "roleSummary": summarize_roles(containers),
            "relationshipSummary": summarize_relationships(bindings),
        },
    )
    validation_errors = validate_text_binding_document(document)
    if validation_errors:
        return build_failed_text_binding_document(
            task_id=task_id,
            image=image,
            code="TEXT_BINDING_VALIDATION_FAILED",
            message="Text binding validation failed.",
            warnings=[
                TextBindingWarning(
                    code="TEXT_BINDING_VALIDATION_ERROR",
                    message=error,
                )
                for error in validation_errors
            ],
        )
    return document


def build_skipped_text_binding_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
) -> TextPrimitiveBindingDocument:
    return TextPrimitiveBindingDocument(
        version="0.1",
        taskId=task_id,
        status="skipped",
        imageSize={"width": image.width, "height": image.height},
        containers=[],
        bindings=[],
        unboundTextIds=[],
        warnings=[TextBindingWarning(code=code, message=message)],
        meta={
            "notes": "text_primitive_binding_harness",
            "boundCount": 0,
            "unboundCount": 0,
            "containerCount": 0,
            "roleSummary": {},
            "relationshipSummary": {},
        },
        error={"code": code, "message": message},
    )


def build_failed_text_binding_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
    warnings: list[TextBindingWarning] | None = None,
) -> TextPrimitiveBindingDocument:
    return TextPrimitiveBindingDocument(
        version="0.1",
        taskId=task_id,
        status="failed",
        imageSize={"width": image.width, "height": image.height},
        containers=[],
        bindings=[],
        unboundTextIds=[],
        warnings=warnings or [TextBindingWarning(code=code, message=message)],
        meta={
            "notes": "text_primitive_binding_harness",
            "boundCount": 0,
            "unboundCount": 0,
            "containerCount": 0,
            "roleSummary": {},
            "relationshipSummary": {},
        },
        error={"code": code, "message": message},
    )


def binding_candidates(
    ocr_document: OCRDocument,
    replacement_document: TextReplacementDocument,
) -> list[BindingCandidate]:
    text_by_id = {block.id: block.text for block in ocr_document.blocks}
    candidates: list[BindingCandidate] = []
    for decision in replacement_document.decisions:
        if decision.decision != "accepted" or not decision.quality.get("applyEligible", False):
            continue
        text = text_by_id.get(decision.ocrBlockId)
        if text is None:
            source_ids = decision.sourceOcrBlockIds or []
            text = "".join(text_by_id.get(source_id, "") for source_id in source_ids).strip()
        if not text:
            continue
        candidates.append(
            BindingCandidate(
                id=decision.ocrBlockId,
                text=text,
                bbox=list(decision.bbox),
                replacement_element_id=f"visible_text_{decision.ocrBlockId}",
                region=str(decision.quality.get("region") or "unknown"),
                strategy_name=str(decision.strategy.get("name")) if decision.strategy else None,
                decision=decision,
            )
        )
    return candidates


def merge_unbound_text_ids(
    replacement_document: TextReplacementDocument,
    bindings: list[TextPrimitiveBinding],
    unbound: list[str],
) -> list[str]:
    bound_ids = {binding.ocrBlockId for binding in bindings}
    unbound_ids = list(unbound)
    seen = set(unbound_ids)
    for decision in replacement_document.decisions:
        if decision.ocrBlockId in bound_ids or decision.ocrBlockId in seen:
            continue
        if decision.decision != "accepted" or not decision.quality.get("applyEligible", False):
            unbound_ids.append(decision.ocrBlockId)
            seen.add(decision.ocrBlockId)
    return unbound_ids


def infer_text_containers(
    candidates: list[BindingCandidate],
    image: PngMetadata,
    primitive_document: VisualPrimitiveDocument,
) -> list[TextBindingContainer]:
    containers: list[TextBindingContainer] = []
    containers.extend(visual_primitive_containers(primitive_document))
    containers.extend(infer_badge_containers(candidates))
    containers.extend(infer_primary_button_containers(candidates, image))
    containers.extend(infer_shortcut_card_containers(candidates))
    containers.extend(infer_preview_containers(candidates))
    containers.extend(infer_legend_containers(candidates))
    containers.extend(infer_tip_containers(candidates))
    containers.extend(infer_bottom_nav_containers(candidates, image))
    return containers


def visual_primitive_containers(primitive_document: VisualPrimitiveDocument) -> list[TextBindingContainer]:
    containers: list[TextBindingContainer] = []
    for primitive in primitive_document.primitives:
        if primitive.kind == "region":
            role = f"fallback_{primitive.sourceRegionId or 'region'}"
            source = "fallback_region"
            confidence = 0.2
        else:
            role = visual_primitive_role(primitive.kind)
            source = "visual_primitive"
            confidence = primitive.confidence
        containers.append(
            TextBindingContainer(
                id=f"container_{primitive.id}",
                role=role,
                source=source,
                bbox=list(primitive.bbox),
                confidence=confidence,
                reason="m8_visual_primitive_context",
                primitiveId=primitive.id,
            )
        )
    return containers


def infer_badge_containers(candidates: list[BindingCandidate]) -> list[TextBindingContainer]:
    containers: list[TextBindingContainer] = []
    for candidate in candidates:
        if not is_badge_like_candidate(candidate):
            continue
        role = "status_badge" if candidate.region == "summary" and candidate.bbox[0] > 360 else "badge"
        reason = "pill_strategy_short_text_status" if role == "status_badge" else "pill_strategy_short_text"
        containers.append(
            TextBindingContainer(
                id=f"container_{role}_{safe_id(candidate.id)}",
                role=role,
                source="inferred_from_text_cluster",
                bbox=expand_bbox(candidate.bbox, 6, 4),
                confidence=0.86,
                reason=reason,
            )
        )
    return containers


def infer_primary_button_containers(candidates: list[BindingCandidate], image: PngMetadata) -> list[TextBindingContainer]:
    containers: list[TextBindingContainer] = []
    for candidate in candidates:
        if candidate.region not in {"summary", "card_grid"}:
            continue
        if candidate.bbox[3] < 32 or len(candidate.text.strip()) > 8:
            continue
        center_x = candidate.bbox[0] + candidate.bbox[2] / 2
        if abs(center_x - image.width / 2) > image.width * 0.18:
            continue
        containers.append(
            TextBindingContainer(
                id=f"container_primary_button_{safe_id(candidate.id)}",
                role="primary_button",
                source="inferred_from_text_cluster",
                bbox=clamp_bbox([48, candidate.bbox[1] - 22, image.width - 96, candidate.bbox[3] + 44], image),
                confidence=0.88,
                reason="single_centered_button_label",
            )
        )
    return containers


def infer_shortcut_card_containers(candidates: list[BindingCandidate]) -> list[TextBindingContainer]:
    card_candidates = [
        candidate
        for candidate in candidates
        if candidate.region == "card_grid" and candidate.bbox[3] >= 24 and len(candidate.text.strip()) <= 8
    ]
    containers: list[TextBindingContainer] = []
    for index, title in enumerate(card_candidates, start=1):
        siblings = [
            candidate
            for candidate in candidates
            if candidate.region == "card_grid"
            and candidate.bbox[1] > title.bbox[1]
            and 0 <= candidate.bbox[1] - title.bbox[1] <= 70
            and horizontal_overlap_ratio(candidate.bbox, title.bbox) >= 0.35
        ]
        if not siblings:
            continue
        bbox = union_bboxes([title.bbox, siblings[0].bbox])
        containers.append(
            TextBindingContainer(
                id=f"container_shortcut_card_{index:03d}",
                role="shortcut_card",
                source="inferred_from_text_cluster",
                bbox=expand_bbox(bbox, 70, 24),
                confidence=0.82,
                reason="title_subtitle_card_pair",
            )
        )
    return containers


def infer_preview_containers(candidates: list[BindingCandidate]) -> list[TextBindingContainer]:
    preview = [candidate for candidate in candidates if candidate.region == "preview_card"]
    if not preview:
        return []
    bbox = union_bboxes([candidate.bbox for candidate in preview])
    return [
        TextBindingContainer(
            id="container_preview_card_001",
            role="preview_card",
            source="inferred_from_text_cluster",
            bbox=expand_bbox(bbox, 28, 28),
            confidence=0.82,
            reason="preview_region_text_cluster",
        )
    ]


def infer_legend_containers(candidates: list[BindingCandidate]) -> list[TextBindingContainer]:
    legend_candidates = [
        candidate
        for candidate in candidates
        if candidate.region == "preview_card" and len(candidate.text.strip()) <= 4 and candidate.bbox[3] <= 32
    ]
    rows: list[list[BindingCandidate]] = []
    for candidate in legend_candidates:
        for row in rows:
            if abs(center_y(row[0].bbox) - center_y(candidate.bbox)) <= 8:
                row.append(candidate)
                break
        else:
            rows.append([candidate])

    containers: list[TextBindingContainer] = []
    for row_index, row in enumerate(rows, start=1):
        if len(row) < 2:
            continue
        row = sorted(row, key=lambda item: item.bbox[0])
        bbox = union_bboxes([candidate.bbox for candidate in row])
        containers.append(
            TextBindingContainer(
                id=f"container_legend_group_{row_index:03d}",
                role="legend_group",
                source="inferred_from_text_cluster",
                bbox=expand_bbox(bbox, 20, 10),
                confidence=0.84,
                reason="same_row_short_labels",
            )
        )
    return containers


def infer_tip_containers(candidates: list[BindingCandidate]) -> list[TextBindingContainer]:
    tip = [candidate for candidate in candidates if candidate.region == "tip_card"]
    if not tip:
        return []
    bbox = union_bboxes([candidate.bbox for candidate in tip])
    return [
        TextBindingContainer(
            id="container_tip_card_001",
            role="tip_card",
            source="inferred_from_text_cluster",
            bbox=expand_bbox(bbox, 26, 22),
            confidence=0.83,
            reason="tip_region_text_cluster",
        )
    ]


def infer_bottom_nav_containers(candidates: list[BindingCandidate], image: PngMetadata) -> list[TextBindingContainer]:
    nav = sorted(
        [
            candidate
            for candidate in candidates
            if candidate.region == "bottom_nav" or center_y(candidate.bbox) / max(1, image.height) >= 0.88
        ],
        key=lambda item: item.bbox[0],
    )
    if not nav:
        return []
    containers: list[TextBindingContainer] = [
        TextBindingContainer(
            id="container_bottom_nav_001",
            role="bottom_nav",
            source="inferred_from_text_cluster",
            bbox=clamp_bbox([0, min(item.bbox[1] for item in nav) - 42, image.width, image.height], image),
            confidence=0.78,
            reason="bottom_region_nav_labels",
        )
    ]
    for index, item in enumerate(nav, start=1):
        containers.append(
            TextBindingContainer(
                id=f"container_bottom_nav_item_{index:03d}",
                role="bottom_nav_item",
                source="inferred_from_text_cluster",
                bbox=clamp_bbox([item.bbox[0] - 36, item.bbox[1] - 46, item.bbox[2] + 72, item.bbox[3] + 58], image),
                confidence=0.84,
                reason="bottom_nav_short_label",
            )
        )
    return containers


def bind_candidates_to_containers(
    candidates: list[BindingCandidate],
    containers: list[TextBindingContainer],
    min_confidence: float,
) -> tuple[list[TextPrimitiveBinding], list[str]]:
    bindings: list[TextPrimitiveBinding] = []
    unbound: list[str] = []
    for candidate in candidates:
        scored = [
            (binding_score(candidate, container), container)
            for container in containers
            if container.source != "fallback_region"
        ]
        scored = [(score, container) for score, container in scored if score >= min_confidence]
        if not scored:
            unbound.append(candidate.id)
            continue
        scored.sort(key=lambda item: (item[0], -bbox_area(item[1].bbox)), reverse=True)
        score, container = scored[0]
        relationship = relationship_for(candidate, container)
        bindings.append(
            TextPrimitiveBinding(
                id=f"binding_{len(bindings) + 1:03d}",
                ocrBlockId=candidate.id,
                text=candidate.text,
                replacementElementId=candidate.replacement_element_id,
                containerId=container.id,
                containerRole=container.role,
                relationship=relationship,
                confidence=round(score, 3),
                reason=reason_for(candidate, container, relationship),
                bbox=list(candidate.bbox),
                containerBBox=list(container.bbox),
            )
        )
    return bindings, unbound


def binding_score(candidate: BindingCandidate, container: TextBindingContainer) -> float:
    if container.role.startswith("fallback_"):
        return 0.2
    center_inside = point_inside(center_x(candidate.bbox), center_y(candidate.bbox), container.bbox)
    overlap = overlap_ratio(candidate.bbox, container.bbox)
    if not center_inside and overlap < 0.55:
        return 0.0
    score = 0.38
    if center_inside:
        score += 0.22
    score += min(overlap, 1.0) * 0.16
    score += min(container.confidence, 1.0) * 0.12
    if role_matches_candidate(candidate, container):
        score += 0.22
    if container_too_large(candidate, container):
        score -= 0.18
    return max(0.0, min(0.99, score))


def role_matches_candidate(candidate: BindingCandidate, container: TextBindingContainer) -> bool:
    if container.role == "badge":
        return is_badge_like_candidate(candidate) and candidate.region == "hero"
    if container.role == "status_badge":
        return is_badge_like_candidate(candidate) and candidate.region == "summary"
    if container.role == "primary_button":
        return candidate.region in {"summary", "card_grid"} and candidate.bbox[3] >= 30
    if container.role == "shortcut_card":
        return candidate.region == "card_grid"
    if container.role == "preview_card":
        return candidate.region == "preview_card"
    if container.role in {"legend_group", "legend_item"}:
        return candidate.region == "preview_card" and len(candidate.text.strip()) <= 4
    if container.role == "tip_card":
        return candidate.region == "tip_card"
    if container.role == "bottom_nav_item":
        return candidate.region == "bottom_nav"
    if container.role == "bottom_nav":
        return candidate.region == "bottom_nav"
    return False


def is_badge_like_candidate(candidate: BindingCandidate) -> bool:
    if candidate.strategy_name == "pill_inner_background_sample":
        return True
    text = candidate.text.strip()
    return candidate.region in {"hero", "summary"} and len(text) <= 8 and candidate.bbox[2] <= 160 and candidate.bbox[3] <= 36


def relationship_for(candidate: BindingCandidate, container: TextBindingContainer) -> str:
    if container.role == "badge":
        return "badge_label"
    if container.role == "status_badge":
        return "status_label"
    if container.role == "primary_button":
        return "button_label"
    if container.role in {"legend_group", "legend_item"}:
        return "legend_label"
    if container.role == "bottom_nav_item":
        return "nav_label"
    if container.role in {"shortcut_card", "preview_card", "tip_card"}:
        return card_relationship(candidate, container)
    return "inside"


def card_relationship(candidate: BindingCandidate, container: TextBindingContainer) -> str:
    relative_y = center_y(candidate.bbox) - container.bbox[1]
    if candidate.bbox[3] >= 28 or relative_y < container.bbox[3] * 0.35:
        return "card_title"
    if candidate.bbox[3] <= 18:
        return "card_body"
    return "card_subtitle"


def reason_for(candidate: BindingCandidate, container: TextBindingContainer, relationship: str) -> str:
    if relationship == "button_label":
        return "text_center_inside_inferred_button"
    if relationship == "badge_label":
        return "pill_strategy_inside_badge"
    if relationship == "status_label":
        return "pill_strategy_inside_status_badge"
    if relationship == "legend_label":
        return "same_row_short_label_legend"
    if relationship == "nav_label":
        return "bottom_region_short_label"
    if relationship in {"card_title", "card_subtitle", "card_body"}:
        return f"{candidate.region}_text_inside_card_cluster"
    return "text_inside_container"


def apply_text_binding_metadata(dsl: dict[str, Any], document: TextPrimitiveBindingDocument) -> dict[str, Any]:
    if document.status != "completed":
        return deepcopy(dsl)
    next_dsl = deepcopy(dsl)
    meta = next_dsl.setdefault("meta", {})
    quality_flags = list(meta.get("qualityFlags") or [])
    if "m15_text_primitive_binding" not in quality_flags:
        quality_flags.append("m15_text_primitive_binding")
    meta["qualityFlags"] = quality_flags
    meta["textPrimitiveBindingCount"] = len(document.bindings)
    meta["textPrimitiveContainerCount"] = len(document.containers)
    meta["textPrimitiveUnboundCount"] = len(document.unboundTextIds)
    return next_dsl


def validate_text_binding_document(document: TextPrimitiveBindingDocument) -> list[str]:
    errors: list[str] = []
    if document.version != "0.1":
        errors.append("version must be 0.1")
    if not document.taskId:
        errors.append("taskId is required")
    container_ids = {container.id for container in document.containers}
    if len(container_ids) != len(document.containers):
        errors.append("container ids must be unique")
    binding_ids = {binding.id for binding in document.bindings}
    if len(binding_ids) != len(document.bindings):
        errors.append("binding ids must be unique")
    for container in document.containers:
        if len(container.bbox) != 4 or container.bbox[2] <= 0 or container.bbox[3] <= 0:
            errors.append(f"invalid container bbox: {container.id}")
        if container.role not in CONTAINER_ROLES and not container.role.startswith("fallback_"):
            errors.append(f"invalid container role: {container.role}")
    for binding in document.bindings:
        if binding.containerId not in container_ids:
            errors.append(f"binding references missing container: {binding.id}")
        if len(binding.bbox) != 4 or binding.bbox[2] <= 0 or binding.bbox[3] <= 0:
            errors.append(f"invalid binding bbox: {binding.id}")
    return errors


def summarize_roles(containers: list[TextBindingContainer]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for container in containers:
        summary[container.role] = summary.get(container.role, 0) + 1
    return summary


def summarize_relationships(bindings: list[TextPrimitiveBinding]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for binding in bindings:
        summary[binding.relationship] = summary.get(binding.relationship, 0) + 1
    return summary


def visual_primitive_role(kind: str) -> str:
    if kind == "button_background":
        return "primary_button"
    if kind == "card":
        return "shortcut_card"
    return "unknown"


def safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char == "_" else "_" for char in value.strip()) or "unknown"


def center_x(bbox: list[int]) -> float:
    return bbox[0] + bbox[2] / 2


def center_y(bbox: list[int]) -> float:
    return bbox[1] + bbox[3] / 2


def point_inside(x: float, y: float, bbox: list[int]) -> bool:
    return bbox[0] <= x <= bbox[0] + bbox[2] and bbox[1] <= y <= bbox[1] + bbox[3]


def overlap_ratio(inner: list[int], outer: list[int]) -> float:
    overlap = intersection_area(inner, outer)
    area = bbox_area(inner)
    if area <= 0:
        return 0
    return overlap / area


def horizontal_overlap_ratio(a: list[int], b: list[int]) -> float:
    left = max(a[0], b[0])
    right = min(a[0] + a[2], b[0] + b[2])
    overlap = max(0, right - left)
    return overlap / max(1, min(a[2], b[2]))


def intersection_area(a: list[int], b: list[int]) -> int:
    left = max(a[0], b[0])
    top = max(a[1], b[1])
    right = min(a[0] + a[2], b[0] + b[2])
    bottom = min(a[1] + a[3], b[1] + b[3])
    return max(0, right - left) * max(0, bottom - top)


def bbox_area(bbox: list[int]) -> int:
    return max(0, bbox[2]) * max(0, bbox[3])


def container_too_large(candidate: BindingCandidate, container: TextBindingContainer) -> bool:
    candidate_area = max(1, bbox_area(candidate.bbox))
    return bbox_area(container.bbox) / candidate_area > 80


def union_bboxes(bboxes: list[list[int]]) -> list[int]:
    left = min(bbox[0] for bbox in bboxes)
    top = min(bbox[1] for bbox in bboxes)
    right = max(bbox[0] + bbox[2] for bbox in bboxes)
    bottom = max(bbox[1] + bbox[3] for bbox in bboxes)
    return [left, top, right - left, bottom - top]


def expand_bbox(bbox: list[int], x_padding: int, y_padding: int) -> list[int]:
    return [
        bbox[0] - x_padding,
        bbox[1] - y_padding,
        bbox[2] + x_padding * 2,
        bbox[3] + y_padding * 2,
    ]


def clamp_bbox(bbox: list[int], image: PngMetadata) -> list[int]:
    x = max(0, bbox[0])
    y = max(0, bbox[1])
    right = min(image.width, bbox[0] + bbox[2])
    bottom = min(image.height, bbox[1] + bbox[3])
    return [x, y, max(1, right - x), max(1, bottom - y)]
