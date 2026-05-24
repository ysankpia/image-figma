from __future__ import annotations

from typing import Any

from .traversal import child_groups


def collect_spacing_tokens(dsl: dict[str, Any]) -> list[dict[str, Any]]:
    counts: dict[tuple[str, int], dict[str, Any]] = {}
    for parent_path, children in child_groups(dsl.get("root") if isinstance(dsl.get("root"), dict) else None):
        add_axis_gaps(counts, parent_path, children, axis="horizontal")
        add_axis_gaps(counts, parent_path, children, axis="vertical")

    tokens = []
    ordered = sorted(counts, key=lambda key: (-counts[key]["count"], key[0], key[1]))
    for index, key in enumerate(ordered, start=1):
        axis, value = key
        item = counts[key]
        tokens.append(
            {
                "id": f"m29_spacing_token_{index:04d}",
                "name": f"spacing/{axis}/{index:03d}",
                "axis": axis,
                "value": value,
                "count": item["count"],
                "sourcePaths": item["sourcePaths"][:12],
                "confidence": confidence_for_count(item["count"]),
            }
        )
    return tokens


def add_axis_gaps(counts: dict[tuple[str, int], dict[str, Any]], parent_path: str, children: list[dict[str, Any]], *, axis: str) -> None:
    ordered = sorted(children, key=lambda item: sort_key(item, axis))
    for index in range(len(ordered) - 1):
        left = layout(ordered[index])
        right = layout(ordered[index + 1])
        if left is None or right is None:
            continue
        gap = gap_between(left, right, axis)
        if gap <= 0:
            continue
        key = (axis, gap)
        item = counts.setdefault(key, {"count": 0, "sourcePaths": []})
        item["count"] += 1
        item["sourcePaths"].append(f"{parent_path}.children[{index}->{index + 1}]")


def sort_key(element: dict[str, Any], axis: str) -> tuple[float, float, str]:
    item = layout(element) or {"x": 0, "y": 0}
    if axis == "horizontal":
        return float(item.get("x") or 0), float(item.get("y") or 0), str(element.get("id") or "")
    return float(item.get("y") or 0), float(item.get("x") or 0), str(element.get("id") or "")


def layout(element: dict[str, Any]) -> dict[str, Any] | None:
    value = element.get("layout")
    return value if isinstance(value, dict) else None


def gap_between(left: dict[str, Any], right: dict[str, Any], axis: str) -> int:
    try:
        if axis == "horizontal":
            return int(round(float(right["x"]) - (float(left["x"]) + float(left["width"]))))
        return int(round(float(right["y"]) - (float(left["y"]) + float(left["height"]))))
    except (KeyError, TypeError, ValueError):
        return 0


def confidence_for_count(count: int) -> str:
    if count >= 4:
        return "high"
    if count >= 2:
        return "medium"
    return "low"

