from __future__ import annotations

from typing import Any


def plan_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    action_order = {
        "shape_replay": 0,
        "image_replay": 1,
        "icon_replay": 2,
        "text_replay": 3,
        "preserve_in_parent_raster": 4,
        "fallback_only": 5,
        "diagnostic_only": 6,
        "suppress_duplicate": 7,
    }
    return action_order.get(str(item.get("finalReplayAction")), 99), str(item.get("sourceObjectId") or "")


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
