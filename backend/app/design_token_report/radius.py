from __future__ import annotations

from typing import Any


def collect_radius_tokens(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[int, dict[str, Any]] = {}
    for element in elements:
        style = element.get("style") if isinstance(element.get("style"), dict) else {}
        for radius in radius_values(style.get("radius")):
            item = counts.setdefault(radius, {"count": 0, "sourcePaths": []})
            item["count"] += 1
            item["sourcePaths"].append(f"{element.get('_path')}.style.radius")

    tokens = []
    for index, value in enumerate(sorted(counts, key=lambda radius: (-counts[radius]["count"], radius)), start=1):
        item = counts[value]
        tokens.append(
            {
                "id": f"m29_radius_token_{index:04d}",
                "name": f"radius/{index:03d}",
                "value": value,
                "count": item["count"],
                "sourcePaths": item["sourcePaths"][:12],
                "confidence": confidence_for_count(item["count"]),
            }
        )
    return tokens


def radius_values(value: Any) -> list[int]:
    if isinstance(value, (int, float)):
        radius = int(round(float(value)))
        return [radius] if radius >= 0 else []
    if isinstance(value, dict):
        result = []
        for key in ["topLeft", "topRight", "bottomRight", "bottomLeft"]:
            item = value.get(key)
            if isinstance(item, (int, float)):
                radius = int(round(float(item)))
                if radius >= 0:
                    result.append(radius)
        return result
    return []


def confidence_for_count(count: int) -> str:
    if count >= 4:
        return "high"
    if count >= 2:
        return "medium"
    return "low"

