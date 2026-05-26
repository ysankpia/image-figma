from __future__ import annotations

from typing import Any

from .types import VISIBLE_REPLAY_ACTIONS


def build_source_object_claims(source_objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "sourceObjectId": item["sourceObjectId"],
            "bbox": item["bbox"],
            "visualKind": item["visualKind"],
            "pixelOwner": item["pixelOwner"],
            "replayDecision": item["replayDecision"],
            "confidence": item["confidence"],
        }
        for item in source_objects
    ]


def build_visible_replay_claims(plan_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for item in plan_items:
        action = item["finalReplayAction"]
        if action not in VISIBLE_REPLAY_ACTIONS:
            continue
        claims.append(
            {
                "planItemId": item["planItemId"],
                "sourceObjectId": item["sourceObjectId"],
                "bbox": item["bbox"],
                "finalReplayAction": action,
                "targetRole": item["targetRole"],
                "pixelOwner": item["pixelOwner"],
                "confidence": item["confidence"],
                "cleanupTargets": item["cleanupTargets"],
                "sourceEvidence": item.get("sourceEvidence", {}),
            }
        )
    return claims


def build_cleanup_claims(plan_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for item in plan_items:
        for target in item["cleanupTargets"]:
            if not isinstance(target, dict):
                continue
            cleanup_target = str(target.get("target") or "")
            if cleanup_target not in {"fallback", "copied_image_asset"}:
                continue
            claims.append(
                {
                    "planItemId": item["planItemId"],
                    "sourceObjectId": item["sourceObjectId"],
                    "bbox": item["bbox"],
                    "cleanupTarget": cleanup_target,
                    "targetSourceObjectId": target.get("targetSourceObjectId"),
                    "reason": str(target.get("reason") or ""),
                    **({"foregroundClaimId": target.get("foregroundClaimId")} if target.get("foregroundClaimId") else {}),
                    **({"maskKind": target.get("maskKind")} if target.get("maskKind") else {}),
                    "authorizedBy": "m29_5_cleanupTargets",
                }
            )
    return claims
