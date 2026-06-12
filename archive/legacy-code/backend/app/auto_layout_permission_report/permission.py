from __future__ import annotations

from typing import Any

from .types import M29AutoLayoutPermissionOptions, SUPPORTED_AUTO_LAYOUT_MODELS


def build_permission_items(candidates: list[dict[str, Any]], options: M29AutoLayoutPermissionOptions) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        decision = permission_decision(candidate, options)
        items.append(
            {
                "id": f"m29_auto_layout_permission_{index:04d}",
                "layoutEnergyCandidateId": candidate["layoutEnergyCandidateId"],
                "subjectId": candidate["subjectId"],
                "subjectType": candidate["subjectType"],
                "sourceCandidateId": candidate["sourceCandidateId"],
                "permission": decision["permission"],
                "recommendedModel": candidate["bestModel"],
                "recommendedAxis": recommended_axis(candidate["bestModel"]),
                "energy": candidate["energy"],
                "confidence": decision["confidence"],
                "threshold": decision["threshold"],
                "memberSourceObjectIds": candidate["memberSourceObjectIds"],
                "bbox": candidate["bbox"],
                "reasons": decision["reasons"],
                "risks": decision["risks"],
                "materializationPermission": False,
                "autoLayoutCreated": False,
            }
        )
    return items


def permission_decision(candidate: dict[str, Any], options: M29AutoLayoutPermissionOptions) -> dict[str, Any]:
    model = candidate["bestModel"]
    energy = float(candidate["energy"])
    risks = list(candidate.get("risks", []))
    threshold = options.threshold_for(model)
    reasons: list[str] = []

    if model not in SUPPORTED_AUTO_LAYOUT_MODELS:
        return {
            "permission": "reject",
            "confidence": "low",
            "threshold": threshold,
            "reasons": ["unsupported_layout_model_for_auto_layout_permission"],
            "risks": ordered_risks(risks + ["unsupported_layout_model"]),
        }

    if "absolute_layout_fallback" in risks:
        return {
            "permission": "reject",
            "confidence": "low",
            "threshold": threshold,
            "reasons": ["absolute_layout_fallback_rejected"],
            "risks": ordered_risks(risks),
        }

    if candidate["confidence"] not in {"high", "medium"}:
        reasons.append("layout_energy_confidence_too_low")
    if energy > threshold:
        reasons.append("layout_energy_above_permission_threshold")
    if "high_layout_energy" in risks:
        reasons.append("layout_energy_risk_present")

    if reasons:
        return {
            "permission": "defer",
            "confidence": "low" if candidate["confidence"] == "low" else "medium",
            "threshold": threshold,
            "reasons": reasons,
            "risks": ordered_risks(risks),
        }

    return {
        "permission": "allow_candidate",
        "confidence": candidate["confidence"],
        "threshold": threshold,
        "reasons": ["supported_model_with_low_layout_energy", "permission_only_not_materialization"],
        "risks": ordered_risks(risks),
    }


def recommended_axis(model: str) -> str | None:
    if model == "row":
        return "horizontal"
    if model == "column":
        return "vertical"
    if model == "grid":
        return "grid"
    return None


def ordered_risks(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
