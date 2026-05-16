from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .component_structure import ComponentStructureDocument, ComponentStructureGroup, ComponentStructureItem
from .config import Settings
from .ocr import OCRDocument
from .png_tools import PngMetadata
from .text_binding import TextPrimitiveBinding, TextPrimitiveBindingDocument
from .text_replacement import TextReplacementDocument


AnnotationStatus = Literal["completed", "failed", "skipped"]
GroupHintStatus = Literal["ready_for_future_grouping", "partial", "blocked"]


ROLE_LABELS = {
    "page_header": "Page Header",
    "hero_profile": "Hero Profile",
    "badge": "Badge",
    "status_badge": "Status Badge",
    "activity_card": "Activity Card",
    "summary_stat_card": "Summary Stat Card",
    "primary_button": "Primary Button",
    "outline_button": "Outline Button",
    "shortcut_card": "Shortcut Card",
    "preview_card": "Preview Card",
    "legend_group": "Legend Group",
    "tip_card": "Tip Card",
    "bottom_nav": "Bottom Nav",
    "bottom_nav_item": "Bottom Nav Item",
    "unknown": "Unknown",
}

FALLBACK_NAMES = {
    "fallback_region_header": "Fallback / Header",
    "fallback_region_content": "Fallback / Content",
    "fallback_region_bottom": "Fallback / Bottom",
    "fallback_full_image": "Fallback / Full Image",
}


@dataclass
class ComponentAnnotationWarning:
    code: str
    message: str
    dslElementId: str | None = None
    componentId: str | None = None
    bindingId: str | None = None


@dataclass
class ComponentAnnotationItem:
    id: str
    dslElementId: str
    elementType: str
    elementRole: str
    componentId: str
    componentRole: str
    groupIds: list[str]
    relationship: str
    bindingId: str
    ocrBlockId: str
    confidence: float
    reason: str
    layerName: str


@dataclass
class ComponentGroupHint:
    id: str
    groupId: str
    role: str
    componentIds: list[str]
    dslElementIds: list[str]
    status: GroupHintStatus
    reason: str


@dataclass
class ComponentAnnotationDocument:
    version: str
    taskId: str
    status: AnnotationStatus
    imageSize: dict[str, int]
    annotations: list[ComponentAnnotationItem]
    groupHints: list[ComponentGroupHint]
    unannotatedElementIds: list[str]
    unresolvedComponentIds: list[str]
    warnings: list[ComponentAnnotationWarning]
    meta: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_component_annotation_document(
    *,
    task_id: str,
    image: PngMetadata,
    ocr_document: OCRDocument,
    replacement_document: TextReplacementDocument,
    binding_document: TextPrimitiveBindingDocument,
    structure_document: ComponentStructureDocument,
    dsl: dict[str, Any],
    settings: Settings,
) -> ComponentAnnotationDocument:
    del ocr_document, replacement_document
    if not settings.component_annotation_enabled:
        return build_skipped_component_annotation_document(
            task_id=task_id,
            image=image,
            code="component_annotation_disabled",
            message="Component annotation is disabled.",
        )
    if binding_document.status != "completed":
        return build_skipped_component_annotation_document(
            task_id=task_id,
            image=image,
            code="text_binding_not_completed",
            message="Component annotation skipped because text binding did not complete.",
        )
    if structure_document.status != "completed":
        return build_skipped_component_annotation_document(
            task_id=task_id,
            image=image,
            code="component_structure_not_completed",
            message="Component annotation skipped because component structure did not complete.",
        )

    elements = index_dsl_elements(dsl)
    bindings_by_id = {binding.id: binding for binding in binding_document.bindings}
    group_ids_by_component = group_ids_by_component_id(structure_document.groups)
    annotations: list[ComponentAnnotationItem] = []
    warnings: list[ComponentAnnotationWarning] = []
    unresolved: list[str] = []

    for component in structure_document.components:
        if component.confidence < settings.component_annotation_min_confidence:
            unresolved.append(component.id)
            warnings.append(
                ComponentAnnotationWarning(
                    code="component_confidence_low",
                    message="Component confidence is below annotation threshold.",
                    componentId=component.id,
                )
            )
            continue
        component_annotation_count = 0
        if not component.bindingIds:
            warnings.append(
                ComponentAnnotationWarning(
                    code="component_without_bindings",
                    message="Component has no binding ids to annotate.",
                    componentId=component.id,
                )
            )
        for binding_id in component.bindingIds:
            binding = bindings_by_id.get(binding_id)
            if binding is None:
                warnings.append(
                    ComponentAnnotationWarning(
                        code="binding_not_found",
                        message="Component references a missing binding.",
                        componentId=component.id,
                        bindingId=binding_id,
                    )
                )
                continue
            created, binding_warnings = annotate_binding_elements(
                component=component,
                binding=binding,
                group_ids=group_ids_by_component.get(component.id, []),
                elements=elements,
                start_index=len(annotations) + 1,
            )
            annotations.extend(created)
            warnings.extend(binding_warnings)
            component_annotation_count += len(created)
        if component_annotation_count == 0:
            unresolved.append(component.id)

    annotated_ids = {annotation.dslElementId for annotation in annotations}
    unannotated = [
        element_id
        for element_id, element in elements.items()
        if is_annotation_target(element_id, element) and element_id not in annotated_ids
    ]
    group_hints = build_group_hints(structure_document, annotations)
    document = ComponentAnnotationDocument(
        version="0.1",
        taskId=task_id,
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        annotations=annotations,
        groupHints=group_hints,
        unannotatedElementIds=sorted(unannotated),
        unresolvedComponentIds=sorted(set(unresolved)),
        warnings=warnings,
        meta={
            "notes": "dsl_component_annotation_harness",
            "annotationCount": len(annotations),
            "annotatedElementCount": len(annotated_ids),
            "unannotatedElementCount": len(unannotated),
            "groupHintCount": len(group_hints),
            "roleSummary": summarize_annotation_roles(annotations),
        },
    )
    validation_errors = validate_component_annotation_document(
        document=document,
        binding_document=binding_document,
        structure_document=structure_document,
        dsl=dsl,
    )
    if validation_errors:
        return build_failed_component_annotation_document(
            task_id=task_id,
            image=image,
            code="COMPONENT_ANNOTATION_VALIDATION_FAILED",
            message="Component annotation validation failed.",
            warnings=[
                ComponentAnnotationWarning(
                    code="COMPONENT_ANNOTATION_VALIDATION_ERROR",
                    message=error,
                )
                for error in validation_errors
            ],
        )
    return document


def annotate_binding_elements(
    *,
    component: ComponentStructureItem,
    binding: TextPrimitiveBinding,
    group_ids: list[str],
    elements: dict[str, dict[str, Any]],
    start_index: int,
) -> tuple[list[ComponentAnnotationItem], list[ComponentAnnotationWarning]]:
    specs = [
        (f"visible_text_{binding.ocrBlockId}", "replacement_text_bound_to_component"),
        (f"cover_{binding.ocrBlockId}", "replacement_cover_bound_to_component"),
        (f"text_{safe_id(binding.ocrBlockId)}", "hidden_candidate_bound_to_component"),
    ]
    annotations: list[ComponentAnnotationItem] = []
    warnings: list[ComponentAnnotationWarning] = []
    present = {element_id: element_id in elements for element_id, _ in specs}
    if present[specs[0][0]] != present[specs[1][0]]:
        warnings.append(
            ComponentAnnotationWarning(
                code="cover_text_pair_incomplete",
                message="Replacement cover/text pair is incomplete for binding.",
                componentId=component.id,
                bindingId=binding.id,
            )
        )
    if not present[specs[2][0]]:
        warnings.append(
            ComponentAnnotationWarning(
                code="candidate_text_not_found",
                message="Hidden OCR candidate text element was not found for binding.",
                componentId=component.id,
                bindingId=binding.id,
                dslElementId=specs[2][0],
            )
        )

    for element_id, reason in specs:
        element = elements.get(element_id)
        if element is None:
            if reason != "hidden_candidate_bound_to_component":
                warnings.append(
                    ComponentAnnotationWarning(
                        code="dsl_element_not_found",
                        message="Expected DSL element was not found for binding.",
                        componentId=component.id,
                        bindingId=binding.id,
                        dslElementId=element_id,
                    )
                )
            continue
        annotation = ComponentAnnotationItem(
            id=f"annotation_{start_index + len(annotations):03d}",
            dslElementId=element_id,
            elementType=str(element.get("type") or "unknown"),
            elementRole=str(element.get("role") or "unknown"),
            componentId=component.id,
            componentRole=component.role,
            groupIds=list(group_ids),
            relationship=binding.relationship,
            bindingId=binding.id,
            ocrBlockId=binding.ocrBlockId,
            confidence=round(min(component.confidence, binding.confidence), 3),
            reason=reason,
            layerName=layer_name_for_annotation(component.role, element, binding.text),
        )
        annotations.append(annotation)
    return annotations, warnings


def build_group_hints(
    structure_document: ComponentStructureDocument,
    annotations: list[ComponentAnnotationItem],
) -> list[ComponentGroupHint]:
    annotations_by_component: dict[str, list[ComponentAnnotationItem]] = {}
    for annotation in annotations:
        annotations_by_component.setdefault(annotation.componentId, []).append(annotation)

    hints: list[ComponentGroupHint] = []
    for group in structure_document.groups:
        component_ids = [component_id for component_id in group.componentIds if component_id in annotations_by_component]
        dsl_ids = unique_preserve_order(
            annotation.dslElementId
            for component_id in group.componentIds
            for annotation in annotations_by_component.get(component_id, [])
        )
        hints.append(
            ComponentGroupHint(
                id=f"group_hint_{group.role}_{len(hints) + 1:03d}",
                groupId=group.id,
                role=group.role,
                componentIds=component_ids,
                dslElementIds=dsl_ids,
                status=group_hint_status(component_ids, dsl_ids),
                reason=group_hint_reason(component_ids, dsl_ids),
            )
        )

    legend_components = [component for component in structure_document.components if component.role == "legend_group"]
    for component in legend_components:
        dsl_ids = unique_preserve_order(
            annotation.dslElementId
            for annotation in annotations_by_component.get(component.id, [])
            if annotation.elementRole == "visible_text_replacement"
        )
        if not dsl_ids:
            continue
        hints.append(
            ComponentGroupHint(
                id=f"group_hint_legend_group_{len(hints) + 1:03d}",
                groupId=component.id,
                role="legend_group",
                componentIds=[component.id],
                dslElementIds=dsl_ids,
                status="ready_for_future_grouping" if len(dsl_ids) >= 2 else "partial",
                reason="legend_component_has_annotated_labels",
            )
        )
    return hints


def group_hint_status(component_ids: list[str], dsl_ids: list[str]) -> GroupHintStatus:
    if len(component_ids) >= 2 and len(dsl_ids) >= 2:
        return "ready_for_future_grouping"
    if component_ids and dsl_ids:
        return "partial"
    return "blocked"


def group_hint_reason(component_ids: list[str], dsl_ids: list[str]) -> str:
    if len(component_ids) >= 2 and len(dsl_ids) >= 2:
        return "m16_layout_group_has_annotated_elements"
    if component_ids and dsl_ids:
        return "m16_layout_group_partially_annotated"
    return "group_without_annotated_elements"


def apply_component_annotations(
    dsl: dict[str, Any],
    document: ComponentAnnotationDocument,
    *,
    layer_naming: bool,
) -> dict[str, Any]:
    if document.status != "completed":
        return deepcopy(dsl)
    next_dsl = deepcopy(dsl)
    annotations_by_id = {annotation.dslElementId: annotation for annotation in document.annotations}
    page_group_ids = [hint.groupId for hint in document.groupHints if hint.role == "page_structure"]
    apply_annotations_to_element(next_dsl.get("root"), annotations_by_id, page_group_ids, layer_naming)

    meta = next_dsl.setdefault("meta", {})
    quality_flags = list(meta.get("qualityFlags") or [])
    if "m17_component_annotation" not in quality_flags:
        quality_flags.append("m17_component_annotation")
    meta["qualityFlags"] = quality_flags
    meta["componentAnnotationCount"] = len(document.annotations)
    meta["componentAnnotatedElementCount"] = len({annotation.dslElementId for annotation in document.annotations})
    meta["componentUnannotatedElementCount"] = len(document.unannotatedElementIds)
    meta["componentGroupHintCount"] = len(document.groupHints)
    return next_dsl


def apply_annotations_to_element(
    element: Any,
    annotations_by_id: dict[str, ComponentAnnotationItem],
    page_group_ids: list[str],
    layer_naming: bool,
) -> None:
    if not isinstance(element, dict):
        return
    element_id = str(element.get("id") or "")
    annotation = annotations_by_id.get(element_id)
    if annotation is not None:
        element_meta = element.setdefault("meta", {})
        element_meta["componentId"] = annotation.componentId
        element_meta["componentRole"] = annotation.componentRole
        element_meta["groupIds"] = annotation.groupIds
        element_meta["bindingId"] = annotation.bindingId
        element_meta["ocrBlockId"] = annotation.ocrBlockId
        element_meta["relationship"] = annotation.relationship
        element_meta["annotationSource"] = "m17_component_annotation"
        if layer_naming:
            element["name"] = annotation.layerName
    elif is_fallback_region(element):
        element_meta = element.setdefault("meta", {})
        element_meta["annotationRole"] = "fallback_context"
        element_meta["groupIds"] = list(page_group_ids)
        element_meta["annotationSource"] = "m17_component_annotation"
        if layer_naming:
            element["name"] = fallback_layer_name(element)
    elif element_id == "original_ref":
        if layer_naming:
            element["name"] = "Original Reference"

    children = element.get("children")
    if isinstance(children, list):
        for child in children:
            apply_annotations_to_element(child, annotations_by_id, page_group_ids, layer_naming)


def validate_component_annotation_document(
    *,
    document: ComponentAnnotationDocument,
    binding_document: TextPrimitiveBindingDocument,
    structure_document: ComponentStructureDocument,
    dsl: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if document.version != "0.1":
        errors.append("version must be 0.1")
    if not document.taskId:
        errors.append("taskId is required")

    elements = index_dsl_elements(dsl)
    binding_ids = {binding.id for binding in binding_document.bindings}
    component_ids = {component.id for component in structure_document.components}
    group_ids = {group.id for group in structure_document.groups}
    annotation_ids = {annotation.id for annotation in document.annotations}
    if len(annotation_ids) != len(document.annotations):
        errors.append("annotation ids must be unique")
    group_hint_ids = {hint.id for hint in document.groupHints}
    if len(group_hint_ids) != len(document.groupHints):
        errors.append("group hint ids must be unique")

    for annotation in document.annotations:
        if annotation.dslElementId not in elements:
            errors.append(f"annotation references missing DSL element: {annotation.id}")
        if annotation.componentId not in component_ids:
            errors.append(f"annotation references missing component: {annotation.id}")
        if annotation.bindingId not in binding_ids:
            errors.append(f"annotation references missing binding: {annotation.id}")
        for group_id in annotation.groupIds:
            if group_id not in group_ids:
                errors.append(f"annotation references missing group: {annotation.id}")

    for hint in document.groupHints:
        if hint.groupId not in group_ids and hint.groupId not in component_ids:
            errors.append(f"group hint references missing group/component: {hint.id}")
        for component_id in hint.componentIds:
            if component_id not in component_ids:
                errors.append(f"group hint references missing component: {hint.id}")
        for dsl_element_id in hint.dslElementIds:
            if dsl_element_id not in elements:
                errors.append(f"group hint references missing DSL element: {hint.id}")

    if document.meta.get("annotationCount") != len(document.annotations):
        errors.append("meta annotationCount must match annotations length")
    if document.meta.get("annotatedElementCount") != len({annotation.dslElementId for annotation in document.annotations}):
        errors.append("meta annotatedElementCount must match annotated DSL element count")
    if document.meta.get("unannotatedElementCount") != len(document.unannotatedElementIds):
        errors.append("meta unannotatedElementCount must match unannotatedElementIds length")
    if document.meta.get("groupHintCount") != len(document.groupHints):
        errors.append("meta groupHintCount must match groupHints length")
    return errors


def build_skipped_component_annotation_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
) -> ComponentAnnotationDocument:
    return ComponentAnnotationDocument(
        version="0.1",
        taskId=task_id,
        status="skipped",
        imageSize={"width": image.width, "height": image.height},
        annotations=[],
        groupHints=[],
        unannotatedElementIds=[],
        unresolvedComponentIds=[],
        warnings=[ComponentAnnotationWarning(code=code, message=message)],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def build_failed_component_annotation_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
    warnings: list[ComponentAnnotationWarning] | None = None,
) -> ComponentAnnotationDocument:
    return ComponentAnnotationDocument(
        version="0.1",
        taskId=task_id,
        status="failed",
        imageSize={"width": image.width, "height": image.height},
        annotations=[],
        groupHints=[],
        unannotatedElementIds=[],
        unresolvedComponentIds=[],
        warnings=warnings or [ComponentAnnotationWarning(code=code, message=message)],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def empty_meta() -> dict[str, Any]:
    return {
        "notes": "dsl_component_annotation_harness",
        "annotationCount": 0,
        "annotatedElementCount": 0,
        "unannotatedElementCount": 0,
        "groupHintCount": 0,
        "roleSummary": {},
    }


def index_dsl_elements(dsl: dict[str, Any]) -> dict[str, dict[str, Any]]:
    elements: dict[str, dict[str, Any]] = {}

    def visit(element: Any) -> None:
        if not isinstance(element, dict):
            return
        element_id = element.get("id")
        if isinstance(element_id, str) and element_id:
            elements[element_id] = element
        children = element.get("children")
        if isinstance(children, list):
            for child in children:
                visit(child)

    visit(dsl.get("root"))
    return elements


def group_ids_by_component_id(groups: list[ComponentStructureGroup]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for group in groups:
        for component_id in group.componentIds:
            grouped.setdefault(component_id, []).append(group.id)
    return grouped


def is_annotation_target(element_id: str, element: dict[str, Any]) -> bool:
    role = str(element.get("role") or "")
    return (
        role in {"visible_text_replacement", "text_replacement_cover", "candidate_text"}
        or element_id.startswith("visible_text_")
        or element_id.startswith("cover_")
        or element_id.startswith("text_")
    )


def is_fallback_region(element: dict[str, Any]) -> bool:
    element_id = str(element.get("id") or "")
    role = str(element.get("role") or "")
    return element_id.startswith("fallback_region_") or element_id == "fallback_full_image" or role == "fallback_region"


def fallback_layer_name(element: dict[str, Any]) -> str:
    element_id = str(element.get("id") or "")
    if element_id in FALLBACK_NAMES:
        return FALLBACK_NAMES[element_id]
    if element_id.startswith("fallback_region_"):
        return f"Fallback / {element_id.removeprefix('fallback_region_').title()}"
    return "Fallback"


def layer_name_for_annotation(component_role: str, element: dict[str, Any], text: str) -> str:
    role_label = ROLE_LABELS.get(component_role, component_role.replace("_", " ").title())
    element_label = element_label_for(element)
    preview = text_preview(text if str(element.get("type") or "") == "text" else "")
    return f"{role_label} / {element_label} / {preview}" if preview else f"{role_label} / {element_label}"


def element_label_for(element: dict[str, Any]) -> str:
    role = str(element.get("role") or "")
    element_id = str(element.get("id") or "")
    if role == "visible_text_replacement":
        return "Text"
    if role == "text_replacement_cover":
        return "Cover"
    if role == "candidate_text":
        return "Candidate Text"
    if element_id.startswith("visible_text_"):
        return "Text"
    if element_id.startswith("cover_"):
        return "Cover"
    if element_id.startswith("text_"):
        return "Candidate Text"
    if is_fallback_region(element):
        return "Fallback"
    return str(element.get("type") or "Element").replace("_", " ").title()


def text_preview(text: str, limit: int = 24) -> str:
    stripped = " ".join(text.strip().split())
    if len(stripped) <= limit:
        return stripped
    return f"{stripped[: max(1, limit - 3)]}..."


def summarize_annotation_roles(annotations: list[ComponentAnnotationItem]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for annotation in annotations:
        summary[annotation.componentRole] = summary.get(annotation.componentRole, 0) + 1
    return summary


def unique_preserve_order(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str) or value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result


def safe_id(value: str) -> str:
    normalized = "".join(char if char.isalnum() or char == "_" else "_" for char in value.strip())
    return normalized or "unknown"
