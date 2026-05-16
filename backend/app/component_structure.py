from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .config import Settings
from .ocr import OCRDocument
from .png_tools import PngMetadata
from .text_binding import (
    TextBindingContainer,
    TextPrimitiveBinding,
    TextPrimitiveBindingDocument,
)
from .text_replacement import TextReplacementDocument
from .visual_primitives import VisualPrimitiveDocument


StructureStatus = Literal["completed", "failed", "skipped"]

COMPONENT_ROLES = {
    "unknown",
    "page_header",
    "hero_profile",
    "badge",
    "status_badge",
    "activity_card",
    "summary_stat_card",
    "primary_button",
    "outline_button",
    "shortcut_card",
    "preview_card",
    "legend_group",
    "tip_card",
    "bottom_nav",
    "bottom_nav_item",
}

GROUP_ROLES = {
    "summary_stat_group",
    "shortcut_grid",
    "preview_section",
    "bottom_nav_group",
    "page_structure",
}

LAYOUT_PATTERNS = {
    "single",
    "vertical_stack",
    "horizontal_row",
    "three_column_row",
    "grid_2x2",
    "bottom_nav_row",
    "unknown",
}

COMPONENT_CONTAINER_ROLES = COMPONENT_ROLES - {"unknown"}


@dataclass
class ComponentStructureWarning:
    code: str
    message: str
    containerId: str | None = None


@dataclass
class ComponentStructureItem:
    id: str
    role: str
    source: str
    bbox: list[int]
    confidence: float
    reason: str
    containerIds: list[str]
    bindingIds: list[str]
    relationships: dict[str, list[str]]
    layout: dict[str, Any]
    quality: dict[str, Any]


@dataclass
class ComponentStructureGroup:
    id: str
    role: str
    source: str
    bbox: list[int]
    componentIds: list[str]
    layout: dict[str, Any]
    confidence: float
    reason: str


@dataclass
class ComponentStructureDocument:
    version: str
    taskId: str
    status: StructureStatus
    imageSize: dict[str, int]
    components: list[ComponentStructureItem]
    groups: list[ComponentStructureGroup]
    unstructuredContainerIds: list[str]
    warnings: list[ComponentStructureWarning]
    meta: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_component_structure_document(
    *,
    task_id: str,
    image: PngMetadata,
    ocr_document: OCRDocument,
    primitive_document: VisualPrimitiveDocument,
    replacement_document: TextReplacementDocument,
    binding_document: TextPrimitiveBindingDocument,
    dsl: dict[str, Any],
    settings: Settings,
) -> ComponentStructureDocument:
    del primitive_document, replacement_document, dsl
    if not settings.component_structure_enabled:
        return build_skipped_component_structure_document(
            task_id=task_id,
            image=image,
            code="component_structure_disabled",
            message="Component structure is disabled.",
        )
    if ocr_document.status != "completed":
        return build_skipped_component_structure_document(
            task_id=task_id,
            image=image,
            code="ocr_not_completed",
            message="Component structure skipped because OCR did not complete.",
        )
    if binding_document.status != "completed":
        return build_skipped_component_structure_document(
            task_id=task_id,
            image=image,
            code="text_binding_not_completed",
            message="Component structure skipped because text binding did not complete.",
        )

    components, unstructured = build_components(binding_document, settings.component_structure_min_confidence)
    groups = build_groups(components)
    document = ComponentStructureDocument(
        version="0.1",
        taskId=task_id,
        status="completed",
        imageSize={"width": image.width, "height": image.height},
        components=components,
        groups=groups,
        unstructuredContainerIds=unstructured,
        warnings=[],
        meta={
            "notes": "component_structure_harness",
            "componentCount": len(components),
            "groupCount": len(groups),
            "unstructuredCount": len(unstructured),
            "roleSummary": summarize_component_roles(components),
            "groupRoleSummary": summarize_group_roles(groups),
            "layoutSummary": summarize_layouts(components, groups),
        },
    )
    validation_errors = validate_component_structure_document(document, binding_document)
    if validation_errors:
        return build_failed_component_structure_document(
            task_id=task_id,
            image=image,
            code="COMPONENT_STRUCTURE_VALIDATION_FAILED",
            message="Component structure validation failed.",
            warnings=[
                ComponentStructureWarning(
                    code="COMPONENT_STRUCTURE_VALIDATION_ERROR",
                    message=error,
                )
                for error in validation_errors
            ],
        )
    return document


def build_skipped_component_structure_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
) -> ComponentStructureDocument:
    return ComponentStructureDocument(
        version="0.1",
        taskId=task_id,
        status="skipped",
        imageSize={"width": image.width, "height": image.height},
        components=[],
        groups=[],
        unstructuredContainerIds=[],
        warnings=[ComponentStructureWarning(code=code, message=message)],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def build_failed_component_structure_document(
    *,
    task_id: str,
    image: PngMetadata,
    code: str,
    message: str,
    warnings: list[ComponentStructureWarning] | None = None,
) -> ComponentStructureDocument:
    return ComponentStructureDocument(
        version="0.1",
        taskId=task_id,
        status="failed",
        imageSize={"width": image.width, "height": image.height},
        components=[],
        groups=[],
        unstructuredContainerIds=[],
        warnings=warnings or [ComponentStructureWarning(code=code, message=message)],
        meta=empty_meta(),
        error={"code": code, "message": message},
    )


def empty_meta() -> dict[str, Any]:
    return {
        "notes": "component_structure_harness",
        "componentCount": 0,
        "groupCount": 0,
        "unstructuredCount": 0,
        "roleSummary": {},
        "groupRoleSummary": {},
        "layoutSummary": {},
    }


def build_components(
    binding_document: TextPrimitiveBindingDocument,
    min_confidence: float,
) -> tuple[list[ComponentStructureItem], list[str]]:
    containers_by_id = {container.id: container for container in binding_document.containers}
    bindings_by_container = group_bindings_by_container(binding_document.bindings)
    components: list[ComponentStructureItem] = []
    unstructured: list[str] = []
    role_index: dict[str, int] = {}

    for container in binding_document.containers:
        if container.source == "fallback_region":
            continue
        if container.role not in COMPONENT_CONTAINER_ROLES:
            unstructured.append(container.id)
            continue
        bindings = bindings_by_container.get(container.id, [])
        confidence = component_confidence(container, bindings)
        if confidence < min_confidence:
            unstructured.append(container.id)
            continue
        role_index[container.role] = role_index.get(container.role, 0) + 1
        components.append(
            build_component(
                container=container,
                bindings=bindings,
                containers_by_id=containers_by_id,
                index=role_index[container.role],
                confidence=confidence,
            )
        )

    return components, sorted(set(unstructured))


def build_component(
    *,
    container: TextBindingContainer,
    bindings: list[TextPrimitiveBinding],
    containers_by_id: dict[str, TextBindingContainer],
    index: int,
    confidence: float,
) -> ComponentStructureItem:
    related_containers = related_container_ids(container, containers_by_id)
    bbox = union_bboxes([containers_by_id[container_id].bbox for container_id in related_containers])
    layout = infer_component_layout(container.role, bindings)
    quality_reasons = ["container_confidence_ok"]
    if bindings:
        quality_reasons.append("bindings_present")
    else:
        quality_reasons.append("missing_required_bindings")
    if layout["pattern"] != "unknown":
        quality_reasons.append("layout_alignment_ok")

    return ComponentStructureItem(
        id=f"component_{container.role}_{index:03d}",
        role=container.role,
        source="m16_from_text_bindings",
        bbox=bbox,
        confidence=round(confidence, 3),
        reason=f"m15_container_role_{container.role}",
        containerIds=related_containers,
        bindingIds=[binding.id for binding in bindings],
        relationships=relationships_for_bindings(bindings),
        layout=layout,
        quality={
            "risk": component_risk(confidence, bindings),
            "reasons": quality_reasons,
        },
    )


def related_container_ids(
    container: TextBindingContainer,
    containers_by_id: dict[str, TextBindingContainer],
) -> list[str]:
    ids = [container.id]
    if container.role == "hero_profile":
        ids.extend(
            related.id
            for related in containers_by_id.values()
            if related.role == "badge" and bbox_inside_or_near(related.bbox, container.bbox)
        )
    if container.role == "activity_card":
        ids.extend(
            related.id
            for related in containers_by_id.values()
            if related.role == "status_badge" and bbox_inside_or_near(related.bbox, container.bbox)
        )
    if container.role == "preview_card":
        ids.extend(
            related.id
            for related in containers_by_id.values()
            if related.role in {"outline_button", "legend_group"} and bbox_inside_or_near(related.bbox, container.bbox)
        )
    return sorted(set(ids), key=ids.index)


def build_groups(components: list[ComponentStructureItem]) -> list[ComponentStructureGroup]:
    groups: list[ComponentStructureGroup] = []
    groups.extend(group_same_row_components(components, "summary_stat_card", "summary_stat_group", "same_row_summary_stat_cards"))
    groups.extend(group_shortcut_grid(components))
    groups.extend(group_preview_section(components))
    groups.extend(group_same_row_components(components, "bottom_nav_item", "bottom_nav_group", "same_row_bottom_nav_items"))
    page_group = group_page_structure(components)
    if page_group is not None:
        groups.append(page_group)
    return groups


def group_same_row_components(
    components: list[ComponentStructureItem],
    component_role: str,
    group_role: str,
    reason: str,
) -> list[ComponentStructureGroup]:
    items = sorted([component for component in components if component.role == component_role], key=lambda item: item.bbox[0])
    if len(items) < 2 or not same_row(items):
        return []
    pattern = "bottom_nav_row" if group_role == "bottom_nav_group" else "three_column_row" if len(items) == 3 else "horizontal_row"
    return [
        ComponentStructureGroup(
            id=f"group_{group_role}_001",
            role=group_role,
            source="m16_from_component_alignment",
            bbox=union_bboxes([item.bbox for item in items]),
            componentIds=[item.id for item in items],
            layout={
                "pattern": pattern,
                "axis": "horizontal",
                "itemCount": len(items),
                "gapEstimate": estimate_horizontal_gap([item.bbox for item in items]),
            },
            confidence=round(average([item.confidence for item in items]), 3),
            reason=reason,
        )
    ]


def group_shortcut_grid(components: list[ComponentStructureItem]) -> list[ComponentStructureGroup]:
    items = sorted([component for component in components if component.role == "shortcut_card"], key=lambda item: (item.bbox[1], item.bbox[0]))
    if len(items) < 2:
        return []
    rows = group_items_by_row(items)
    if len(items) == 4 and len(rows) == 2 and all(len(row) == 2 for row in rows):
        pattern = "grid_2x2"
    elif len(rows) == 1:
        pattern = "horizontal_row"
    else:
        pattern = "unknown"
    if pattern == "unknown":
        return []
    return [
        ComponentStructureGroup(
            id="group_shortcut_grid_001",
            role="shortcut_grid",
            source="m16_from_component_alignment",
            bbox=union_bboxes([item.bbox for item in items]),
            componentIds=[item.id for item in items],
            layout={
                "pattern": pattern,
                "axis": "grid" if pattern == "grid_2x2" else "horizontal",
                "itemCount": len(items),
                "gapEstimate": estimate_grid_gap(rows),
            },
            confidence=round(average([item.confidence for item in items]), 3),
            reason="aligned_shortcut_cards",
        )
    ]


def group_preview_section(components: list[ComponentStructureItem]) -> list[ComponentStructureGroup]:
    preview = [component for component in components if component.role == "preview_card"]
    if not preview:
        return []
    related = [
        component
        for component in components
        if component.role in {"preview_card", "outline_button", "legend_group"}
        and any(bbox_inside_or_near(component.bbox, item.bbox) for item in preview)
    ]
    if len(related) < 2:
        return []
    return [
        ComponentStructureGroup(
            id="group_preview_section_001",
            role="preview_section",
            source="m16_from_component_alignment",
            bbox=union_bboxes([item.bbox for item in related]),
            componentIds=[item.id for item in sorted(related, key=lambda item: (item.bbox[1], item.bbox[0]))],
            layout={
                "pattern": "vertical_stack",
                "axis": "vertical",
                "itemCount": len(related),
                "gapEstimate": estimate_vertical_gap([item.bbox for item in related]),
            },
            confidence=round(average([item.confidence for item in related]), 3),
            reason="preview_card_with_controls",
        )
    ]


def group_page_structure(components: list[ComponentStructureItem]) -> ComponentStructureGroup | None:
    main_components = [
        component
        for component in components
        if component.role
        in {
            "page_header",
            "hero_profile",
            "activity_card",
            "summary_stat_card",
            "primary_button",
            "shortcut_card",
            "preview_card",
            "tip_card",
            "bottom_nav",
            "bottom_nav_item",
        }
    ]
    if len(main_components) < 2:
        return None
    ordered = sorted(main_components, key=lambda item: (item.bbox[1], item.bbox[0]))
    return ComponentStructureGroup(
        id="group_page_structure_001",
        role="page_structure",
        source="m16_from_component_alignment",
        bbox=union_bboxes([item.bbox for item in ordered]),
        componentIds=[item.id for item in ordered],
        layout={
            "pattern": "vertical_stack",
            "axis": "vertical",
            "itemCount": len(ordered),
            "gapEstimate": estimate_vertical_gap([item.bbox for item in ordered]),
        },
        confidence=round(average([item.confidence for item in ordered]), 3),
        reason="page_components_ordered_by_y",
    )


def apply_component_structure_metadata(
    dsl: dict[str, Any],
    document: ComponentStructureDocument,
) -> dict[str, Any]:
    if document.status != "completed":
        return deepcopy(dsl)
    next_dsl = deepcopy(dsl)
    meta = next_dsl.setdefault("meta", {})
    quality_flags = list(meta.get("qualityFlags") or [])
    if "m16_component_structure_harness" not in quality_flags:
        quality_flags.append("m16_component_structure_harness")
    meta["qualityFlags"] = quality_flags
    meta["componentStructureCount"] = len(document.components)
    meta["componentStructureGroupCount"] = len(document.groups)
    meta["componentStructureUnstructuredCount"] = len(document.unstructuredContainerIds)
    return next_dsl


def validate_component_structure_document(
    document: ComponentStructureDocument,
    binding_document: TextPrimitiveBindingDocument,
) -> list[str]:
    errors: list[str] = []
    if document.version != "0.1":
        errors.append("version must be 0.1")
    if not document.taskId:
        errors.append("taskId is required")
    component_ids = {component.id for component in document.components}
    if len(component_ids) != len(document.components):
        errors.append("component ids must be unique")
    group_ids = {group.id for group in document.groups}
    if len(group_ids) != len(document.groups):
        errors.append("group ids must be unique")

    binding_ids = {binding.id for binding in binding_document.bindings}
    container_ids = {container.id for container in binding_document.containers}
    for component in document.components:
        if component.role not in COMPONENT_ROLES:
            errors.append(f"invalid component role: {component.role}")
        if not valid_bbox(component.bbox):
            errors.append(f"invalid component bbox: {component.id}")
        for binding_id in component.bindingIds:
            if binding_id not in binding_ids:
                errors.append(f"component references missing binding: {component.id}")
        for container_id in component.containerIds:
            if container_id not in container_ids:
                errors.append(f"component references missing container: {component.id}")
        if component.layout.get("pattern") not in LAYOUT_PATTERNS:
            errors.append(f"invalid component layout pattern: {component.id}")
    for group in document.groups:
        if group.role not in GROUP_ROLES:
            errors.append(f"invalid group role: {group.role}")
        if not valid_bbox(group.bbox):
            errors.append(f"invalid group bbox: {group.id}")
        if group.layout.get("pattern") not in LAYOUT_PATTERNS:
            errors.append(f"invalid group layout pattern: {group.id}")
        for component_id in group.componentIds:
            if component_id not in component_ids:
                errors.append(f"group references missing component: {group.id}")
    if document.meta.get("componentCount") != len(document.components):
        errors.append("meta componentCount must match components length")
    if document.meta.get("groupCount") != len(document.groups):
        errors.append("meta groupCount must match groups length")
    if document.meta.get("unstructuredCount") != len(document.unstructuredContainerIds):
        errors.append("meta unstructuredCount must match unstructuredContainerIds length")
    return errors


def group_bindings_by_container(bindings: list[TextPrimitiveBinding]) -> dict[str, list[TextPrimitiveBinding]]:
    grouped: dict[str, list[TextPrimitiveBinding]] = {}
    for binding in bindings:
        grouped.setdefault(binding.containerId, []).append(binding)
    return grouped


def component_confidence(container: TextBindingContainer, bindings: list[TextPrimitiveBinding]) -> float:
    values = [container.confidence, *[binding.confidence for binding in bindings]]
    confidence = average(values)
    if bindings:
        confidence += 0.04
    else:
        confidence -= 0.08
    if container.role in {"badge", "status_badge", "primary_button", "outline_button", "bottom_nav_item"}:
        confidence += 0.03
    return max(0.0, min(0.99, confidence))


def component_risk(confidence: float, bindings: list[TextPrimitiveBinding]) -> str:
    if confidence < 0.7 or not bindings:
        return "high"
    if confidence < 0.82:
        return "medium"
    return "low"


def relationships_for_bindings(bindings: list[TextPrimitiveBinding]) -> dict[str, list[str]]:
    relationships: dict[str, list[str]] = {}
    for binding in bindings:
        relationships.setdefault(binding.relationship, []).append(binding.id)
    return relationships


def infer_component_layout(role: str, bindings: list[TextPrimitiveBinding]) -> dict[str, Any]:
    if role in {"page_header", "badge", "status_badge", "primary_button", "outline_button", "bottom_nav_item"}:
        pattern = "single"
        axis = "none"
    elif same_row_bindings(bindings):
        pattern = "horizontal_row"
        axis = "horizontal"
    elif len(bindings) > 1:
        pattern = "vertical_stack"
        axis = "vertical"
    else:
        pattern = "single"
        axis = "none"
    return {
        "pattern": pattern,
        "axis": axis,
        "itemCount": len(bindings),
        "gapEstimate": estimate_binding_gap(bindings, axis),
    }


def same_row_bindings(bindings: list[TextPrimitiveBinding]) -> bool:
    if len(bindings) < 2:
        return False
    centers = [bbox_center_y(binding.bbox) for binding in bindings]
    heights = [binding.bbox[3] for binding in bindings]
    return max(centers) - min(centers) <= max(8, average(heights) * 0.45)


def group_items_by_row(items: list[ComponentStructureItem]) -> list[list[ComponentStructureItem]]:
    rows: list[list[ComponentStructureItem]] = []
    for item in sorted(items, key=lambda value: (bbox_center_y(value.bbox), value.bbox[0])):
        for row in rows:
            row_center = average([bbox_center_y(value.bbox) for value in row])
            row_height = average([value.bbox[3] for value in row])
            if abs(bbox_center_y(item.bbox) - row_center) <= max(10, row_height * 0.5):
                row.append(item)
                break
        else:
            rows.append([item])
    return [sorted(row, key=lambda value: value.bbox[0]) for row in rows]


def same_row(items: list[ComponentStructureItem]) -> bool:
    if len(items) < 2:
        return False
    centers = [bbox_center_y(item.bbox) for item in items]
    heights = [item.bbox[3] for item in items]
    return max(centers) - min(centers) <= max(10, average(heights) * 0.5)


def estimate_binding_gap(bindings: list[TextPrimitiveBinding], axis: str) -> int:
    if len(bindings) < 2:
        return 0
    bboxes = [binding.bbox for binding in sorted(bindings, key=lambda item: (item.bbox[1], item.bbox[0]))]
    if axis == "horizontal":
        return estimate_horizontal_gap(bboxes)
    if axis == "vertical":
        return estimate_vertical_gap(bboxes)
    return 0


def estimate_grid_gap(rows: list[list[ComponentStructureItem]]) -> int:
    gaps = [estimate_horizontal_gap([item.bbox for item in row]) for row in rows if len(row) > 1]
    if len(rows) > 1:
        row_bboxes = [union_bboxes([item.bbox for item in row]) for row in rows]
        gaps.append(estimate_vertical_gap(row_bboxes))
    return round(average(gaps)) if gaps else 0


def estimate_horizontal_gap(bboxes: list[list[int]]) -> int:
    ordered = sorted(bboxes, key=lambda bbox: bbox[0])
    gaps = [ordered[index + 1][0] - (ordered[index][0] + ordered[index][2]) for index in range(len(ordered) - 1)]
    return round(average([max(0, gap) for gap in gaps])) if gaps else 0


def estimate_vertical_gap(bboxes: list[list[int]]) -> int:
    ordered = sorted(bboxes, key=lambda bbox: bbox[1])
    gaps = [ordered[index + 1][1] - (ordered[index][1] + ordered[index][3]) for index in range(len(ordered) - 1)]
    return round(average([max(0, gap) for gap in gaps])) if gaps else 0


def bbox_inside_or_near(inner: list[int], outer: list[int]) -> bool:
    expanded = expand_bbox(outer, 24, 24)
    return point_inside(bbox_center_x(inner), bbox_center_y(inner), expanded) or intersection_area(inner, expanded) > 0


def point_inside(x: float, y: float, bbox: list[int]) -> bool:
    return bbox[0] <= x <= bbox[0] + bbox[2] and bbox[1] <= y <= bbox[1] + bbox[3]


def valid_bbox(bbox: list[int]) -> bool:
    return len(bbox) == 4 and bbox[2] > 0 and bbox[3] > 0


def bbox_center_x(bbox: list[int]) -> float:
    return bbox[0] + bbox[2] / 2


def bbox_center_y(bbox: list[int]) -> float:
    return bbox[1] + bbox[3] / 2


def intersection_area(a: list[int], b: list[int]) -> int:
    left = max(a[0], b[0])
    top = max(a[1], b[1])
    right = min(a[0] + a[2], b[0] + b[2])
    bottom = min(a[1] + a[3], b[1] + b[3])
    return max(0, right - left) * max(0, bottom - top)


def union_bboxes(bboxes: list[list[int]]) -> list[int]:
    left = min(bbox[0] for bbox in bboxes)
    top = min(bbox[1] for bbox in bboxes)
    right = max(bbox[0] + bbox[2] for bbox in bboxes)
    bottom = max(bbox[1] + bbox[3] for bbox in bboxes)
    return [left, top, right - left, bottom - top]


def expand_bbox(bbox: list[int], x_padding: int, y_padding: int) -> list[int]:
    return [bbox[0] - x_padding, bbox[1] - y_padding, bbox[2] + x_padding * 2, bbox[3] + y_padding * 2]


def average(values: list[float]) -> float:
    if not values:
        return 0
    return sum(values) / len(values)


def summarize_component_roles(components: list[ComponentStructureItem]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for component in components:
        summary[component.role] = summary.get(component.role, 0) + 1
    return summary


def summarize_group_roles(groups: list[ComponentStructureGroup]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for group in groups:
        summary[group.role] = summary.get(group.role, 0) + 1
    return summary


def summarize_layouts(
    components: list[ComponentStructureItem],
    groups: list[ComponentStructureGroup],
) -> dict[str, int]:
    summary: dict[str, int] = {}
    for item in [*components, *groups]:
        pattern = str(item.layout.get("pattern", "unknown"))
        summary[pattern] = summary.get(pattern, 0) + 1
    return summary
