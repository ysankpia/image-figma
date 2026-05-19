from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from .png_tools import PngPixels, decode_png_pixels, encode_rgb_png, read_png_metadata
from .visual_evidence_normalization import parse_bbox
from .visual_primitive_graph import bbox_area, bbox_in_bounds, bbox_iou, crop_pixels, draw_rect


LineageStrength = Literal["weak", "medium", "strong"]
LineageLossStage = Literal["m29_1", "m29_0_2", "m29_0_3", "m29_0_7"]


@dataclass(frozen=True)
class PreOcrSymbolLineageAuditOptions:
    match_iou_min: float = 0.55
    max_examples_per_kind: int = 40

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LineageFinding:
    id: str
    finding_kind: str
    m29_node_id: str | None
    m29_blocked_id: str | None
    m291_candidate_id: str | None
    m291_group_id: str | None
    matched_m2902_media_evidence_id: str | None
    matched_m2903_visual_evidence_item_id: str | None
    matched_m2907_ownership_decision_id: str | None
    bbox: list[int]
    lineage_strength: LineageStrength
    lineage_loss_stage: LineageLossStage
    later_visual_kind: str | None
    later_ownership: str | None
    reasons: list[str]
    risks: list[str]
    example_asset_paths: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "findingKind": self.finding_kind,
            "sourceM29NodeId": self.m29_node_id,
            "sourceM29BlockedId": self.m29_blocked_id,
            "sourceM291CandidateId": self.m291_candidate_id,
            "sourceM291GroupId": self.m291_group_id,
            "matchedM2902MediaEvidenceId": self.matched_m2902_media_evidence_id,
            "matchedM2903VisualEvidenceItemId": self.matched_m2903_visual_evidence_item_id,
            "matchedM2907OwnershipDecisionId": self.matched_m2907_ownership_decision_id,
            "bbox": self.bbox,
            "lineageStrength": self.lineage_strength,
            "lineageLossStage": self.lineage_loss_stage,
            "laterVisualKind": self.later_visual_kind,
            "laterOwnership": self.later_ownership,
            "reasons": self.reasons,
            "risks": self.risks,
            "exampleAssetPaths": self.example_asset_paths,
        }


@dataclass(frozen=True)
class PreOcrSymbolLineageAuditDocument:
    schema_name: str
    schema_version: str
    source_image: str
    source_m29_nodes_json: str
    source_m291_group_nodes_json: str | None
    source_m2902_audit_json: str | None
    source_m2903_visual_evidence_json: str | None
    source_m2907_ownership_json: str | None
    options: PreOcrSymbolLineageAuditOptions
    findings: list[LineageFinding]
    summary: dict[str, Any]
    debug: dict[str, str]
    warnings: list[str]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaName": self.schema_name,
            "schemaVersion": self.schema_version,
            "sourceImage": self.source_image,
            "sourceM29NodesJson": self.source_m29_nodes_json,
            "sourceM291GroupNodesJson": self.source_m291_group_nodes_json,
            "sourceM2902AuditJson": self.source_m2902_audit_json,
            "sourceM2903VisualEvidenceJson": self.source_m2903_visual_evidence_json,
            "sourceM2907OwnershipJson": self.source_m2907_ownership_json,
            "options": self.options.to_dict(),
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
            "debug": self.debug,
            "warnings": self.warnings,
            "meta": self.meta,
        }


def extract_pre_ocr_symbol_lineage_audit(
    *,
    png_data: bytes,
    source_image: str,
    m29_document: dict[str, Any],
    m29_nodes_json_path: str,
    output_dir: Path,
    m291_document: dict[str, Any] | None = None,
    m291_group_nodes_json_path: str | None = None,
    m2902_document: dict[str, Any] | None = None,
    m2902_audit_json_path: str | None = None,
    m2903_document: dict[str, Any] | None = None,
    m2903_visual_evidence_json_path: str | None = None,
    m2907_document: dict[str, Any] | None = None,
    m2907_ownership_json_path: str | None = None,
    options: PreOcrSymbolLineageAuditOptions | None = None,
    warnings: list[str] | None = None,
) -> PreOcrSymbolLineageAuditDocument:
    options = options or PreOcrSymbolLineageAuditOptions()
    pixels = decode_png_pixels(png_data)
    output_dir.mkdir(parents=True, exist_ok=True)
    source_records = collect_lineage_sources(m29_document, m291_document, pixels.width, pixels.height)
    m2902_items = [item for item in (m2902_document or {}).get("mediaEvidence", []) if isinstance(item, dict)]
    m2903_items = [item for item in (m2903_document or {}).get("items", []) if isinstance(item, dict)]
    m2907_items = [item for item in (m2907_document or {}).get("ownershipDecisions", []) if isinstance(item, dict)]
    findings = build_findings(source_records, m2902_items, m2903_items, m2907_items, options)
    export_examples(pixels, output_dir, findings, options)
    overlay_path = write_overlay(pixels, output_dir, findings)
    document = PreOcrSymbolLineageAuditDocument(
        schema_name="M2911PreOcrSymbolLineageAuditDocument",
        schema_version="0.1",
        source_image=source_image,
        source_m29_nodes_json=m29_nodes_json_path,
        source_m291_group_nodes_json=m291_group_nodes_json_path,
        source_m2902_audit_json=m2902_audit_json_path,
        source_m2903_visual_evidence_json=m2903_visual_evidence_json_path,
        source_m2907_ownership_json=m2907_ownership_json_path,
        options=options,
        findings=findings,
        summary=build_summary(findings, source_records),
        debug={"preOcrSymbolLineage": overlay_path},
        warnings=warnings or [],
        meta={"notes": "m29_1_1_pre_ocr_symbol_lineage_audit", "findingCount": len(findings), "lineageSourceCount": len(source_records)},
    )
    validate_pre_ocr_symbol_lineage_audit_document(document, output_dir, pixels.width, pixels.height)
    write_outputs(document, output_dir)
    return document


def collect_lineage_sources(m29_document: dict[str, Any], m291_document: dict[str, Any] | None, width: int, height: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    grouped_source_ids: set[str] = set()
    for group in (m291_document or {}).get("groups", []):
        if not isinstance(group, dict):
            continue
        bbox = parse_bbox(group.get("bbox"))
        if bbox is None or not bbox_in_bounds(bbox, width, height):
            continue
        lineage = group.get("sourceLineage") if isinstance(group.get("sourceLineage"), dict) else None
        rejected = str(group.get("rejectedLineageReason") or "")
        for member in group.get("members", []):
            if isinstance(member, dict) and member.get("sourceNodeId"):
                grouped_source_ids.add(str(member.get("sourceNodeId")))
        if lineage is None and not rejected:
            continue
        records.append(
            {
                "source": "m291_group",
                "m291GroupId": str(group.get("id") or ""),
                "m291CandidateId": None,
                "m29NodeId": first_string((lineage or {}).get("m29NodeIds")),
                "m29BlockedId": first_string((lineage or {}).get("m29BlockedIds")),
                "bbox": bbox,
                "lineage": lineage or {"rejectedLineageReason": rejected, "preOcrSymbolCandidate": False, "lineageStrength": "weak"},
                "lineageStrength": str((lineage or {}).get("lineageStrength") or "weak"),
                "rejectedLineageReason": rejected or None,
                "reasons": [str(reason) for reason in group.get("reasons", [])],
                "risks": [str(risk) for risk in (lineage or {}).get("risks", [])],
            }
        )
    for candidate in (m291_document or {}).get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        bbox = parse_bbox(candidate.get("bbox"))
        lineage = candidate.get("sourceLineage") if isinstance(candidate.get("sourceLineage"), dict) else None
        source_node_id = str(candidate.get("sourceNodeId") or "")
        if bbox is None or lineage is None or not bbox_in_bounds(bbox, width, height) or source_node_id in grouped_source_ids:
            continue
        source_kind = str(candidate.get("sourceKind") or "")
        records.append(
            {
                "source": "m291_candidate",
                "m291GroupId": None,
                "m291CandidateId": str(candidate.get("id") or ""),
                "m29NodeId": source_node_id if source_kind == "symbol" else None,
                "m29BlockedId": source_node_id if source_kind == "blocked" else None,
                "bbox": bbox,
                "lineage": lineage,
                "lineageStrength": str(lineage.get("lineageStrength") or "weak"),
                "rejectedLineageReason": None,
                "reasons": [str(reason) for reason in candidate.get("riskReasons", [])],
                "risks": [str(risk) for risk in lineage.get("risks", [])],
            }
        )
    grouped_or_candidate_ids = {str(record.get("m29NodeId") or record.get("m29BlockedId") or "") for record in records}
    for item in m29_document.get("blocked", []):
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("id") or "")
        bbox = parse_bbox(item.get("bbox"))
        reasons = [str(reason) for reason in item.get("reasons", [])]
        if not source_id or bbox is None or source_id in grouped_or_candidate_ids or not bbox_in_bounds(bbox, width, height):
            continue
        if not any(reason in {"weak_symbol_metrics", "symbol_color_too_high", "symbol_texture_too_high", "symbol_edge_too_high", "symbol_area_too_small"} for reason in reasons):
            continue
        records.append(
            {
                "source": "m29_blocked",
                "m291GroupId": None,
                "m291CandidateId": None,
                "m29NodeId": None,
                "m29BlockedId": source_id,
                "bbox": bbox,
                "lineage": {"preOcrSymbolCandidate": True, "lineageStrength": "weak", "lineageSource": "eligible_blocked", "ownershipHint": "visual_or_mixed"},
                "lineageStrength": "weak",
                "rejectedLineageReason": None,
                "reasons": reasons,
                "risks": ["eligible_blocked_not_grouped"],
            }
        )
    return records


def build_findings(
    source_records: list[dict[str, Any]],
    m2902_items: list[dict[str, Any]],
    m2903_items: list[dict[str, Any]],
    m2907_items: list[dict[str, Any]],
    options: PreOcrSymbolLineageAuditOptions,
) -> list[LineageFinding]:
    findings: list[LineageFinding] = []
    for record in source_records:
        m2902 = best_bbox_match(record["bbox"], m2902_items, options.match_iou_min)
        m2903 = best_visual_match(m2902, record["bbox"], m2903_items, options.match_iou_min)
        m2907 = best_ownership_match(m2903, record["bbox"], m2907_items, options.match_iou_min)
        finding_kind = classify_finding_kind(record, m2902, m2903, m2907)
        if finding_kind is None:
            continue
        findings.append(
            LineageFinding(
                id=f"lineage_finding_{len(findings) + 1:04d}",
                finding_kind=finding_kind,
                m29_node_id=record.get("m29NodeId"),
                m29_blocked_id=record.get("m29BlockedId"),
                m291_candidate_id=record.get("m291CandidateId"),
                m291_group_id=record.get("m291GroupId"),
                matched_m2902_media_evidence_id=str(m2902.get("id")) if m2902 else None,
                matched_m2903_visual_evidence_item_id=str(m2903.get("id")) if m2903 else None,
                matched_m2907_ownership_decision_id=str(m2907.get("id")) if m2907 else None,
                bbox=list(record["bbox"]),
                lineage_strength=parse_lineage_strength(record.get("lineageStrength")),
                lineage_loss_stage=lineage_loss_stage(record, m2902, m2903, m2907),
                later_visual_kind=str(m2903.get("visualKind")) if m2903 else None,
                later_ownership=str(m2907.get("ownership")) if m2907 else None,
                reasons=dedupe_strings([*record.get("reasons", []), *later_reasons(m2902, m2903, m2907)]),
                risks=dedupe_strings([*record.get("risks", []), *later_risks(m2902, m2903, m2907)]),
                example_asset_paths=[],
            )
        )
    return findings


def classify_finding_kind(record: dict[str, Any], m2902: dict[str, Any] | None, m2903: dict[str, Any] | None, m2907: dict[str, Any] | None) -> str | None:
    if record.get("rejectedLineageReason") == "text_like_glyph_sequence":
        return "text_like_glyph_sequence"
    if record.get("source") == "m29_blocked":
        return "eligible_blocked_not_grouped"
    if record.get("source") == "m291_candidate" and record.get("m29BlockedId"):
        return "compact_icon_like_blocked"
    later_visual_kind = str((m2903 or {}).get("visualKind") or "")
    later_ownership = str((m2907 or {}).get("ownership") or "")
    if later_visual_kind == "text_noise" and later_ownership == "text_owned":
        return "visual_lineage_lost_after_text_mask"
    if later_visual_kind == "text_noise":
        if record.get("m291GroupId") and str(record.get("lineageStrength")) == "strong":
            return "accepted_symbol_later_demoted"
        if record.get("m291GroupId"):
            return "uncertain_group_later_demoted"
        return "visual_lineage_lost_after_text_mask"
    if later_visual_kind == "mixed_symbol_text_candidate" or later_ownership == "mixed_or_uncertain":
        return "symbol_text_ownership_conflict"
    if record.get("source") == "m291_candidate":
        return "anchorless_symbol_fragment"
    return None


def lineage_loss_stage(record: dict[str, Any], m2902: dict[str, Any] | None, m2903: dict[str, Any] | None, m2907: dict[str, Any] | None) -> LineageLossStage:
    if m2907 is not None and bool(m2907.get("suppressedAsVisual")):
        return "m29_0_7"
    if m2903 is not None and str(m2903.get("visualKind") or "") == "text_noise":
        return "m29_0_3"
    if m2902 is not None:
        return "m29_0_2"
    return "m29_1"


def best_visual_match(m2902: dict[str, Any] | None, bbox: list[int], m2903_items: list[dict[str, Any]], min_iou: float) -> dict[str, Any] | None:
    if m2902 is not None:
        source_id = str(m2902.get("id") or "")
        for item in m2903_items:
            if str(item.get("sourceEvidenceId") or "") == source_id:
                return item
    return best_bbox_match(bbox, m2903_items, min_iou)


def best_ownership_match(m2903: dict[str, Any] | None, bbox: list[int], m2907_items: list[dict[str, Any]], min_iou: float) -> dict[str, Any] | None:
    if m2903 is not None:
        source_id = str(m2903.get("id") or "")
        for item in m2907_items:
            if str(item.get("sourceVisualEvidenceItemId") or "") == source_id:
                return item
    return best_bbox_match(bbox, m2907_items, min_iou)


def best_bbox_match(bbox: list[int], items: list[dict[str, Any]], min_iou: float) -> dict[str, Any] | None:
    best: tuple[float, dict[str, Any]] | None = None
    for item in items:
        other = parse_bbox(item.get("bbox"))
        if other is None:
            continue
        score = max(bbox_iou(bbox, other), intersection_over_smaller(bbox, other))
        if score >= min_iou and (best is None or score > best[0]):
            best = (score, item)
    return best[1] if best else None


def intersection_over_smaller(left: list[int], right: list[int]) -> float:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(left[0] + left[2], right[0] + right[2])
    y2 = min(left[1] + left[3], right[1] + right[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    return intersection / max(1, min(bbox_area(left), bbox_area(right)))


def export_examples(
    pixels: PngPixels,
    output_dir: Path,
    findings: list[LineageFinding],
    options: PreOcrSymbolLineageAuditOptions,
) -> None:
    folder_by_kind = {
        "text_like_glyph_sequence": "text_like_glyph_examples",
        "symbol_text_ownership_conflict": "mixed_conflict_examples",
    }
    counts: dict[str, int] = {}
    for index, finding in enumerate(findings):
        count = counts.get(finding.finding_kind, 0)
        if count >= options.max_examples_per_kind:
            continue
        counts[finding.finding_kind] = count + 1
        folder = folder_by_kind.get(finding.finding_kind, "lineage_lost_examples")
        target_dir = output_dir / "assets" / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{finding.finding_kind}_{count + 1:04d}_{finding.id}.png"
        path.write_bytes(crop_pixels(pixels, finding.bbox))
        findings[index] = LineageFinding(**{**finding.__dict__, "example_asset_paths": [str(path.relative_to(output_dir))]})


def write_overlay(pixels: PngPixels, output_dir: Path, findings: list[LineageFinding]) -> str:
    rows = [bytearray(row) for row in pixels.rows]
    colors = {
        "visual_lineage_lost_after_text_mask": (235, 64, 52),
        "eligible_blocked_not_grouped": (238, 190, 40),
        "accepted_symbol_later_demoted": (235, 64, 52),
        "uncertain_group_later_demoted": (238, 140, 40),
        "anchorless_symbol_fragment": (120, 120, 120),
        "compact_icon_like_blocked": (0, 122, 255),
        "text_like_glyph_sequence": (160, 80, 220),
        "symbol_text_ownership_conflict": (0, 180, 90),
    }
    for finding in findings:
        draw_rect(rows, pixels.width, pixels.height, finding.bbox, colors.get(finding.finding_kind, (60, 60, 60)), 3 if finding.lineage_strength == "strong" else 2)
    path = output_dir / "overlay_pre_ocr_symbol_lineage.png"
    path.write_bytes(encode_rgb_png(pixels.width, pixels.height, [bytes(row) for row in rows]))
    return str(path.relative_to(output_dir))


def build_summary(findings: list[LineageFinding], source_records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "lineageSourceCount": len(source_records),
        "findingCount": len(findings),
        "byFindingKind": count_by([finding.finding_kind for finding in findings]),
        "byLineageLossStage": count_by([finding.lineage_loss_stage for finding in findings]),
        "byLaterVisualKind": count_by([finding.later_visual_kind or "missing" for finding in findings]),
        "byLaterOwnership": count_by([finding.later_ownership or "missing" for finding in findings]),
    }


def write_outputs(document: PreOcrSymbolLineageAuditDocument, output_dir: Path) -> None:
    payload = document.to_dict()
    (output_dir / "pre_ocr_symbol_lineage_audit.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "pre_ocr_symbol_lineage_audit.md").write_text(build_markdown_report(document), encoding="utf-8")


def build_markdown_report(document: PreOcrSymbolLineageAuditDocument) -> str:
    lines = [
        "# M29.1.1 Pre-OCR Symbol Lineage Audit",
        "",
        f"- Source M29: `{document.source_m29_nodes_json}`",
        f"- Source M29.1: `{document.source_m291_group_nodes_json}`",
        f"- Findings: {len(document.findings)}",
        f"- By kind: `{document.summary.get('byFindingKind', {})}`",
        f"- By loss stage: `{document.summary.get('byLineageLossStage', {})}`",
        "",
        "## Findings",
        "",
    ]
    for finding in document.findings[:160]:
        lines.append(
            f"- `{finding.id}` `{finding.finding_kind}` stage=`{finding.lineage_loss_stage}` "
            f"strength=`{finding.lineage_strength}` bbox={finding.bbox} "
            f"m2903=`{finding.matched_m2903_visual_evidence_item_id}` later=`{finding.later_visual_kind}` "
            f"ownership=`{finding.later_ownership}`"
        )
    return "\n".join(lines).rstrip() + "\n"


def validate_pre_ocr_symbol_lineage_audit_document(document: PreOcrSymbolLineageAuditDocument, output_dir: Path, width: int, height: int) -> None:
    if document.schema_name != "M2911PreOcrSymbolLineageAuditDocument" or document.schema_version != "0.1":
        raise ValueError("invalid M29.1.1 document schema")
    ids: set[str] = set()
    for finding in document.findings:
        if finding.id in ids:
            raise ValueError(f"duplicate M29.1.1 finding id: {finding.id}")
        ids.add(finding.id)
        if not bbox_in_bounds(finding.bbox, width, height):
            raise ValueError(f"M29.1.1 finding bbox out of bounds: {finding.id}")
        for path in finding.example_asset_paths:
            assert_readable_relative_png(output_dir, path)
    for path in document.debug.values():
        metadata = assert_readable_relative_png(output_dir, path)
        if metadata.width != width or metadata.height != height:
            raise ValueError(f"M29.1.1 overlay dimensions do not match source image: {path}")


def assert_readable_relative_png(output_dir: Path, path: str):
    resolved = output_dir / path
    metadata = read_png_metadata(resolved.read_bytes()) if resolved.exists() else None
    if metadata is None:
        raise ValueError(f"M29.1.1 PNG output missing or unreadable: {path}")
    return metadata


def later_reasons(*items: dict[str, Any] | None) -> list[str]:
    reasons: list[str] = []
    for item in items:
        if not item:
            continue
        reasons.extend(str(reason) for reason in item.get("reasons", []))
        reason = item.get("ownershipReasonKind")
        if reason:
            reasons.append(str(reason))
    return reasons


def later_risks(*items: dict[str, Any] | None) -> list[str]:
    risks: list[str] = []
    for item in items:
        if not item:
            continue
        risks.extend(str(risk) for risk in item.get("risks", []))
        if bool(item.get("suppressedAsVisual")):
            risks.append("suppressed_as_visual")
    return risks


def parse_lineage_strength(value: object) -> LineageStrength:
    if value in {"weak", "medium", "strong"}:
        return value  # type: ignore[return-value]
    return "weak"


def count_by(items: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def dedupe_strings(items: list[str]) -> list[str]:
    output: list[str] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output


def first_string(value: object) -> str | None:
    if isinstance(value, list) and value:
        return str(value[0])
    return None
