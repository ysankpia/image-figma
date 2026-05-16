from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .component_annotation import ComponentAnnotationDocument, ComponentAnnotationItem, index_dsl_elements
from .component_structure import ComponentStructureDocument, ComponentStructureGroup, ComponentStructureItem
from .config import Settings
from .png_tools import (
    PngMetadata,
    PngPixels,
    UnsupportedPngCropError,
    decode_png_pixels,
    sample_region_background,
)
from .text_binding import TextPrimitiveBinding, TextPrimitiveBindingDocument
from .text_replacement import TextReplacementDecision, TextReplacementDocument


LayerSeparationStatus = Literal["completed", "failed", "skipped"]
CandidateStatus = Literal["candidate", "blocked", "not_applicable"]
CandidateRisk = Literal["low", "medium", "high"]

CANDIDATE_STATUSES = {"candidate", "blocked", "not_applicable"}
STRATEGIES = {
    "shape_background_plus_editable_text",
    "image_slice_without_text",
    "image_slice_with_simple_fill_candidate",
    "image_slice_with_repair_required",
    "image_slice_with_embedded_text",
    "fallback_context_only",
    "blocked",
}
BACKGROUND_KINDS = {"solid", "low_complexity", "complex", "unknown"}
FILL_MODES = {"solid_color_fill", "local_edge_fill", "none"}
TEXT_SEPARATION_MODES = {
    "editable_text_over_fill",
    "editable_text_over_repaired_background",
    "embedded_text",
    "no_text",
    "not_safe_to_separate",
}
RISKS = {"low", "medium", "high"}

SHAPE_TEXT_ROLES = {
    "badge",
    "status_badge",
    "primary_button",
    "outline_button",
    "summary_stat_card",
    "bottom_nav_item",
}

SLICE_TEXT_ROLES = {
    "activity_card",
    "shortcut_card",
    "preview_card",
    "tip_card",
    "hero_profile",
}

FALLBACK_ELEMENT_IDS = {
    "fallback_region_header",
    "fallback_region_content",
    "fallback_region_bottom",
    "fallback_full_image",
}


@dataclass
class LayerSeparationWarning:
    code: str
    message: str
    componentId: str | None = None
    dslElementId: str | None = None
    bindingId: str | None = None


@dataclass
class LayerSeparationFallbackContext:
    dslElementId: str
    strategy: str
    groupIds: list[str]
    reason: str


@dataclass
class LayerSeparationCandidate:
    id: str
    componentId: str
    componentRole: str
    groupIds: list[str]
    annotationIds: list[str]
    bindingIds: list[str]
    strategy: str
    status: CandidateStatus
    bbox: list[int]
    textElementIds: list[str]
    coverElementIds: list[str]
    candidateTextElementIds: list[str]
    background: dict[str, Any]
    fillCandidate: dict[str, Any]
    textSeparation: dict[str, Any]
    risk: CandidateRisk
    reasons: list[str]


@dataclass
class LayerSeparationDocument:
    version: str
    taskId: str
    status: LayerSeparationStatus
    imageSize: dict[str, int]
    candidates: list[LayerSeparationCandidate]
    fallbackContexts: list[LayerSeparationFallbackContext]
    blockedComponentIds: list[str]
    warnings: list[LayerSeparationWarning]
    meta: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BackgroundEvidence:
    kind: str
    source: str
    color: str | None
    mean_rgb: list[int] | None
    max_channel_delta: int | None
    confidence: float
    bbox: list[int] | None


def build_layer_separation_document(
    *,
    task_id: str,
    image: PngMetadata,
    png_data: bytes,
    replacement_document: TextReplacementDocument,
    binding_document: TextPrimitiveBindingDocument,
    structure_document: ComponentStructureDocument,
    annotation_document: ComponentAnnotationDocument,
    dsl: dict[str, Any],
    settings: Settings,
) -> LayerSeparationDocument:
    if not settings.layer_separation_enabled:
        return build_skipped_layer_separation_document(
            task_id=task_id,
            image=image,
            code="layer_separation_disabled",
            message="Layer separation is disabled.",
        )
    if binding_document.status != "completed":
        return build_skipped_layer_separation_document(
            task_id=task_id,
            image=image,
            code="text_binding_not_completed",
            message="Layer separation skipped because text binding did not complete.",
        )
    if structure_document.status != "completed":
        return build_skipped_layer_separation_document(
            task_id=task_id,
            image=image,
            code="component_structure_not_completed",
            message="Layer separation skipped because component structure did not complete.",
        )
    if annotation_document.status != "completed":
        return build_skipped_layer_separation_document(
            task_id=task_id,
            image=image,
            code="component_annotation_not_completed",
            message="Layer separation skipped because component annotation did not complete.",
        )

    elements = index_dsl_elements(dsl)
    bindings_by_id = {binding.id: binding for binding in binding_document.bindings}
    decisions_by_id = {decision.ocrBlockId: decision for decision in replacement_document.decisions}
    annotations_by_component = group_annotations_by_component(annotation_document.annotations)
    group_ids_by_component = group_ids_by_component_id(structure_document.groups)
    pixels, pixel_warning = try_decode_pixels(png_data)

    candidates: list[LayerSeparationCandidate] = []
    warnings: list[LayerSeparationWarning] = []
    if pixel_warning is not None:
        warnings.append(pixel_warning)
    blocked_ids: list[str] = []

    for index, component in enumerate(structure_document.components, start=1):
        component_annotations = annotations_by_component.get(component.id, [])
        candidate, candidate_warnings = build_candidate_for_component(
            component=component,
            index=index,
            annotations=component_annotations,
            group_ids=group_ids_by_component.get(component.id, []),
            bindings_by_id=bindings_by_id,
            decisions_by_id=decisions_by_id,
            elements=elements,
            pixels=pixels,
            image=image,
            settings=settings,
        )
        candidates.append(candidate)
        warnings.extend(candidate_warnings)
        if candidate.status == "blocked":
            blocked_ids.append(component.id)

    fallback_contexts = build_fallback_contexts(elements, annotation_document)
    document = LayerSeparationDocument(
        version="0.1",
        taskId=task_id,
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        candidates=candidates,
        fallbackContexts=fallback_contexts,
        blockedComponentIds=blocked_ids,
        warnings=warnings,
        meta=build_meta(candidates, fallback_contexts, warnings),
    )
    validation_errors = validate_layer_separation_document(
        document=document,
        binding_document=binding_document,
        structure_document=structure_document,
        annotation_document=annotation_document,
        dsl=dsl,
        image=image,
    )
    if validation_errors:
        return build_failed_layer_separation_document(
            task_id=task_id,
            image=image,
            code="LAYER_SEPARATION_VALIDATION_FAILED",
            message="Layer separation validation failed.",
            warnings=[
                LayerSeparationWarning(
                    code="LAYER_SEPARATION_VALIDATION_ERROR",
                    message=error,
                )
                for error in validation_errors
            ],
        )
    return document


def build_candidate_for_component(
    *,
    component: ComponentStructureItem,
    index: int,
    annotations: list[ComponentAnnotationItem],
    group_ids: list[str],
    bindings_by_id: dict[str, TextPrimitiveBinding],
    decisions_by_id: dict[str, TextReplacementDecision],
    elements: dict[str, dict[str, Any]],
    pixels: PngPixels | None,
    image: PngMetadata,
    settings: Settings,
) -> tuple[LayerSeparationCandidate, list[LayerSeparationWarning]]:
    warnings: list[LayerSeparationWarning] = []
    reasons = ["component_annotation_found"] if annotations else ["missing_component_annotation"]
    if component.confidence >= settings.layer_separation_min_confidence:
        reasons.append("component_confidence_ok")
    annotation_ids = [annotation.id for annotation in annotations]
    text_ids = sorted(
        {
            annotation.dslElementId
            for annotation in annotations
            if annotation.elementRole == "visible_text_replacement" or annotation.dslElementId.startswith("visible_text_")
        }
    )
    cover_ids = sorted(
        {
            annotation.dslElementId
            for annotation in annotations
            if annotation.elementRole == "text_replacement_cover" or annotation.dslElementId.startswith("cover_")
        }
    )
    candidate_text_ids = sorted(
        {
            annotation.dslElementId
            for annotation in annotations
            if annotation.elementRole == "candidate_text" or annotation.dslElementId.startswith("text_")
        }
    )
    if annotations:
        reasons.append("component_has_annotated_text")
    if text_ids:
        reasons.append("component_has_visible_replacement")
    if cover_ids:
        reasons.append("component_has_cover")

    binding_ids = sorted({annotation.bindingId for annotation in annotations if annotation.bindingId in bindings_by_id})
    decisions = [
        decisions_by_id[binding.ocrBlockId]
        for binding_id in binding_ids
        if (binding := bindings_by_id.get(binding_id)) is not None and binding.ocrBlockId in decisions_by_id
    ]
    evidence, evidence_warnings = background_evidence_for_component(
        component=component,
        decisions=decisions,
        cover_ids=cover_ids,
        elements=elements,
        pixels=pixels,
        settings=settings,
    )
    warnings.extend(evidence_warnings)
    if evidence.kind == "solid":
        reasons.append("solid_background_under_text")
    elif evidence.kind == "low_complexity":
        reasons.append("low_complexity_background_under_text")
    elif evidence.kind == "complex":
        reasons.append("complex_background_under_text")
    else:
        reasons.append("missing_text_background_sample")

    fill_targets = fill_target_bboxes(
        decisions=decisions,
        cover_ids=cover_ids,
        elements=elements,
        image=image,
    )
    simple_fill_ok = simple_fill_candidate_is_safe(
        component=component,
        role=component.role,
        evidence=evidence,
        decisions=decisions,
        fill_targets=fill_targets,
        image=image,
        settings=settings,
    )
    if simple_fill_ok:
        reasons.extend(["simple_fill_candidate", "editable_text_should_stay_separate"])

    block_reasons = blocking_reasons(
        component=component,
        role=component.role,
        fill_targets=fill_targets,
        image=image,
        settings=settings,
    )
    if block_reasons:
        reasons.extend(block_reasons)

    strategy, status, text_mode, risk = classify_component_strategy(
        role=component.role,
        has_text=bool(annotations),
        simple_fill_ok=simple_fill_ok,
        evidence=evidence,
        block_reasons=block_reasons,
    )
    if strategy == "image_slice_with_repair_required":
        reasons.append("repair_required_before_slice")
    elif strategy == "image_slice_with_embedded_text":
        reasons.append("embedded_text_not_safe_to_separate")
    elif strategy == "image_slice_without_text":
        reasons.append("image_region_has_no_text")
    candidate_bbox = normalize_bbox(component.bbox, image) or [0, 0, 1, 1]

    return (
        LayerSeparationCandidate(
            id=f"layer_sep_{index:03d}",
            componentId=component.id,
            componentRole=component.role,
            groupIds=list(group_ids),
            annotationIds=annotation_ids,
            bindingIds=binding_ids,
            strategy=strategy,
            status=status,
            bbox=candidate_bbox,
            textElementIds=text_ids,
            coverElementIds=cover_ids,
            candidateTextElementIds=candidate_text_ids,
            background=background_to_contract(evidence),
            fillCandidate=fill_candidate_contract(simple_fill_ok, evidence, fill_targets),
            textSeparation={
                "mode": text_mode,
                "confidence": text_separation_confidence(status, simple_fill_ok, evidence, component.confidence),
            },
            risk=risk,
            reasons=unique_preserve_order(reasons),
        ),
        warnings,
    )


def background_evidence_for_component(
    *,
    component: ComponentStructureItem,
    decisions: list[TextReplacementDecision],
    cover_ids: list[str],
    elements: dict[str, dict[str, Any]],
    pixels: PngPixels | None,
    settings: Settings,
) -> tuple[BackgroundEvidence, list[LayerSeparationWarning]]:
    warnings: list[LayerSeparationWarning] = []
    accepted = [
        decision
        for decision in decisions
        if decision.decision == "accepted" and decision.quality.get("applyEligible", False) and decision.background is not None
    ]
    if accepted:
        best = min(
            accepted,
            key=lambda decision: (
                int(decision.background.get("maxChannelDelta", 999)) if decision.background else 999,
                -float(decision.background.get("confidence", 0)) if decision.background else 0,
            ),
        )
        background = best.background or {}
        max_delta = int(background.get("maxChannelDelta", 999))
        return (
            BackgroundEvidence(
                kind=background_kind(max_delta, float(background.get("confidence", 0)), settings),
                source="m14_text_replacement_background",
                color=str(background.get("color") or ""),
                mean_rgb=coerce_rgb(background.get("meanRgb")),
                max_channel_delta=max_delta,
                confidence=round(float(background.get("confidence", 0)), 3),
                bbox=list(best.expandedBBox or best.bbox),
            ),
            warnings,
        )

    cover_evidence = cover_background_evidence(cover_ids, elements)
    if cover_evidence is not None:
        return cover_evidence, warnings

    if pixels is not None:
        try:
            sample = sample_region_background(pixels, component.bbox, settings.layer_separation_simple_fill_tolerance)
            return (
                BackgroundEvidence(
                    kind=background_kind(sample.max_channel_delta, sample.confidence, settings),
                    source="png_tools_component_bbox_edge_sample",
                    color=sample.color,
                    mean_rgb=sample.mean_rgb,
                    max_channel_delta=sample.max_channel_delta,
                    confidence=sample.confidence,
                    bbox=sample.bbox,
                ),
                warnings,
            )
        except UnsupportedPngCropError:
            warnings.append(
                LayerSeparationWarning(
                    code="missing_text_background_sample",
                    message="PNG local background sampling failed for component.",
                    componentId=component.id,
                )
            )

    return (
        BackgroundEvidence(
            kind="unknown",
            source="missing_text_background_sample",
            color=None,
            mean_rgb=None,
            max_channel_delta=None,
            confidence=0,
            bbox=None,
        ),
        warnings,
    )


def cover_background_evidence(
    cover_ids: list[str],
    elements: dict[str, dict[str, Any]],
) -> BackgroundEvidence | None:
    for cover_id in cover_ids:
        element = elements.get(cover_id)
        if element is None:
            continue
        fill = (element.get("style") or {}).get("fill") if isinstance(element.get("style"), dict) else None
        layout = element.get("layout") if isinstance(element.get("layout"), dict) else {}
        if not isinstance(fill, str) or not fill.startswith("#"):
            continue
        bbox = [
            round(float(layout.get("x", 0) or 0)),
            round(float(layout.get("y", 0) or 0)),
            round(float(layout.get("width", 0) or 0)),
            round(float(layout.get("height", 0) or 0)),
        ]
        return BackgroundEvidence(
            kind="solid",
            source="text_replacement_cover_fill",
            color=fill,
            mean_rgb=hex_to_rgb(fill),
            max_channel_delta=0,
            confidence=0.82,
            bbox=bbox,
        )
    return None


def fill_target_bboxes(
    *,
    decisions: list[TextReplacementDecision],
    cover_ids: list[str],
    elements: dict[str, dict[str, Any]],
    image: PngMetadata,
) -> list[list[int]]:
    targets: list[list[int]] = []
    for decision in decisions:
        bbox = decision.expandedBBox or decision.bbox
        normalized = normalize_bbox(bbox, image)
        if normalized is not None:
            targets.append(normalized)
    for cover_id in cover_ids:
        element = elements.get(cover_id)
        if element is None:
            continue
        layout = element.get("layout")
        if not isinstance(layout, dict):
            continue
        normalized = normalize_bbox(
            [
                layout.get("x", 0),
                layout.get("y", 0),
                layout.get("width", 0),
                layout.get("height", 0),
            ],
            image,
        )
        if normalized is not None:
            targets.append(normalized)
    return unique_bboxes(targets)


def simple_fill_candidate_is_safe(
    *,
    component: ComponentStructureItem,
    role: str,
    evidence: BackgroundEvidence,
    decisions: list[TextReplacementDecision],
    fill_targets: list[list[int]],
    image: PngMetadata,
    settings: Settings,
) -> bool:
    if component.confidence < settings.layer_separation_min_confidence:
        return False
    if not fill_targets:
        return False
    if evidence.kind not in {"solid", "low_complexity"}:
        return False
    if evidence.max_channel_delta is None or evidence.max_channel_delta > settings.layer_separation_simple_fill_tolerance:
        return False
    if evidence.confidence < 0.65:
        return False
    if not any(
        decision.decision == "accepted" and decision.quality.get("applyEligible", False) and decision.background is not None
        for decision in decisions
    ) and evidence.source != "text_replacement_cover_fill":
        return False
    max_fill_area = image.width * image.height * 0.05
    for target in fill_targets:
        if not bbox_in_bounds(target, image) or target[2] * target[3] > max_fill_area:
            return False
    if role == "bottom_nav_item" and bottom_nav_fill_invades_icon(fill_targets, component.bbox):
        return False
    return True


def blocking_reasons(
    *,
    component: ComponentStructureItem,
    role: str,
    fill_targets: list[list[int]],
    image: PngMetadata,
    settings: Settings,
) -> list[str]:
    reasons: list[str] = []
    if component.confidence < settings.layer_separation_min_confidence:
        reasons.append("component_confidence_low")
    if not bbox_in_bounds(component.bbox, image):
        reasons.append("component_bbox_too_small")
    elif component.bbox[2] * component.bbox[3] <= 16:
        reasons.append("component_bbox_too_small")
    elif component.bbox[2] * component.bbox[3] / max(1, image.width * image.height) > settings.layer_separation_max_component_area_ratio:
        reasons.append("component_bbox_too_large")
    if fill_targets and role == "bottom_nav_item" and bottom_nav_fill_invades_icon(fill_targets, component.bbox):
        reasons.append("near_bottom_nav_icon")
    if fill_targets and min(target[1] for target in fill_targets) < 44:
        reasons.append("near_status_bar")
    return reasons


def classify_component_strategy(
    *,
    role: str,
    has_text: bool,
    simple_fill_ok: bool,
    evidence: BackgroundEvidence,
    block_reasons: list[str],
) -> tuple[str, CandidateStatus, str, CandidateRisk]:
    if block_reasons:
        return "blocked", "blocked", "not_safe_to_separate", "high"
    if not has_text:
        return "image_slice_without_text", "not_applicable", "no_text", "low"
    if simple_fill_ok and role in SHAPE_TEXT_ROLES:
        return "shape_background_plus_editable_text", "candidate", "editable_text_over_fill", "low"
    if simple_fill_ok:
        return "image_slice_with_simple_fill_candidate", "candidate", "editable_text_over_fill", "low"
    if evidence.kind in {"complex", "unknown"} and role in SLICE_TEXT_ROLES | {"legend_group"}:
        return "image_slice_with_repair_required", "candidate", "editable_text_over_repaired_background", "medium"
    return "image_slice_with_embedded_text", "candidate", "embedded_text", "medium"


def build_fallback_contexts(
    elements: dict[str, dict[str, Any]],
    annotation_document: ComponentAnnotationDocument,
) -> list[LayerSeparationFallbackContext]:
    page_group_ids = [hint.groupId for hint in annotation_document.groupHints if hint.role == "page_structure"]
    contexts: list[LayerSeparationFallbackContext] = []
    for element_id in sorted(elements):
        element = elements[element_id]
        if not is_fallback_element(element_id, element):
            continue
        contexts.append(
            LayerSeparationFallbackContext(
                dslElementId=element_id,
                strategy="fallback_context_only",
                groupIds=page_group_ids,
                reason="fallback_context_only",
            )
        )
    return contexts


def apply_layer_separation_metadata(
    dsl: dict[str, Any],
    document: LayerSeparationDocument,
) -> dict[str, Any]:
    if document.status != "completed":
        return deepcopy(dsl)
    next_dsl = deepcopy(dsl)
    meta = next_dsl.setdefault("meta", {})
    quality_flags = list(meta.get("qualityFlags") or [])
    if "m18_layer_separation_candidates" not in quality_flags:
        quality_flags.append("m18_layer_separation_candidates")
    meta["qualityFlags"] = quality_flags
    meta["layerSeparationCandidateCount"] = len(document.candidates)
    meta["layerSeparationFillCandidateCount"] = int(document.meta.get("fillCandidateCount", 0))
    meta["layerSeparationRepairRequiredCount"] = int(document.meta.get("repairRequiredCount", 0))
    meta["layerSeparationEmbeddedTextCount"] = int(document.meta.get("embeddedTextCount", 0))
    meta["layerSeparationBlockedCount"] = int(document.meta.get("blockedCount", 0))
    return next_dsl


def validate_layer_separation_document(
    *,
    document: LayerSeparationDocument,
    binding_document: TextPrimitiveBindingDocument,
    structure_document: ComponentStructureDocument,
    annotation_document: ComponentAnnotationDocument,
    dsl: dict[str, Any],
    image: PngMetadata,
) -> list[str]:
    errors: list[str] = []
    if document.version != "0.1":
        errors.append("version must be 0.1")
    if not document.taskId:
        errors.append("taskId is required")
    elements = index_dsl_elements(dsl)
    component_ids = {component.id for component in structure_document.components}
    group_ids = {group.id for group in structure_document.groups}
    annotation_ids = {annotation.id for annotation in annotation_document.annotations}
    binding_ids = {binding.id for binding in binding_document.bindings}
    candidate_ids = {candidate.id for candidate in document.candidates}
    if len(candidate_ids) != len(document.candidates):
        errors.append("candidate ids must be unique")

    for candidate in document.candidates:
        if candidate.componentId not in component_ids:
            errors.append(f"candidate references missing component: {candidate.id}")
        for group_id in candidate.groupIds:
            if group_id not in group_ids:
                errors.append(f"candidate references missing group: {candidate.id}")
        for annotation_id in candidate.annotationIds:
            if annotation_id not in annotation_ids:
                errors.append(f"candidate references missing annotation: {candidate.id}")
        for binding_id in candidate.bindingIds:
            if binding_id not in binding_ids:
                errors.append(f"candidate references missing binding: {candidate.id}")
        for element_id in [*candidate.textElementIds, *candidate.coverElementIds, *candidate.candidateTextElementIds]:
            if element_id not in elements:
                errors.append(f"candidate references missing DSL element: {candidate.id}")
        if not bbox_in_bounds(candidate.bbox, image):
            errors.append(f"candidate bbox is out of bounds: {candidate.id}")
        if candidate.strategy not in STRATEGIES:
            errors.append(f"invalid candidate strategy: {candidate.id}")
        if candidate.status not in CANDIDATE_STATUSES:
            errors.append(f"invalid candidate status: {candidate.id}")
        if candidate.risk not in RISKS:
            errors.append(f"invalid candidate risk: {candidate.id}")
        if candidate.background.get("kind") not in BACKGROUND_KINDS:
            errors.append(f"invalid background kind: {candidate.id}")
        if candidate.fillCandidate.get("mode") not in FILL_MODES:
            errors.append(f"invalid fill mode: {candidate.id}")
        if candidate.textSeparation.get("mode") not in TEXT_SEPARATION_MODES:
            errors.append(f"invalid text separation mode: {candidate.id}")
        for target in candidate.fillCandidate.get("targetBBoxes") or []:
            if not bbox_in_bounds(target, image):
                errors.append(f"fill target bbox is out of bounds: {candidate.id}")

    for context in document.fallbackContexts:
        element = elements.get(context.dslElementId)
        if element is None or not is_fallback_element(context.dslElementId, element):
            errors.append(f"fallback context references missing fallback element: {context.dslElementId}")

    if document.meta.get("candidateCount") != len(document.candidates):
        errors.append("meta candidateCount must match candidates length")
    if document.meta.get("fillCandidateCount") != sum(1 for candidate in document.candidates if candidate.fillCandidate.get("enabled")):
        errors.append("meta fillCandidateCount must match fill candidate count")
    if document.meta.get("repairRequiredCount") != sum(1 for candidate in document.candidates if candidate.strategy == "image_slice_with_repair_required"):
        errors.append("meta repairRequiredCount must match repair required count")
    if document.meta.get("embeddedTextCount") != sum(1 for candidate in document.candidates if candidate.strategy == "image_slice_with_embedded_text"):
        errors.append("meta embeddedTextCount must match embedded text count")
    if document.meta.get("blockedCount") != sum(1 for candidate in document.candidates if candidate.status == "blocked"):
        errors.append("meta blockedCount must match blocked candidates count")
    if document.meta.get("fallbackContextCount") != len(document.fallbackContexts):
        errors.append("meta fallbackContextCount must match fallbackContexts length")
    if document.meta.get("strategySummary") != summarize_strategies(document.candidates):
        errors.append("meta strategySummary must match candidates")
    if document.meta.get("riskSummary") != summarize_risks(document.candidates):
        errors.append("meta riskSummary must match candidates")
    return errors


def build_skipped_layer_separation_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
) -> LayerSeparationDocument:
    return LayerSeparationDocument(
        version="0.1",
        taskId=task_id,
        status="skipped",
        imageSize={"width": image.width, "height": image.height},
        candidates=[],
        fallbackContexts=[],
        blockedComponentIds=[],
        warnings=[LayerSeparationWarning(code=code, message=message)],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def build_failed_layer_separation_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
    warnings: list[LayerSeparationWarning] | None = None,
) -> LayerSeparationDocument:
    return LayerSeparationDocument(
        version="0.1",
        taskId=task_id,
        status="failed",
        imageSize={"width": image.width, "height": image.height},
        candidates=[],
        fallbackContexts=[],
        blockedComponentIds=[],
        warnings=warnings or [LayerSeparationWarning(code=code, message=message)],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def build_meta(
    candidates: list[LayerSeparationCandidate],
    fallback_contexts: list[LayerSeparationFallbackContext],
    warnings: list[LayerSeparationWarning],
) -> dict[str, Any]:
    del warnings
    return {
        "notes": "component_aware_layer_separation_candidates",
        "candidateCount": len(candidates),
        "fillCandidateCount": sum(1 for candidate in candidates if candidate.fillCandidate.get("enabled")),
        "repairRequiredCount": sum(1 for candidate in candidates if candidate.strategy == "image_slice_with_repair_required"),
        "embeddedTextCount": sum(1 for candidate in candidates if candidate.strategy == "image_slice_with_embedded_text"),
        "blockedCount": sum(1 for candidate in candidates if candidate.status == "blocked"),
        "fallbackContextCount": len(fallback_contexts),
        "strategySummary": summarize_strategies(candidates),
        "riskSummary": summarize_risks(candidates),
    }


def empty_meta() -> dict[str, Any]:
    return {
        "notes": "component_aware_layer_separation_candidates",
        "candidateCount": 0,
        "fillCandidateCount": 0,
        "repairRequiredCount": 0,
        "embeddedTextCount": 0,
        "blockedCount": 0,
        "fallbackContextCount": 0,
        "strategySummary": {},
        "riskSummary": {},
    }


def background_to_contract(evidence: BackgroundEvidence) -> dict[str, Any]:
    return {
        "kind": evidence.kind,
        "source": evidence.source,
        "color": evidence.color,
        "meanRgb": evidence.mean_rgb,
        "maxChannelDelta": evidence.max_channel_delta,
        "confidence": round(evidence.confidence, 3),
    }


def fill_candidate_contract(
    enabled: bool,
    evidence: BackgroundEvidence,
    fill_targets: list[list[int]],
) -> dict[str, Any]:
    if not enabled:
        return {
            "enabled": False,
            "mode": "none",
            "targetBBoxes": [],
            "color": None,
            "confidence": 0,
            "source": "none",
        }
    return {
        "enabled": True,
        "mode": "solid_color_fill",
        "targetBBoxes": fill_targets,
        "color": evidence.color,
        "confidence": round(min(0.99, evidence.confidence + 0.04), 3),
        "source": "m14_expanded_bbox" if evidence.source == "m14_text_replacement_background" else evidence.source,
    }


def text_separation_confidence(status: str, simple_fill_ok: bool, evidence: BackgroundEvidence, component_confidence: float) -> float:
    if status == "blocked":
        return 0.0
    if simple_fill_ok:
        return round(min(0.99, (evidence.confidence + component_confidence) / 2), 3)
    if evidence.kind == "complex":
        return 0.62
    if evidence.kind == "unknown":
        return 0.45
    return 0.7


def try_decode_pixels(png_data: bytes) -> tuple[PngPixels | None, LayerSeparationWarning | None]:
    try:
        return decode_png_pixels(png_data), None
    except UnsupportedPngCropError as error:
        return None, LayerSeparationWarning(code="png_pixel_decode_unsupported", message=str(error))


def group_annotations_by_component(
    annotations: list[ComponentAnnotationItem],
) -> dict[str, list[ComponentAnnotationItem]]:
    grouped: dict[str, list[ComponentAnnotationItem]] = {}
    for annotation in annotations:
        grouped.setdefault(annotation.componentId, []).append(annotation)
    return grouped


def group_ids_by_component_id(groups: list[ComponentStructureGroup]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for group in groups:
        for component_id in group.componentIds:
            grouped.setdefault(component_id, []).append(group.id)
    return grouped


def background_kind(max_delta: int, confidence: float, settings: Settings) -> str:
    if max_delta <= settings.layer_separation_simple_fill_tolerance and confidence >= 0.75:
        return "solid"
    if max_delta <= settings.layer_separation_simple_fill_tolerance and confidence >= 0.65:
        return "low_complexity"
    return "complex"


def coerce_rgb(value: Any) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 3:
        return None
    try:
        return [max(0, min(255, round(float(item)))) for item in value]
    except (TypeError, ValueError):
        return None


def hex_to_rgb(value: str) -> list[int] | None:
    normalized = value.strip().lstrip("#")
    if len(normalized) != 6:
        return None
    try:
        return [int(normalized[index : index + 2], 16) for index in (0, 2, 4)]
    except ValueError:
        return None


def normalize_bbox(bbox: list[Any], image: PngMetadata) -> list[int] | None:
    if len(bbox) != 4:
        return None
    try:
        x, y, width, height = [round(float(value)) for value in bbox]
    except (TypeError, ValueError):
        return None
    x1 = max(0, min(image.width, x))
    y1 = max(0, min(image.height, y))
    x2 = max(0, min(image.width, x + width))
    y2 = max(0, min(image.height, y + height))
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2 - x1, y2 - y1]


def bbox_in_bounds(bbox: list[Any], image: PngMetadata) -> bool:
    if len(bbox) != 4:
        return False
    try:
        x, y, width, height = [float(value) for value in bbox]
    except (TypeError, ValueError):
        return False
    return width > 0 and height > 0 and x >= 0 and y >= 0 and x + width <= image.width and y + height <= image.height


def bottom_nav_fill_invades_icon(fill_targets: list[list[int]], component_bbox: list[int]) -> bool:
    if len(component_bbox) != 4:
        return True
    component_icon_boundary = component_bbox[1] + component_bbox[3] * 0.42
    return any(target[1] < component_icon_boundary for target in fill_targets)


def is_fallback_element(element_id: str, element: dict[str, Any]) -> bool:
    role = str(element.get("role") or "")
    return element_id in FALLBACK_ELEMENT_IDS or element_id.startswith("fallback_region_") or role == "fallback_region"


def unique_bboxes(bboxes: list[list[int]]) -> list[list[int]]:
    result: list[list[int]] = []
    seen: set[tuple[int, int, int, int]] = set()
    for bbox in bboxes:
        key = tuple(bbox)
        if key in seen:
            continue
        result.append(bbox)
        seen.add(key)
    return result


def unique_preserve_order(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result


def summarize_strategies(candidates: list[LayerSeparationCandidate]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for candidate in candidates:
        summary[candidate.strategy] = summary.get(candidate.strategy, 0) + 1
    return summary


def summarize_risks(candidates: list[LayerSeparationCandidate]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for candidate in candidates:
        summary[candidate.risk] = summary.get(candidate.risk, 0) + 1
    return summary
