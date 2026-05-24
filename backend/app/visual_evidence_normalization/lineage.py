from __future__ import annotations

from typing import Any

from .parsing import parse_bbox
from .text_overlap import dedupe_strings


def rejected_lineage(source_lineage: dict[str, Any] | None, reason: str, counter_evidence: list[str] | None = None) -> dict[str, Any] | None:
    if not isinstance(source_lineage, dict):
        return source_lineage
    rejected = dict(source_lineage)
    rejected["rejectedLineageReason"] = reason
    rejected["conflictClass"] = "text_owned_rejected_lineage"
    rejected["ownershipHint"] = "text_owned"
    rejected["survivingPreOcrSymbolCandidate"] = False
    rejected["counterEvidence"] = dedupe_strings([*rejected.get("counterEvidence", []), *(counter_evidence or [])])
    rejected["risks"] = dedupe_strings([*rejected.get("risks", []), "text_contamination_possible"])
    rejected["reasons"] = dedupe_strings([*rejected.get("reasons", []), reason])
    return rejected

def lineage_survives_as_conflict(source_lineage: dict[str, Any] | None) -> bool:
    if not isinstance(source_lineage, dict):
        return False
    if source_lineage.get("rejectedLineageReason"):
        return False
    return bool(source_lineage.get("preOcrSymbolCandidate"))

def lineage_is_rejected_text_like(source_lineage: dict[str, Any] | None) -> bool:
    if not isinstance(source_lineage, dict):
        return False
    reason = str(source_lineage.get("rejectedLineageReason") or "")
    return reason in {"text_like_glyph_sequence", "image_like_merged_result"}

def build_lineage_lookup(document: dict[str, Any] | None) -> dict[str, dict[str, Any]] | None:
    if document is None:
        return None
    if document.get("schemaName") != "M291SymbolFragmentGroupingDocument" or document.get("schemaVersion") != "0.1":
        raise ValueError("M29.0.3 lineage input must be M291SymbolFragmentGroupingDocument v0.1")
    lookup: dict[str, dict[str, Any]] = {}
    candidate_bboxes_by_id = {
        str(candidate.get("id")): bbox
        for candidate in document.get("candidates", [])
        if isinstance(candidate, dict) and candidate.get("id") and (bbox := parse_bbox(candidate.get("bbox"))) is not None
    }
    for candidate in document.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        lineage = normalized_lineage(candidate.get("sourceLineage"), candidate)
        if lineage is None:
            continue
        lineage = attach_candidate_bboxes(lineage, candidate_bboxes_by_id)
        bbox = parse_bbox(candidate.get("bbox"))
        source_node_id = str(candidate.get("sourceNodeId") or "")
        source_kind = str(candidate.get("sourceKind") or "")
        if source_node_id:
            if source_kind == "symbol":
                lookup[f"source_node:m29_symbol:{source_node_id}"] = lineage
            elif source_kind == "blocked":
                lookup[f"source_node:m29_blocked:{source_node_id}"] = lineage
        if bbox is not None:
            lookup.setdefault(bbox_key(bbox), lineage)
    for group in document.get("groups", []):
        if not isinstance(group, dict):
            continue
        lineage = normalized_lineage(group.get("sourceLineage"), group)
        if lineage is None and group.get("rejectedLineageReason"):
            lineage = {
                "preOcrSymbolCandidate": False,
                "lineageStrength": "weak",
                "lineageSource": "m291_group",
                "m291GroupId": str(group.get("id") or ""),
                "ownershipHint": "text_owned",
                "rejectedLineageReason": str(group.get("rejectedLineageReason") or ""),
                "risks": ["text_like_sequence_risk"],
                "reasons": [str(reason) for reason in group.get("reasons", [])],
            }
        if lineage is None:
            continue
        lineage = attach_candidate_bboxes(lineage, candidate_bboxes_by_id)
        bbox = parse_bbox(group.get("bbox"))
        group_id = str(group.get("id") or "")
        if group_id:
            lookup[f"source_node:m291_group:{group_id}"] = lineage
        if bbox is not None:
            lookup[bbox_key(bbox)] = lineage
    return lookup

def normalized_lineage(value: object, owner: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    lineage = dict(value)
    owner_id = str(owner.get("id") or "")
    if owner_id and not lineage.get("sourceOwnerId"):
        lineage["sourceOwnerId"] = owner_id
    return lineage

def attach_candidate_bboxes(lineage: dict[str, Any], candidate_bboxes_by_id: dict[str, list[int]]) -> dict[str, Any]:
    candidate_ids = [str(value) for value in lineage.get("m291CandidateIds", []) if value]
    bboxes = [candidate_bboxes_by_id[candidate_id] for candidate_id in candidate_ids if candidate_id in candidate_bboxes_by_id]
    if not bboxes or lineage.get("m291CandidateBboxes"):
        return lineage
    output = dict(lineage)
    output["m291CandidateBboxes"] = bboxes
    return output

def lookup_source_lineage(raw: dict[str, Any], bbox: list[int], lineage_lookup: dict[str, dict[str, Any]] | None) -> dict[str, Any] | None:
    if not lineage_lookup:
        return None
    source = str(raw.get("source") or "")
    source_id = str(raw.get("sourceId") or raw.get("sourceNodeId") or raw.get("sourceGroupId") or "")
    if source_id:
        found = lineage_lookup.get(f"source_node:{source}:{source_id}")
        if found is not None:
            return found
    return lineage_lookup.get(bbox_key(bbox))

def bbox_key(bbox: list[int]) -> str:
    return "bbox:" + ",".join(str(int(item)) for item in bbox)
