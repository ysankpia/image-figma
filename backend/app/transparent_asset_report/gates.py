from __future__ import annotations

from typing import Any


def visible_replay_eligible(item: dict[str, Any] | None) -> bool:
    if item is None or not item.get("assetPath"):
        return False
    if "visibleReplayEligible" in item:
        return item.get("visibleReplayEligible") is True
    return item.get("decision") == "allow"


def visible_replay_block_reason(item: dict[str, Any] | None, *, fallback: str = "missing_transparent_asset_path") -> str:
    if item is None:
        return "missing_transparent_asset_item"
    if not item.get("assetPath"):
        return first_reason(item, fallback=fallback)
    gate = item.get("gateDecision") if isinstance(item.get("gateDecision"), dict) else {}
    reason = str(gate.get("visibleReplayReason") or "")
    if reason:
        return reason
    if item.get("visibleReplayEligible") is False:
        return "transparent_asset_not_allowing_visible_replay"
    return first_reason(item, fallback=fallback)


def first_reason(item: dict[str, Any], *, fallback: str) -> str:
    for key in ("reasons", "risks"):
        values = item.get(key)
        for value in values if isinstance(values, list) else []:
            text = str(value or "")
            if text and not text.startswith("m29_"):
                return text
    return fallback
