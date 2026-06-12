from __future__ import annotations

from typing import Any

from .colors import normalize_hex_color


def collect_text_style_tokens(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[tuple[Any, ...], dict[str, Any]] = {}
    for element in elements:
        if element.get("type") != "text":
            continue
        style = element.get("style") if isinstance(element.get("style"), dict) else {}
        key = (
            str(style.get("fontFamily") or ""),
            safe_int(style.get("fontSize")),
            safe_int(style.get("fontWeight")),
            safe_int(style.get("lineHeight")),
            normalize_hex_color(style.get("color")),
        )
        item = counts.setdefault(key, {"count": 0, "sourcePaths": []})
        item["count"] += 1
        item["sourcePaths"].append(str(element.get("_path") or ""))

    tokens: list[dict[str, Any]] = []
    ordered = sorted(counts, key=lambda key: (-counts[key]["count"], key))
    for index, key in enumerate(ordered, start=1):
        family, font_size, weight, line_height, color = key
        item = counts[key]
        tokens.append(
            {
                "id": f"m29_text_style_token_{index:04d}",
                "name": f"text/{index:03d}",
                "fontFamily": family or None,
                "fontSize": font_size,
                "fontWeight": weight,
                "lineHeight": line_height,
                "color": color,
                "count": item["count"],
                "sourcePaths": item["sourcePaths"][:12],
                "confidence": confidence_for_count(item["count"]),
            }
        )
    return tokens


def safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def confidence_for_count(count: int) -> str:
    if count >= 4:
        return "high"
    if count >= 2:
        return "medium"
    return "low"

