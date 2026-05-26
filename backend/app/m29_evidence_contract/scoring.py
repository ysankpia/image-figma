from __future__ import annotations

from typing import Any

from ..region_relation_kernel import bbox_area, intersection_area, normalize_bbox
from ..transparent_asset_report.gates import visible_replay_eligible as transparent_visible_replay_eligible


ALLOW_VISIBLE_THRESHOLD = 0.68
REPORT_ONLY_THRESHOLD = 0.42
MAX_TEXT_OVERLAP_FOR_VISIBLE = 0.20
MAX_HERO_PENALTY_FOR_VISIBLE = 0.42
MIN_MEDIA_CONTAINMENT_FOR_VISIBLE = 0.95
MIN_ANCHORED_FOREGROUND_TEXT_ANCHOR = 0.70
MAX_ANCHORED_FOREGROUND_HERO_PENALTY = 0.26
PROMOTABLE_SHAPE_ROLES = {
    "selected_marker_candidate",
    "status_dot_candidate",
    "table_marker_candidate",
    "internal_shape_candidate",
    "internal_control_background",
}


def build_m296_contract_item(
    *,
    contract_id: str,
    candidate: dict[str, Any],
    parent_media: dict[str, Any] | None,
    transparent_item: dict[str, Any] | None,
) -> dict[str, Any]:
    bbox = normalize_bbox(candidate.get("bbox"), "candidate.bbox")
    media_bbox = normalize_bbox(parent_media.get("bbox"), "parent_media.bbox") if parent_media is not None else None
    breakdown = candidate.get("scoreBreakdown") if isinstance(candidate.get("scoreBreakdown"), dict) else {}
    text_overlap = max(float_value(breakdown.get("textMaskOverlap")), float_value((transparent_item or {}).get("textOverlap")))
    hero_penalty = float_value(breakdown.get("heroGraphicPenalty"))
    media_containment = containment_ratio(bbox, media_bbox) if media_bbox is not None else 0.0
    transparent_allowed = transparent_visible_replay_eligible(transparent_item)
    execution_supported = candidate.get("confidence") == "high" or candidate.get("groupSupportedExecution") is True

    positive = {
        "sourceCandidateScore": clamp01(float_value(candidate.get("score"))),
        "sizeCompactness": round((float_value(breakdown.get("sizeScore")) + float_value(breakdown.get("compactnessScore"))) / 2, 4),
        "textAnchor": clamp01(float_value(breakdown.get("textAnchorScore"))),
        "sameMediaContainment": round(media_containment, 4),
        "repetition": clamp01(float_value(breakdown.get("repetitionScore"))),
        "relationConsistency": clamp01(float_value(breakdown.get("relationConsistencyScore"))),
        "transparentAsset": 1.0 if transparent_allowed else 0.0,
    }
    cleanup_risk = cleanup_risk_score(
        transparent_allowed=transparent_allowed,
        media_containment=media_containment,
        text_overlap=text_overlap,
        hero_penalty=hero_penalty,
        parent_media_exists=parent_media is not None,
    )
    negative = {
        "textOverlapPenalty": round(min(1.0, text_overlap / MAX_TEXT_OVERLAP_FOR_VISIBLE), 4),
        "heroGraphicPenalty": round(hero_penalty, 4),
        "cleanupRisk": cleanup_risk,
        "repairCostPenalty": repair_cost_penalty(transparent_allowed=transparent_allowed, execution_supported=execution_supported),
    }
    evidence_score = score_evidence(positive, negative)
    hard_reasons = hard_rejection_reasons(
        candidate=candidate,
        parent_media=parent_media,
        text_overlap=text_overlap,
        hero_penalty=hero_penalty,
    )
    mode = decision_mode(
        evidence_score=evidence_score,
        hard_reasons=hard_reasons,
        transparent_allowed=transparent_allowed,
        execution_supported=execution_supported,
        media_containment=media_containment,
        text_overlap=text_overlap,
        hero_penalty=hero_penalty,
    )
    risk_level = risk_level_for(mode=mode, cleanup_risk=cleanup_risk, hard_reasons=hard_reasons, transparent_allowed=transparent_allowed)
    reasons = decision_reasons(
        mode=mode,
        hard_reasons=hard_reasons,
        transparent_allowed=transparent_allowed,
        execution_supported=execution_supported,
        media_containment=media_containment,
        evidence_score=evidence_score,
    )
    return {
        "contractId": contract_id,
        "candidateId": str(candidate.get("candidateId") or ""),
        "candidateRole": str(candidate.get("role") or ""),
        "sourceKind": "m29_6_internal_icon_candidate",
        "mediaSourceObjectId": str(candidate.get("mediaSourceObjectId") or ""),
        "bbox": bbox,
        "sourceTruth": {
            "rawNodeIds": [str(candidate.get("rawNodeId"))] if candidate.get("rawNodeId") else [],
            "blockedIds": [],
            "ocrAnchorIds": [str(candidate.get("matchedOcrBoxId"))] if candidate.get("matchedOcrBoxId") else [],
            "parentMediaId": str(parent_media.get("id") or parent_media.get("sourceObjectId") or "") if parent_media is not None else None,
            "transparentAssetCandidateId": (transparent_item or {}).get("candidateId"),
            "transparentAssetPath": (transparent_item or {}).get("assetPath"),
        },
        "positiveEvidence": positive,
        "negativeEvidence": negative,
        "risk": {
            "level": risk_level,
            "repairCost": "low" if risk_level == "low" else "medium" if risk_level == "medium" else "high",
            "risks": risks_for(hard_reasons=hard_reasons, transparent_allowed=transparent_allowed, execution_supported=execution_supported),
        },
        "decision": {
            "mode": mode,
            "evidenceScore": evidence_score,
            "reasons": reasons,
            "requiredForPromotion": True,
            "promotionAllowed": mode == "allow_visible_replay",
        },
        "reportOnly": True,
    }


def build_label_anchored_blocked_contract_item(*, contract_id: str, source: dict[str, Any], parent_media: dict[str, Any] | None, transparent_item: dict[str, Any] | None) -> dict[str, Any]:
    bbox = normalize_bbox(source.get("bbox"), "source.bbox")
    media_bbox = normalize_bbox(parent_media.get("bbox"), "parent_media.bbox") if parent_media is not None else None
    evidence = source.get("sourceEvidence") if isinstance(source.get("sourceEvidence"), dict) else {}
    media_containment = float_value(evidence.get("mediaContainmentRatio")) or (containment_ratio(bbox, media_bbox) if media_bbox is not None else 0.0)
    text_overlap = float_value(evidence.get("textOverlapRatio"))
    transparent_allowed = transparent_visible_replay_eligible(transparent_item)
    source_score = {"high": 0.9, "medium": 0.72, "low": 0.35}.get(str(source.get("confidence") or "low"), 0.35)
    positive = {
        "sourceCandidateScore": source_score,
        "sizeCompactness": 0.78,
        "textAnchor": 0.76 if evidence.get("labelAnchorOcrBoxId") else 0.0,
        "sameMediaContainment": round(media_containment, 4),
        "repetition": 0.0,
        "relationConsistency": 0.70 if parent_media is not None else 0.0,
        "transparentAsset": 1.0 if transparent_allowed else 0.0,
    }
    negative = {
        "textOverlapPenalty": round(min(1.0, text_overlap / MAX_TEXT_OVERLAP_FOR_VISIBLE), 4),
        "heroGraphicPenalty": 0.0,
        "cleanupRisk": cleanup_risk_score(
            transparent_allowed=transparent_allowed,
            media_containment=media_containment,
            text_overlap=text_overlap,
            hero_penalty=0.0,
            parent_media_exists=parent_media is not None,
        ),
        "repairCostPenalty": 0.12,
    }
    return {
        "contractId": contract_id,
        "candidateId": str(source.get("id") or ""),
        "candidateRole": "raster_icon",
        "sourceKind": "m29_2_label_anchored_blocked_icon",
        "mediaSourceObjectId": str(parent_media.get("id") or "") if parent_media is not None else "",
        "bbox": bbox,
        "sourceTruth": {
            "rawNodeIds": list(evidence.get("m29NodeIds") or []),
            "blockedIds": list(evidence.get("blockedIds") or []),
            "ocrAnchorIds": [str(evidence.get("labelAnchorOcrBoxId"))] if evidence.get("labelAnchorOcrBoxId") else [],
            "parentMediaId": str(parent_media.get("id") or "") if parent_media is not None else None,
            "transparentAssetCandidateId": (transparent_item or {}).get("candidateId"),
            "transparentAssetPath": (transparent_item or {}).get("assetPath"),
        },
        "positiveEvidence": positive,
        "negativeEvidence": negative,
        "risk": {
            "level": "low" if parent_media is not None and text_overlap <= MAX_TEXT_OVERLAP_FOR_VISIBLE else "medium",
            "repairCost": "low",
            "risks": [],
        },
        "decision": {
            "mode": "report_only",
            "evidenceScore": score_evidence(positive, negative),
            "reasons": ["already_source_owned_label_anchored_blocked_icon", "m29_2_audit_only"],
            "requiredForPromotion": False,
            "promotionAllowed": False,
        },
        "reportOnly": True,
    }


def build_m296_shape_contract_item(
    *,
    contract_id: str,
    candidate: dict[str, Any],
    parent_media: dict[str, Any] | None,
) -> dict[str, Any]:
    bbox = normalize_bbox(candidate.get("bbox"), "candidate.bbox")
    media_bbox = normalize_bbox(parent_media.get("bbox"), "parent_media.bbox") if parent_media is not None else None
    breakdown = candidate.get("scoreBreakdown") if isinstance(candidate.get("scoreBreakdown"), dict) else {}
    text_overlap = float_value(breakdown.get("textMaskOverlap"))
    hero_penalty = float_value(breakdown.get("heroGraphicPenalty"))
    media_containment = containment_ratio(bbox, media_bbox) if media_bbox is not None else 0.0
    role_supported = shape_role_supported(candidate)
    positive = {
        "sourceCandidateScore": clamp01(float_value(candidate.get("score"))),
        "sizeCompactness": round((float_value(breakdown.get("sizeScore")) + float_value(breakdown.get("compactnessScore"))) / 2, 4),
        "shapeRoleSupport": 1.0 if role_supported else 0.0,
        "sameMediaContainment": round(media_containment, 4),
        "repetition": clamp01(float_value(breakdown.get("repetitionScore"))),
        "relationConsistency": clamp01(float_value(breakdown.get("relationConsistencyScore"))),
    }
    negative = {
        "textOverlapPenalty": round(min(1.0, text_overlap / MAX_TEXT_OVERLAP_FOR_VISIBLE), 4),
        "heroGraphicPenalty": round(hero_penalty, 4),
        "repairCostPenalty": 0.10 if role_supported else 0.28,
    }
    evidence_score = score_shape_evidence(positive, negative)
    hard_reasons = shape_hard_rejection_reasons(
        candidate=candidate,
        parent_media=parent_media,
        text_overlap=text_overlap,
        hero_penalty=hero_penalty,
        role_supported=role_supported,
    )
    mode = shape_decision_mode(
        evidence_score=evidence_score,
        hard_reasons=hard_reasons,
        role_supported=role_supported,
        media_containment=media_containment,
        text_overlap=text_overlap,
        hero_penalty=hero_penalty,
    )
    reasons = shape_decision_reasons(
        mode=mode,
        hard_reasons=hard_reasons,
        role_supported=role_supported,
        media_containment=media_containment,
        evidence_score=evidence_score,
    )
    risk_level = "low" if mode == "allow_visible_replay" else "medium" if mode == "report_only" else "high"
    return {
        "contractId": contract_id,
        "candidateId": str(candidate.get("candidateId") or ""),
        "candidateRole": str(candidate.get("role") or ""),
        "sourceKind": "m29_6_internal_shape_candidate",
        "mediaSourceObjectId": str(candidate.get("mediaSourceObjectId") or ""),
        "bbox": bbox,
        "sourceTruth": {
            "rawNodeIds": [str(candidate.get("rawNodeId"))] if candidate.get("rawNodeId") else [],
            "blockedIds": [],
            "ocrAnchorIds": [str(candidate.get("matchedOcrBoxId"))] if candidate.get("matchedOcrBoxId") else [],
            "parentMediaId": str(parent_media.get("id") or parent_media.get("sourceObjectId") or "") if parent_media is not None else None,
        },
        "positiveEvidence": positive,
        "negativeEvidence": negative,
        "risk": {
            "level": risk_level,
            "repairCost": "low" if risk_level == "low" else "medium" if risk_level == "medium" else "high",
            "risks": dedupe(hard_reasons + ([] if role_supported else ["shape_role_support_missing"])),
        },
        "decision": {
            "mode": mode,
            "evidenceScore": evidence_score,
            "reasons": reasons,
            "requiredForPromotion": True,
            "promotionAllowed": mode == "allow_visible_replay",
        },
        "reportOnly": True,
    }


def score_evidence(positive: dict[str, float], negative: dict[str, float]) -> float:
    score = (
        positive["sourceCandidateScore"] * 0.20
        + positive["sizeCompactness"] * 0.12
        + positive["textAnchor"] * 0.16
        + positive["sameMediaContainment"] * 0.12
        + positive["repetition"] * 0.10
        + positive["relationConsistency"] * 0.10
        + positive["transparentAsset"] * 0.20
        - negative["textOverlapPenalty"] * 0.20
        - negative["heroGraphicPenalty"] * 0.16
        - negative["cleanupRisk"] * 0.12
        - negative["repairCostPenalty"] * 0.08
    )
    return round(clamp01(score), 4)


def score_shape_evidence(positive: dict[str, float], negative: dict[str, float]) -> float:
    score = (
        positive["sourceCandidateScore"] * 0.18
        + positive["sizeCompactness"] * 0.18
        + positive["shapeRoleSupport"] * 0.22
        + positive["sameMediaContainment"] * 0.16
        + positive["repetition"] * 0.12
        + positive["relationConsistency"] * 0.08
        - negative["textOverlapPenalty"] * 0.18
        - negative["heroGraphicPenalty"] * 0.18
        - negative["repairCostPenalty"] * 0.08
    )
    return round(clamp01(score), 4)


def decision_mode(*, evidence_score: float, hard_reasons: list[str], transparent_allowed: bool, execution_supported: bool, media_containment: float, text_overlap: float, hero_penalty: float) -> str:
    if hard_reasons:
        return "reject"
    if (
        evidence_score >= ALLOW_VISIBLE_THRESHOLD
        and transparent_allowed
        and execution_supported
        and media_containment >= MIN_MEDIA_CONTAINMENT_FOR_VISIBLE
        and text_overlap <= MAX_TEXT_OVERLAP_FOR_VISIBLE
        and hero_penalty <= MAX_HERO_PENALTY_FOR_VISIBLE
    ):
        return "allow_visible_replay"
    if evidence_score >= REPORT_ONLY_THRESHOLD:
        return "report_only"
    return "reject"


def shape_decision_mode(*, evidence_score: float, hard_reasons: list[str], role_supported: bool, media_containment: float, text_overlap: float, hero_penalty: float) -> str:
    if hard_reasons:
        return "reject"
    if (
        evidence_score >= ALLOW_VISIBLE_THRESHOLD
        and role_supported
        and media_containment >= MIN_MEDIA_CONTAINMENT_FOR_VISIBLE
        and text_overlap <= MAX_TEXT_OVERLAP_FOR_VISIBLE
        and hero_penalty <= MAX_HERO_PENALTY_FOR_VISIBLE
    ):
        return "allow_visible_replay"
    if evidence_score >= REPORT_ONLY_THRESHOLD:
        return "report_only"
    return "reject"


def hard_rejection_reasons(*, candidate: dict[str, Any], parent_media: dict[str, Any] | None, text_overlap: float, hero_penalty: float) -> list[str]:
    reasons: list[str] = []
    if candidate.get("role") != "internal_icon_candidate":
        reasons.append("not_internal_icon_candidate")
    if candidate.get("candidateDecision") != "accepted_report_candidate":
        reasons.append("internal_candidate_not_accepted")
    if is_unanchored_generic_foreground(candidate, text_overlap=text_overlap, hero_penalty=hero_penalty):
        reasons.append("generic_foreground_not_visible_replay")
    if parent_media is None:
        reasons.append("missing_parent_media_source_object")
    if text_overlap > 0.30:
        reasons.append("text_overlap_too_high")
    if hero_penalty > 0.62:
        reasons.append("hero_or_texture_risk_too_high")
    return reasons


def shape_hard_rejection_reasons(*, candidate: dict[str, Any], parent_media: dict[str, Any] | None, text_overlap: float, hero_penalty: float, role_supported: bool) -> list[str]:
    reasons: list[str] = []
    if candidate.get("role") not in PROMOTABLE_SHAPE_ROLES:
        reasons.append("not_internal_shape_candidate")
    if candidate.get("candidateDecision") != "accepted_report_candidate":
        reasons.append("internal_candidate_not_accepted")
    if parent_media is None:
        reasons.append("missing_parent_media_source_object")
    if not role_supported:
        reasons.append("shape_role_support_missing")
    if text_overlap > 0.30:
        reasons.append("text_overlap_too_high")
    if hero_penalty > 0.62:
        reasons.append("hero_or_texture_risk_too_high")
    return reasons


def shape_role_supported(candidate: dict[str, Any]) -> bool:
    role = str(candidate.get("role") or "")
    confidence = str(candidate.get("confidence") or "low")
    breakdown = candidate.get("scoreBreakdown") if isinstance(candidate.get("scoreBreakdown"), dict) else {}
    text_anchor = float_value(breakdown.get("textAnchorScore"))
    relation = str(candidate.get("anchorRelation") or "")
    repetition = float_value(breakdown.get("repetitionScore"))
    compactness = float_value(breakdown.get("compactnessScore"))
    color = float_value(breakdown.get("colorCoherenceScore"))
    if role == "selected_marker_candidate":
        return bool(candidate.get("matchedOcrBoxId")) and relation == "below_text" and text_anchor >= 0.45
    if role == "table_marker_candidate":
        return repetition >= 0.60 and confidence in {"high", "medium"}
    if role == "status_dot_candidate":
        return confidence == "high" and compactness >= 0.55 and color >= 0.45
    if role == "internal_shape_candidate":
        return candidate.get("rawType") == "shape" and confidence in {"high", "medium"}
    if role == "internal_control_background":
        return confidence in {"high", "medium"} and compactness >= 0.50
    return False


def is_unanchored_generic_foreground(candidate: dict[str, Any], *, text_overlap: float, hero_penalty: float) -> bool:
    if candidate.get("rawType") != "pixel_component" or candidate.get("rawSubtype") != "non_ocr_foreground":
        return False
    breakdown = candidate.get("scoreBreakdown") if isinstance(candidate.get("scoreBreakdown"), dict) else {}
    anchor_relation = str(candidate.get("anchorRelation") or "")
    anchored = (
        bool(candidate.get("matchedOcrBoxId"))
        and anchor_relation in {"above_text", "below_text", "left_of_text", "right_of_text"}
        and float_value(breakdown.get("textAnchorScore")) >= MIN_ANCHORED_FOREGROUND_TEXT_ANCHOR
        and text_overlap <= MAX_TEXT_OVERLAP_FOR_VISIBLE
        and hero_penalty <= MAX_ANCHORED_FOREGROUND_HERO_PENALTY
        and candidate.get("groupSupportedExecution") is True
    )
    return not anchored


def decision_reasons(*, mode: str, hard_reasons: list[str], transparent_allowed: bool, execution_supported: bool, media_containment: float, evidence_score: float) -> list[str]:
    if mode == "reject":
        return hard_reasons or ["weak_evidence_contract_score"]
    reasons: list[str] = ["evidence_contract_score_threshold_met"] if evidence_score >= REPORT_ONLY_THRESHOLD else []
    if transparent_allowed:
        reasons.append("transparent_asset_allow")
    else:
        reasons.append("transparent_asset_not_allowing_visible_replay")
    if execution_supported:
        reasons.append("execution_supported_internal_icon")
    else:
        reasons.append("execution_support_missing")
    if media_containment >= MIN_MEDIA_CONTAINMENT_FOR_VISIBLE:
        reasons.append("same_media_containment")
    if mode == "allow_visible_replay":
        reasons.append("allow_visible_replay_contract")
    return reasons


def shape_decision_reasons(*, mode: str, hard_reasons: list[str], role_supported: bool, media_containment: float, evidence_score: float) -> list[str]:
    if mode == "reject":
        return hard_reasons or ["weak_evidence_contract_score"]
    reasons: list[str] = ["evidence_contract_score_threshold_met"] if evidence_score >= REPORT_ONLY_THRESHOLD else []
    if role_supported:
        reasons.append("shape_role_supported")
    else:
        reasons.append("shape_role_support_missing")
    if media_containment >= MIN_MEDIA_CONTAINMENT_FOR_VISIBLE:
        reasons.append("same_media_containment")
    if mode == "allow_visible_replay":
        reasons.append("allow_visible_replay_contract")
    return reasons


def cleanup_risk_score(*, transparent_allowed: bool, media_containment: float, text_overlap: float, hero_penalty: float, parent_media_exists: bool) -> float:
    risk = 0.08
    if not transparent_allowed:
        risk += 0.30
    if not parent_media_exists:
        risk += 0.25
    if media_containment < MIN_MEDIA_CONTAINMENT_FOR_VISIBLE:
        risk += 0.16
    if text_overlap > MAX_TEXT_OVERLAP_FOR_VISIBLE:
        risk += 0.20
    if hero_penalty > MAX_HERO_PENALTY_FOR_VISIBLE:
        risk += 0.18
    return round(clamp01(risk), 4)


def repair_cost_penalty(*, transparent_allowed: bool, execution_supported: bool) -> float:
    value = 0.10
    if not transparent_allowed:
        value += 0.22
    if not execution_supported:
        value += 0.14
    return round(clamp01(value), 4)


def risk_level_for(*, mode: str, cleanup_risk: float, hard_reasons: list[str], transparent_allowed: bool) -> str:
    if mode == "reject" or hard_reasons:
        return "high"
    if cleanup_risk <= 0.22 and transparent_allowed:
        return "low"
    return "medium"


def risks_for(*, hard_reasons: list[str], transparent_allowed: bool, execution_supported: bool) -> list[str]:
    risks = list(hard_reasons)
    if not transparent_allowed:
        risks.append("transparent_asset_not_allowing_visible_replay")
    if not execution_supported:
        risks.append("internal_candidate_not_execution_supported")
    return dedupe(risks)


def containment_ratio(bbox: list[int], container: list[int] | None) -> float:
    if container is None:
        return 0.0
    return intersection_area(bbox, container) / max(1, bbox_area(bbox))


def float_value(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
