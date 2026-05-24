from __future__ import annotations

from typing import Any

from ..visual_evidence_normalization import parse_bbox, parse_metrics
from ..visual_primitive_graph import M29PrimitiveMetrics, bbox_in_bounds
from .geometry import dedupe_strings, is_icon_like_text_noise, is_wide_bbox, truncate_text
from .types import EvidenceNodeKind, M2904Options, VisualObjectEvidenceNode


def build_evidence_nodes(
    m2903_document: dict[str, Any],
    m2902_document: dict[str, Any],
    width: int,
    height: int,
    options: M2904Options,
    ownership_routing: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[VisualObjectEvidenceNode], list[str]]:
    warnings: list[str] = []
    nodes: list[VisualObjectEvidenceNode] = []
    for raw in m2903_document.get("items", []):
        if not isinstance(raw, dict):
            continue
        bbox = parse_bbox(raw.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, width, height):
            continue
        source_id = str(raw.get("id") or "")
        if not source_id:
            continue
        visual_kind = str(raw.get("visualKind") or "")
        metrics = parse_metrics(raw.get("metrics"))
        node_kind, risks, reasons = classify_m2903_node(raw, bbox, metrics, options, warnings)
        ownership = (ownership_routing or {}).get(f"m2903_visual_evidence:{source_id}")
        nodes.append(
            VisualObjectEvidenceNode(
                id=f"evidence_{len(nodes) + 1:04d}",
                source="m2903_visual_evidence",
                source_id=source_id,
                bbox=bbox,
                node_kind=node_kind,
                source_visual_kind=visual_kind,
                source_decision=str(raw.get("decision") or ""),
                text=None,
                text_preview=None,
                confidence=float(raw.get("confidence", 0.5)),
                metrics=metrics,
                risks=ownership_augmented_risks(risks, ownership),
                reasons=ownership_augmented_reasons([*reasons, *[str(reason) for reason in raw.get("reasons", [])]], ownership),
                ownership_routing=ownership,
            )
        )
    for raw in m2902_document.get("textBoxes", []):
        if not isinstance(raw, dict):
            continue
        bbox = parse_bbox(raw.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, width, height):
            continue
        source_id = str(raw.get("id") or "")
        if not source_id:
            continue
        text = str(raw.get("text") or "").strip() or None
        ownership = (ownership_routing or {}).get(f"m2902_text_box:{source_id}")
        nodes.append(
            VisualObjectEvidenceNode(
                id=f"evidence_{len(nodes) + 1:04d}",
                source="m2902_text_box",
                source_id=source_id,
                bbox=bbox,
                node_kind="text",
                source_visual_kind=None,
                source_decision=None,
                text=text,
                text_preview=truncate_text(text, options.text_preview_max_chars),
                confidence=float(raw.get("confidence", 1.0)),
                metrics=None,
                risks=ownership_augmented_risks([], ownership),
                reasons=ownership_augmented_reasons(["m2902_text_box"], ownership),
                ownership_routing=ownership,
            )
        )
    return nodes, warnings

def build_ownership_routing(document: dict[str, Any] | None) -> tuple[dict[str, dict[str, Any]] | None, list[str]]:
    if document is None:
        return None, []
    if document.get("schemaName") != "M2907TextVisualOwnershipGateDocument" or document.get("schemaVersion") != "0.1":
        raise ValueError("M29.0.4 ownership input must be M2907TextVisualOwnershipGateDocument v0.1")
    routing: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for raw in document.get("ownershipDecisions", []):
        if not isinstance(raw, dict):
            continue
        source = str(raw.get("source") or "")
        if source == "m2903_visual_evidence":
            source_id = str(raw.get("sourceVisualEvidenceItemId") or "")
        elif source == "m2902_text_box":
            source_id = str(raw.get("sourceTextBoxId") or "")
        else:
            warnings.append(f"unknown_m2907_ownership_source:{source or '<empty>'}")
            continue
        if not source_id:
            warnings.append(f"missing_m2907_ownership_source_id:{raw.get('id', '<missing>')}")
            continue
        routing[f"{source}:{source_id}"] = {
            "ownershipDecisionId": str(raw.get("id") or ""),
            "ownership": str(raw.get("ownership") or ""),
            "decision": str(raw.get("decision") or ""),
            "ownershipReasonKind": str(raw.get("ownershipReasonKind") or ""),
            "matchedTextBoxIds": [str(item) for item in raw.get("matchedTextBoxIds", [])],
            "textPreview": raw.get("textPreview"),
            "suppressedAsVisual": bool(raw.get("suppressedAsVisual")),
            "allowedForObjectFormingVisualSide": bool(raw.get("allowedForObjectFormingVisualSide")),
            "allowedForTextSide": bool(raw.get("allowedForTextSide")),
            "allowedForAuditOnly": bool(raw.get("allowedForAuditOnly", True)),
        }
    return routing, warnings

def ownership_augmented_risks(risks: list[str], ownership: dict[str, Any] | None) -> list[str]:
    if ownership is None:
        return risks
    additions: list[str] = []
    if bool(ownership.get("suppressedAsVisual")):
        additions.append("ownership_suppressed_as_visual")
    if str(ownership.get("ownership") or "") == "mixed_or_uncertain":
        additions.append("ownership_mixed_or_uncertain")
    return dedupe_strings([*risks, *additions])

def ownership_augmented_reasons(reasons: list[str], ownership: dict[str, Any] | None) -> list[str]:
    if ownership is None:
        return reasons
    additions = [
        "m2907_ownership_routing",
        str(ownership.get("ownershipReasonKind") or ""),
    ]
    return dedupe_strings([*reasons, *additions])

def classify_m2903_node(
    raw: dict[str, Any],
    bbox: list[int],
    metrics: M29PrimitiveMetrics,
    options: M2904Options,
    warnings: list[str],
) -> tuple[EvidenceNodeKind, list[str], list[str]]:
    visual_kind = str(raw.get("visualKind") or "")
    text_overlap = float(raw.get("textOverlapRatio", 0.0))
    risks: list[str] = []
    reasons: list[str] = [f"from_{visual_kind or 'unknown_visual_kind'}"]
    if is_wide_bbox(bbox, options):
        risks.append("wide_source_bbox")
        return "wide_visual_source", risks, [*reasons, "wide_visual_source"]
    if visual_kind in {"accepted_image", "media_candidate", "icon_candidate", "other_candidate"}:
        return "visual", risks, reasons
    if visual_kind == "mixed_symbol_text_candidate":
        return "noise", ["symbol_text_ownership_conflict"], [*reasons, "mixed_symbol_text_candidate_audit_only"]
    if visual_kind == "text_noise":
        if is_icon_like_text_noise(bbox, metrics):
            return "weak_visual_text_noise", ["text_overlap", "icon_like_text_noise"], [*reasons, "icon_like_text_noise"]
        return "noise", ["text_overlap"] if text_overlap > 0 else [], reasons
    warnings.append(f"unknown_visual_kind:{visual_kind or '<empty>'}")
    return "noise", ["unknown_visual_kind"], [*reasons, "unknown_visual_kind"]
