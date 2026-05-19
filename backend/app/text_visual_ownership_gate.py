from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from .png_tools import PngPixels, UnsupportedPngCropError, decode_png_pixels, encode_rgb_png, read_png_metadata
from .visual_evidence_normalization import parse_bbox
from .visual_primitive_graph import bbox_area, bbox_in_bounds, bbox_x2, bbox_y2, crop_pixels, draw_rect


OwnershipSource = Literal["m2903_visual_evidence", "m2902_text_box"]
OwnershipKind = Literal["text_owned", "visual_owned", "shape_owned", "mixed_or_uncertain", "audit_only"]
OwnershipDecisionKind = Literal["accepted", "candidate", "uncertain", "rejected"]


@dataclass(frozen=True)
class M2907Options:
    text_owned_overlap_min: float = 0.55
    text_owned_text_covered_min: float = 0.45
    ocr_confidence_min: float = 0.55
    visual_candidate_high_text_overlap: float = 0.35
    text_preview_max_chars: int = 24
    output_preview_max_thumb: int = 160
    max_examples_per_kind: int = 40

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OwnershipDecision:
    id: str
    source: OwnershipSource
    source_evidence_id: str | None
    source_visual_evidence_item_id: str | None
    source_text_box_id: str | None
    source_visual_kind: str | None
    bbox: list[int]
    ownership: OwnershipKind
    decision: OwnershipDecisionKind
    ownership_reason_kind: str
    matched_text_box_ids: list[str]
    text_overlap_ratio: float
    ocr_overlap_ratio: float
    text_preview: str | None
    ocr_confidence: float | None
    suppressed_as_visual: bool
    allowed_for_object_forming_visual_side: bool
    allowed_for_text_side: bool
    allowed_for_audit_only: bool
    risks: list[str]
    reasons: list[str]
    source_lineage: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "source": self.source,
            "sourceEvidenceId": self.source_evidence_id,
            "sourceVisualEvidenceItemId": self.source_visual_evidence_item_id,
            "sourceTextBoxId": self.source_text_box_id,
            "sourceVisualKind": self.source_visual_kind,
            "bbox": self.bbox,
            "ownership": self.ownership,
            "decision": self.decision,
            "ownershipReasonKind": self.ownership_reason_kind,
            "matchedTextBoxIds": self.matched_text_box_ids,
            "textOverlapRatio": round(self.text_overlap_ratio, 4),
            "ocrOverlapRatio": round(self.ocr_overlap_ratio, 4),
            "textPreview": self.text_preview,
            "ocrConfidence": round(self.ocr_confidence, 3) if self.ocr_confidence is not None else None,
            "suppressedAsVisual": self.suppressed_as_visual,
            "allowedForObjectFormingVisualSide": self.allowed_for_object_forming_visual_side,
            "allowedForTextSide": self.allowed_for_text_side,
            "allowedForAuditOnly": self.allowed_for_audit_only,
            "risks": self.risks,
            "reasons": self.reasons,
        }
        if self.source_lineage is not None:
            data["sourceLineage"] = self.source_lineage
        return data


@dataclass(frozen=True)
class M2907DebugArtifacts:
    text_owned: str
    visual_owned: str
    mixed_or_uncertain: str
    object_forming_allowed: str

    def to_dict(self) -> dict[str, str]:
        return {
            "textOwned": self.text_owned,
            "visualOwned": self.visual_owned,
            "mixedOrUncertain": self.mixed_or_uncertain,
            "objectFormingAllowed": self.object_forming_allowed,
        }


@dataclass(frozen=True)
class M2907Document:
    schema_name: str
    schema_version: str
    source_image: str
    source_m2903_visual_evidence_json: str
    source_m2902_audit_json: str
    options: M2907Options
    ownership_decisions: list[OwnershipDecision]
    routing_views: dict[str, Any]
    audit: list[dict[str, Any]]
    debug: M2907DebugArtifacts
    warnings: list[str]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaName": self.schema_name,
            "schemaVersion": self.schema_version,
            "sourceImage": self.source_image,
            "sourceM2903VisualEvidenceJson": self.source_m2903_visual_evidence_json,
            "sourceM2902AuditJson": self.source_m2902_audit_json,
            "options": self.options.to_dict(),
            "ownershipDecisions": [item.to_dict() for item in self.ownership_decisions],
            "routingViews": self.routing_views,
            "audit": self.audit,
            "debug": self.debug.to_dict(),
            "warnings": self.warnings,
            "meta": self.meta,
        }


def extract_text_visual_ownership_gate(
    *,
    png_data: bytes,
    source_image: str,
    m2903_document: dict[str, Any],
    m2903_visual_evidence_json_path: str,
    m2902_document: dict[str, Any],
    m2902_audit_json_path: str,
    output_dir: Path,
    options: M2907Options | None = None,
    warnings: list[str] | None = None,
) -> M2907Document:
    options = options or M2907Options()
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)
    text_boxes = valid_text_boxes(m2902_document, pixels.width, pixels.height, options)
    decisions = build_ownership_decisions(m2903_document, text_boxes, pixels.width, pixels.height, options)
    examples: list[dict[str, Any]] = []
    export_examples(pixels, output_dir, decisions, options, examples)
    debug = write_debug_artifacts(pixels, output_dir, decisions)
    preview_path = output_dir / "preview_text_visual_ownership_gate.png"
    preview_path.write_bytes(build_preview_sheet(pixels, output_dir, debug, examples, options))
    document = M2907Document(
        schema_name="M2907TextVisualOwnershipGateDocument",
        schema_version="0.1",
        source_image=source_image,
        source_m2903_visual_evidence_json=m2903_visual_evidence_json_path,
        source_m2902_audit_json=m2902_audit_json_path,
        options=options,
        ownership_decisions=decisions,
        routing_views=build_routing_views(decisions),
        audit=build_audit(decisions),
        debug=debug,
        warnings=warnings or [],
        meta=build_meta(decisions, examples),
    )
    validate_text_visual_ownership_gate_document(document, output_dir, pixels.width, pixels.height, m2903_document, m2902_document)
    write_outputs(document, output_dir)
    return document


def valid_text_boxes(m2902_document: dict[str, Any], width: int, height: int, options: M2907Options) -> list[dict[str, Any]]:
    boxes: list[dict[str, Any]] = []
    for raw in m2902_document.get("textBoxes", []):
        if not isinstance(raw, dict):
            continue
        bbox = parse_bbox(raw.get("bbox"))
        source_id = str(raw.get("id") or "")
        if bbox is None or not source_id or not bbox_in_bounds(bbox, width, height):
            continue
        text = str(raw.get("text") or "").strip()
        boxes.append(
            {
                "id": source_id,
                "bbox": bbox,
                "text": text,
                "textPreview": truncate_text(text, options.text_preview_max_chars),
                "confidence": float(raw.get("confidence", 1.0)),
            }
        )
    return boxes


def build_ownership_decisions(
    m2903_document: dict[str, Any],
    text_boxes: list[dict[str, Any]],
    width: int,
    height: int,
    options: M2907Options,
) -> list[OwnershipDecision]:
    decisions: list[OwnershipDecision] = []
    for raw in m2903_document.get("items", []):
        if not isinstance(raw, dict):
            continue
        bbox = parse_bbox(raw.get("bbox"))
        source_id = str(raw.get("sourceEvidenceId") or "")
        item_id = str(raw.get("id") or "")
        if bbox is None or not item_id or not source_id or not bbox_in_bounds(bbox, width, height):
            continue
        decisions.append(decide_visual_item(f"own_{len(decisions) + 1:04d}", raw, bbox, text_boxes, options))
    for text_box in text_boxes:
        decisions.append(decide_text_box(f"own_{len(decisions) + 1:04d}", text_box, options))
    return decisions


def decide_text_box(id: str, text_box: dict[str, Any], options: M2907Options) -> OwnershipDecision:
    confidence = float(text_box.get("confidence", 1.0))
    return OwnershipDecision(
        id=id,
        source="m2902_text_box",
        source_evidence_id=str(text_box["id"]),
        source_visual_evidence_item_id=None,
        source_text_box_id=str(text_box["id"]),
        source_visual_kind=None,
        bbox=list(text_box["bbox"]),
        ownership="text_owned",
        decision="accepted" if confidence >= options.ocr_confidence_min else "candidate",
        ownership_reason_kind="high_ocr_overlap_text_noise" if confidence >= options.ocr_confidence_min else "low_ocr_confidence",
        matched_text_box_ids=[str(text_box["id"])],
        text_overlap_ratio=1.0,
        ocr_overlap_ratio=1.0,
        text_preview=str(text_box.get("textPreview") or ""),
        ocr_confidence=confidence,
        suppressed_as_visual=False,
        allowed_for_object_forming_visual_side=False,
        allowed_for_text_side=True,
        allowed_for_audit_only=True,
        risks=[] if confidence >= options.ocr_confidence_min else ["low_ocr_confidence"],
        reasons=["m2902_text_box", "text_owned_source"],
    )


def decide_visual_item(id: str, raw: dict[str, Any], bbox: list[int], text_boxes: list[dict[str, Any]], options: M2907Options) -> OwnershipDecision:
    visual_kind = str(raw.get("visualKind") or "")
    source_lineage = raw.get("sourceLineage") if isinstance(raw.get("sourceLineage"), dict) else None
    matched = overlapping_text_boxes(bbox, text_boxes)
    matched_ids = [str(item["id"]) for item in matched]
    ocr_overlap = overlap_with_text_union(bbox, matched, denominator="bbox")
    text_covered = overlap_with_text_union(bbox, matched, denominator="text")
    best_text = max(matched, key=lambda item: float(item.get("confidence", 0.0)), default=None)
    confidence = float(best_text.get("confidence", 0.0)) if best_text else None
    raw_text_overlap = float(raw.get("textOverlapRatio", 0.0))
    text_preview = truncate_text(" ".join(str(item.get("text") or "").strip() for item in matched if str(item.get("text") or "").strip()), options.text_preview_max_chars) if matched else None
    has_good_ocr = confidence is not None and confidence >= options.ocr_confidence_min
    has_text_ownership_overlap = ocr_overlap >= options.text_owned_overlap_min and text_covered >= options.text_owned_text_covered_min

    if visual_kind == "mixed_symbol_text_candidate":
        return make_visual_decision(
            id,
            raw,
            bbox,
            ownership="mixed_or_uncertain",
            decision="uncertain",
            reason_kind="symbol_text_ownership_conflict",
            matched_ids=matched_ids,
            raw_text_overlap=raw_text_overlap,
            ocr_overlap=ocr_overlap,
            text_preview=text_preview,
            ocr_confidence=confidence,
            suppressed=False,
            allow_visual=False,
            allow_text=False,
            risks=["pre_ocr_symbol_lineage_conflict"],
            reasons=["mixed_symbol_text_candidate_audit_only", "pre_ocr_symbol_lineage_preserved"],
        )

    if visual_kind == "text_noise":
        text_noise_risks: list[str] = []
        text_noise_reasons = ["text_noise_owned_by_ocr", "high_ocr_overlap"]
        if lineage_is_text_owned_rejected(source_lineage):
            text_noise_risks.append("text_contamination_possible")
            text_noise_reasons.append("text_owned_rejected_lineage")
        if has_good_ocr and has_text_ownership_overlap:
            return make_visual_decision(
                id,
                raw,
                bbox,
                ownership="text_owned",
                decision="accepted",
                reason_kind="high_ocr_overlap_text_noise",
                matched_ids=matched_ids,
                raw_text_overlap=raw_text_overlap,
                ocr_overlap=ocr_overlap,
                text_preview=text_preview,
                ocr_confidence=confidence,
                suppressed=True,
                allow_visual=False,
                allow_text=True,
                risks=text_noise_risks,
                reasons=text_noise_reasons,
            )
        return make_visual_decision(
            id,
            raw,
            bbox,
            ownership="audit_only" if not matched else "mixed_or_uncertain",
            decision="uncertain",
            reason_kind="low_ocr_confidence" if matched else "missing_text_match",
            matched_ids=matched_ids,
            raw_text_overlap=raw_text_overlap,
            ocr_overlap=ocr_overlap,
            text_preview=text_preview,
            ocr_confidence=confidence,
            suppressed=True,
            allow_visual=False,
            allow_text=False,
            risks=["low_ocr_confidence"] if matched else ["missing_text_match"],
            reasons=["text_noise_not_allowed_as_visual_side"],
        )

    if visual_kind == "icon_candidate":
        if matched and ocr_overlap >= options.visual_candidate_high_text_overlap:
            return make_visual_decision(
                id,
                raw,
                bbox,
                ownership="mixed_or_uncertain",
                decision="uncertain",
                reason_kind="conflicting_ownership",
                matched_ids=matched_ids,
                raw_text_overlap=raw_text_overlap,
                ocr_overlap=ocr_overlap,
                text_preview=text_preview,
                ocr_confidence=confidence,
                suppressed=False,
                allow_visual=True,
                allow_text=False,
                risks=["ocr_overlap_on_visual_candidate"],
                reasons=["icon_candidate_kept_for_visual_review"],
            )
        return visual_owned_decision(id, raw, bbox, matched_ids, raw_text_overlap, ocr_overlap, text_preview, confidence)

    if visual_kind in {"media_candidate", "accepted_image"}:
        risks = ["text_overlay_on_visual"] if matched and ocr_overlap > 0 else []
        return make_visual_decision(
            id,
            raw,
            bbox,
            ownership="visual_owned",
            decision="accepted" if visual_kind == "accepted_image" else "candidate",
            reason_kind="image_with_text_overlay" if risks else "visual_candidate_kept",
            matched_ids=matched_ids,
            raw_text_overlap=raw_text_overlap,
            ocr_overlap=ocr_overlap,
            text_preview=text_preview,
            ocr_confidence=confidence,
            suppressed=False,
            allow_visual=True,
            allow_text=False,
            risks=risks,
            reasons=["visual_image_kept", "text_overlay_recorded"] if risks else ["visual_image_kept"],
        )

    if matched and ocr_overlap >= options.visual_candidate_high_text_overlap:
        return make_visual_decision(
            id,
            raw,
            bbox,
            ownership="mixed_or_uncertain",
            decision="uncertain",
            reason_kind="conflicting_ownership",
            matched_ids=matched_ids,
            raw_text_overlap=raw_text_overlap,
            ocr_overlap=ocr_overlap,
            text_preview=text_preview,
            ocr_confidence=confidence,
            suppressed=False,
            allow_visual=True,
            allow_text=False,
            risks=["ocr_overlap_on_visual_candidate"],
            reasons=["visual_candidate_kept_with_ownership_conflict"],
        )
    return visual_owned_decision(id, raw, bbox, matched_ids, raw_text_overlap, ocr_overlap, text_preview, confidence)


def visual_owned_decision(
    id: str,
    raw: dict[str, Any],
    bbox: list[int],
    matched_ids: list[str],
    raw_text_overlap: float,
    ocr_overlap: float,
    text_preview: str | None,
    confidence: float | None,
) -> OwnershipDecision:
    return make_visual_decision(
        id,
        raw,
        bbox,
        ownership="visual_owned",
        decision="candidate",
        reason_kind="visual_candidate_kept",
        matched_ids=matched_ids,
        raw_text_overlap=raw_text_overlap,
        ocr_overlap=ocr_overlap,
        text_preview=text_preview,
        ocr_confidence=confidence,
        suppressed=False,
        allow_visual=True,
        allow_text=False,
        risks=[],
        reasons=["visual_candidate_kept"],
    )


def make_visual_decision(
    id: str,
    raw: dict[str, Any],
    bbox: list[int],
    *,
    ownership: OwnershipKind,
    decision: OwnershipDecisionKind,
    reason_kind: str,
    matched_ids: list[str],
    raw_text_overlap: float,
    ocr_overlap: float,
    text_preview: str | None,
    ocr_confidence: float | None,
    suppressed: bool,
    allow_visual: bool,
    allow_text: bool,
    risks: list[str],
    reasons: list[str],
) -> OwnershipDecision:
    source_lineage = raw.get("sourceLineage") if isinstance(raw.get("sourceLineage"), dict) else None
    return OwnershipDecision(
        id=id,
        source="m2903_visual_evidence",
        source_evidence_id=str(raw.get("sourceEvidenceId") or ""),
        source_visual_evidence_item_id=str(raw.get("id") or ""),
        source_text_box_id=None,
        source_visual_kind=str(raw.get("visualKind") or ""),
        bbox=bbox,
        ownership=ownership,
        decision=decision,
        ownership_reason_kind=reason_kind,
        matched_text_box_ids=matched_ids,
        text_overlap_ratio=raw_text_overlap,
        ocr_overlap_ratio=ocr_overlap,
        text_preview=text_preview,
        ocr_confidence=ocr_confidence,
        suppressed_as_visual=suppressed,
        allowed_for_object_forming_visual_side=allow_visual,
        allowed_for_text_side=allow_text,
        allowed_for_audit_only=True,
        risks=dedupe_strings(risks),
        reasons=dedupe_strings([*reasons, f"source_visual_kind_{str(raw.get('visualKind') or 'unknown')}"]),
        source_lineage=dict(source_lineage) if source_lineage is not None else None,
    )


def overlapping_text_boxes(bbox: list[int], text_boxes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in text_boxes if intersection_area(bbox, item["bbox"]) > 0]


def overlap_with_text_union(bbox: list[int], text_boxes: list[dict[str, Any]], *, denominator: str) -> float:
    if not text_boxes:
        return 0.0
    intersection = sum(intersection_area(bbox, item["bbox"]) for item in text_boxes)
    if denominator == "text":
        total = sum(bbox_area(item["bbox"]) for item in text_boxes)
    else:
        total = bbox_area(bbox)
    return min(1.0, intersection / max(1, total))


def intersection_area(left: list[int], right: list[int]) -> int:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(bbox_x2(left), bbox_x2(right))
    y2 = min(bbox_y2(left), bbox_y2(right))
    return max(0, x2 - x1) * max(0, y2 - y1)


def build_routing_views(decisions: list[OwnershipDecision]) -> dict[str, Any]:
    return {
        "textOwnedEvidenceIds": [item.id for item in decisions if item.ownership == "text_owned"],
        "visualFormingEvidenceIds": [item.id for item in decisions if item.allowed_for_object_forming_visual_side],
        "auditOnlyEvidenceIds": [item.id for item in decisions if item.ownership == "audit_only"],
        "mixedOrUncertainEvidenceIds": [item.id for item in decisions if item.ownership == "mixed_or_uncertain"],
        "textOverlayOnVisualEvidenceIds": [item.id for item in decisions if item.ownership_reason_kind == "image_with_text_overlay"],
        "bySourceVisualEvidenceItemId": {
            item.source_visual_evidence_item_id: {
                "ownershipDecisionId": item.id,
                "allowedForObjectFormingVisualSide": item.allowed_for_object_forming_visual_side,
                "allowedForTextSide": item.allowed_for_text_side,
                "suppressedAsVisual": item.suppressed_as_visual,
                "ownership": item.ownership,
                "decision": item.decision,
                "ownershipReasonKind": item.ownership_reason_kind,
                "matchedTextBoxIds": item.matched_text_box_ids,
                "textPreview": item.text_preview,
                **({"sourceLineage": item.source_lineage} if item.source_lineage is not None else {}),
            }
            for item in decisions
            if item.source_visual_evidence_item_id
        },
        "byTextBoxId": {
            item.source_text_box_id: {
                "ownershipDecisionId": item.id,
                "allowedForTextSide": item.allowed_for_text_side,
                "ownership": item.ownership,
                "decision": item.decision,
                "textPreview": item.text_preview,
            }
            for item in decisions
            if item.source_text_box_id
        },
    }


def build_audit(decisions: list[OwnershipDecision]) -> list[dict[str, Any]]:
    return [
        {
            "id": f"audit_{index + 1:04d}",
            "ownershipDecisionId": item.id,
            "source": item.source,
            "sourceEvidenceId": item.source_evidence_id,
            "sourceVisualEvidenceItemId": item.source_visual_evidence_item_id,
            "sourceTextBoxId": item.source_text_box_id,
            "ownership": item.ownership,
            "decision": item.decision,
            "ownershipReasonKind": item.ownership_reason_kind,
            "matchedTextBoxIds": item.matched_text_box_ids,
            "suppressedAsVisual": item.suppressed_as_visual,
            "allowedForObjectFormingVisualSide": item.allowed_for_object_forming_visual_side,
            "allowedForTextSide": item.allowed_for_text_side,
            "risks": item.risks,
            "reasons": item.reasons,
            **({"sourceLineage": item.source_lineage} if item.source_lineage is not None else {}),
        }
        for index, item in enumerate(decisions)
    ]


def export_examples(pixels: PngPixels, output_dir: Path, decisions: list[OwnershipDecision], options: M2907Options, examples: list[dict[str, Any]]) -> None:
    counts: dict[str, int] = {}
    folder_by_ownership = {
        "text_owned": "text_owned_examples",
        "visual_owned": "visual_owned_examples",
        "mixed_or_uncertain": "mixed_or_uncertain_examples",
        "audit_only": "audit_only_examples",
        "shape_owned": "audit_only_examples",
    }
    for item in decisions:
        folder = folder_by_ownership[item.ownership]
        count = counts.get(item.ownership, 0)
        if count >= options.max_examples_per_kind:
            continue
        counts[item.ownership] = count + 1
        target = output_dir / "assets" / folder
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"{item.ownership}_{count + 1:04d}_{item.id}.png"
        path.write_bytes(crop_pixels(pixels, item.bbox))
        examples.append({"ownershipDecisionId": item.id, "ownership": item.ownership, "bbox": item.bbox, "assetPath": str(path.relative_to(output_dir))})


def write_debug_artifacts(pixels: PngPixels, output_dir: Path, decisions: list[OwnershipDecision]) -> M2907DebugArtifacts:
    overlay_dir = output_dir / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "textOwned": overlay_dir / "29_text_owned.png",
        "visualOwned": overlay_dir / "30_visual_owned.png",
        "mixedOrUncertain": overlay_dir / "31_mixed_or_uncertain.png",
        "objectFormingAllowed": overlay_dir / "32_object_forming_allowed.png",
    }
    paths["textOwned"].write_bytes(overlay_decisions(pixels, decisions, lambda item: item.ownership == "text_owned", (235, 64, 52)))
    paths["visualOwned"].write_bytes(overlay_decisions(pixels, decisions, lambda item: item.ownership == "visual_owned", (0, 122, 255)))
    paths["mixedOrUncertain"].write_bytes(overlay_decisions(pixels, decisions, lambda item: item.ownership == "mixed_or_uncertain", (238, 140, 40)))
    paths["objectFormingAllowed"].write_bytes(overlay_decisions(pixels, decisions, lambda item: item.allowed_for_object_forming_visual_side, (0, 180, 90)))
    return M2907DebugArtifacts(
        text_owned=str(paths["textOwned"].relative_to(output_dir)),
        visual_owned=str(paths["visualOwned"].relative_to(output_dir)),
        mixed_or_uncertain=str(paths["mixedOrUncertain"].relative_to(output_dir)),
        object_forming_allowed=str(paths["objectFormingAllowed"].relative_to(output_dir)),
    )


def overlay_decisions(pixels: PngPixels, decisions: list[OwnershipDecision], include: Any, color: tuple[int, int, int]) -> bytes:
    rows = [bytearray(row) for row in pixels.rows]
    for item in decisions:
        if include(item):
            draw_rect(rows, pixels.width, pixels.height, item.bbox, color, 2)
    return encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows])


def build_preview_sheet(pixels: PngPixels, output_dir: Path, debug: M2907DebugArtifacts, examples: list[dict[str, Any]], options: M2907Options) -> bytes:
    overlays = [decode_png_pixels((output_dir / path).read_bytes()) for path in debug.to_dict().values()]
    sheet_width = 1400
    margin = 24
    gap = 18
    top_scale = min(0.32, (sheet_width - margin * 2 - gap * 4) / max(1, pixels.width * 5))
    top_w = max(1, round(pixels.width * top_scale))
    top_h = max(1, round(pixels.height * top_scale))
    previews = crop_previews(output_dir, examples, options.output_preview_max_thumb)
    grid_h = grid_height(previews, sheet_width, margin, gap)
    sheet_height = margin + top_h + margin + grid_h + margin
    canvas = [bytearray(b"\xfa\xfa\xfa" * sheet_width) for _ in range(sheet_height)]
    x = margin
    for image in [pixels, *overlays]:
        paste_scaled(canvas, sheet_width, image, x, margin, top_w, top_h)
        x += top_w + gap
    paste_grid(canvas, sheet_width, previews, margin, margin + top_h + margin, gap)
    return encode_rgb_png(sheet_width, sheet_height, [bytes(row) for row in canvas])


def crop_previews(output_dir: Path, examples: list[dict[str, Any]], max_edge: int) -> list[tuple[str, PngPixels, int, int]]:
    previews: list[tuple[str, PngPixels, int, int]] = []
    for example in examples[:160]:
        path = str(example.get("assetPath") or "")
        if not path:
            continue
        try:
            crop = decode_png_pixels((output_dir / path).read_bytes())
        except UnsupportedPngCropError:
            continue
        scale = min(1.0, max_edge / max(1, crop.width, crop.height))
        previews.append((str(example.get("ownership") or ""), crop, max(1, round(crop.width * scale)), max(1, round(crop.height * scale))))
    return previews


def write_outputs(document: M2907Document, output_dir: Path) -> None:
    payload = document.to_dict()
    (output_dir / "text_visual_ownership_gate.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "text_visual_ownership_audit.json").write_text(json.dumps(document.audit, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "text_owned_evidence.json").write_text(json.dumps([item.to_dict() for item in document.ownership_decisions if item.ownership == "text_owned"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "visual_forming_evidence.json").write_text(json.dumps([item.to_dict() for item in document.ownership_decisions if item.allowed_for_object_forming_visual_side], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "audit_only_evidence.json").write_text(json.dumps([item.to_dict() for item in document.ownership_decisions if item.ownership == "audit_only"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "text_overlay_on_visual.json").write_text(json.dumps([item.to_dict() for item in document.ownership_decisions if item.ownership_reason_kind == "image_with_text_overlay"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "text_visual_ownership_gate.md").write_text(build_markdown_report(document), encoding="utf-8")


def build_markdown_report(document: M2907Document) -> str:
    lines = [
        "# M29.0.7 Text Visual Ownership Gate",
        "",
        f"- Source M29.0.3: `{document.source_m2903_visual_evidence_json}`",
        f"- Source M29.0.2: `{document.source_m2902_audit_json}`",
        f"- Decisions: {len(document.ownership_decisions)}",
        f"- Ownership counts: `{document.meta.get('ownershipCounts', {})}`",
        f"- Reason counts: `{document.meta.get('ownershipReasonKindCounts', {})}`",
        "",
        "## Top Decisions",
        "",
    ]
    for item in document.ownership_decisions[:120]:
        lines.append(f"- `{item.id}` `{item.ownership}` `{item.decision}` source=`{item.source}` sourceId=`{item.source_visual_evidence_item_id or item.source_text_box_id}` bbox={item.bbox} reason=`{item.ownership_reason_kind}` visualSide={item.allowed_for_object_forming_visual_side} textSide={item.allowed_for_text_side}")
    return "\n".join(lines).rstrip() + "\n"


def validate_text_visual_ownership_gate_document(document: M2907Document, output_dir: Path, width: int, height: int, m2903_document: dict[str, Any], m2902_document: dict[str, Any]) -> None:
    if document.schema_name != "M2907TextVisualOwnershipGateDocument" or document.schema_version != "0.1":
        raise ValueError("invalid M29.0.7 document schema")
    assert_unique([item.id for item in document.ownership_decisions], "ownership decision")
    visual_ids = {str(item.get("id")) for item in m2903_document.get("items", []) if isinstance(item, dict) and item.get("id")}
    source_ids = {str(item.get("sourceEvidenceId")) for item in m2903_document.get("items", []) if isinstance(item, dict) and item.get("sourceEvidenceId")}
    text_ids = {str(item.get("id")) for item in m2902_document.get("textBoxes", []) if isinstance(item, dict) and item.get("id")}
    for item in document.ownership_decisions:
        if not bbox_in_bounds(item.bbox, width, height):
            raise ValueError(f"M29.0.7 decision bbox out of bounds: {item.id}")
        if item.source == "m2903_visual_evidence":
            if item.source_visual_evidence_item_id not in visual_ids or item.source_evidence_id not in source_ids:
                raise ValueError(f"M29.0.7 decision references missing visual evidence: {item.id}")
        elif item.source == "m2902_text_box":
            if item.source_text_box_id not in text_ids:
                raise ValueError(f"M29.0.7 decision references missing text box: {item.id}")
        else:
            raise ValueError(f"M29.0.7 illegal source: {item.id}")
        if item.ownership == "text_owned" and item.allowed_for_object_forming_visual_side:
            raise ValueError(f"M29.0.7 text-owned decision cannot allow visual side: {item.id}")
        if item.suppressed_as_visual and item.allowed_for_object_forming_visual_side:
            raise ValueError(f"M29.0.7 suppressed visual cannot allow visual side: {item.id}")
    for path in document.debug.to_dict().values():
        metadata = assert_readable_relative_png(output_dir, path)
        if metadata.width != width or metadata.height != height:
            raise ValueError(f"M29.0.7 overlay dimensions do not match source image: {path}")
    assert_readable_relative_png(output_dir, "preview_text_visual_ownership_gate.png")


def build_meta(decisions: list[OwnershipDecision], examples: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "notes": "m29_0_7_text_visual_ownership_gate",
        "decisionCount": len(decisions),
        "exampleCount": len(examples),
        "ownershipCounts": count_by(decisions, lambda item: item.ownership),
        "decisionCounts": count_by(decisions, lambda item: item.decision),
        "ownershipReasonKindCounts": count_by(decisions, lambda item: item.ownership_reason_kind),
        "objectFormingVisualAllowedCount": sum(1 for item in decisions if item.allowed_for_object_forming_visual_side),
        "textSideAllowedCount": sum(1 for item in decisions if item.allowed_for_text_side),
        "suppressedAsVisualCount": sum(1 for item in decisions if item.suppressed_as_visual),
    }


def count_by(items: list[Any], key_fn: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = str(key_fn(item))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def assert_unique(values: list[str], label: str) -> set[str]:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"duplicate M29.0.7 {label} id: {value}")
        seen.add(value)
    return seen


def assert_readable_relative_png(output_dir: Path, path: str):
    resolved = output_dir / path
    if not resolved.exists():
        raise ValueError(f"M29.0.7 PNG output missing or unreadable: {path}")
    metadata = read_png_metadata(resolved.read_bytes())
    if metadata is None:
        raise ValueError(f"M29.0.7 PNG output missing or unreadable: {path}")
    return metadata


def truncate_text(text: str | None, max_chars: int) -> str | None:
    if text is None:
        return None
    return text if len(text) <= max_chars else text[:max_chars] + "..."


def dedupe_strings(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def lineage_is_text_owned_rejected(source_lineage: dict[str, Any] | None) -> bool:
    if not isinstance(source_lineage, dict):
        return False
    return (
        source_lineage.get("conflictClass") == "text_owned_rejected_lineage"
        or source_lineage.get("rejectedLineageReason") == "text_owned_rejected_lineage"
    )


def grid_height(previews: list[tuple[str, PngPixels, int, int]], sheet_width: int, margin: int, gap: int) -> int:
    if not previews:
        return 48
    x = margin
    row_h = 0
    total = 0
    for _label, _pixels, width, height in previews:
        if x + width > sheet_width - margin:
            total += row_h + gap
            x = margin
            row_h = 0
        row_h = max(row_h, height)
        x += width + gap
    return total + row_h


def paste_grid(canvas: list[bytearray], sheet_width: int, previews: list[tuple[str, PngPixels, int, int]], x: int, y: int, gap: int) -> int:
    row_h = 0
    margin = x
    if not previews:
        fill_rect(canvas, sheet_width, x, y, sheet_width - x * 2, 48, (232, 232, 232))
        return y + 48
    for label, preview, width, height in previews:
        if x + width > sheet_width - margin:
            y += row_h + gap
            x = margin
            row_h = 0
        fill_rect(canvas, sheet_width, x - 4, y - 4, width + 8, height + 8, frame_color(label))
        fill_rect(canvas, sheet_width, x - 2, y - 2, width + 4, height + 4, (244, 244, 244))
        paste_scaled(canvas, sheet_width, preview, x, y, width, height)
        x += width + gap
        row_h = max(row_h, height)
    return y + row_h


def paste_scaled(canvas: list[bytearray], sheet_width: int, source: PngPixels, x: int, y: int, target_width: int, target_height: int) -> None:
    for target_y in range(target_height):
        source_y = min(source.height - 1, round(target_y * source.height / target_height))
        if y + target_y < 0 or y + target_y >= len(canvas):
            continue
        source_row = source.rows[source_y]
        target_row = canvas[y + target_y]
        for target_x in range(target_width):
            source_x = min(source.width - 1, round(target_x * source.width / target_width))
            dst_x = x + target_x
            if 0 <= dst_x < sheet_width:
                target_row[dst_x * 3 : dst_x * 3 + 3] = source_row[source_x * 3 : source_x * 3 + 3]


def fill_rect(canvas: list[bytearray], sheet_width: int, x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> None:
    color_bytes = bytes(color)
    for row_index in range(max(0, y), min(len(canvas), y + height)):
        row = canvas[row_index]
        for column in range(max(0, x), min(sheet_width, x + width)):
            row[column * 3 : column * 3 + 3] = color_bytes


def frame_color(label: str) -> tuple[int, int, int]:
    if label == "text_owned":
        return (235, 64, 52)
    if label == "visual_owned":
        return (0, 122, 255)
    if label == "mixed_or_uncertain":
        return (238, 140, 40)
    return (170, 170, 170)
