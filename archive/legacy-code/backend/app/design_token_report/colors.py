from __future__ import annotations

import re
from typing import Any


HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def collect_color_tokens(dsl: dict[str, Any], elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, Any]] = {}
    add_color(counts, page_background_color(dsl), "page.background")
    root_style = dsl.get("root", {}).get("style") if isinstance(dsl.get("root"), dict) else None
    if isinstance(root_style, dict):
        add_color(counts, root_style.get("fill"), "root.style.fill")

    for element in elements:
        style = element.get("style") if isinstance(element.get("style"), dict) else {}
        path = str(element.get("_path") or "")
        add_color(counts, style.get("fill"), f"{path}.style.fill")
        add_color(counts, style.get("color"), f"{path}.style.color")

    tokens = []
    for index, value in enumerate(sorted(counts, key=lambda color: (-counts[color]["count"], color)), start=1):
        item = counts[value]
        tokens.append(
            {
                "id": f"m29_color_token_{index:04d}",
                "name": f"color/{index:03d}",
                "value": value,
                "count": item["count"],
                "sourcePaths": item["sourcePaths"][:12],
                "confidence": confidence_for_count(item["count"]),
            }
        )
    return tokens


def page_background_color(dsl: dict[str, Any]) -> Any:
    page = dsl.get("page") if isinstance(dsl.get("page"), dict) else {}
    background = page.get("background") if isinstance(page, dict) else {}
    if isinstance(background, dict) and background.get("type") == "color":
        return background.get("value")
    return None


def add_color(counts: dict[str, dict[str, Any]], value: Any, path: str) -> None:
    color = normalize_hex_color(value)
    if color is None:
        return
    item = counts.setdefault(color, {"count": 0, "sourcePaths": []})
    item["count"] += 1
    item["sourcePaths"].append(path)


def normalize_hex_color(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not HEX_COLOR_RE.match(stripped):
        return None
    return stripped.upper()


def confidence_for_count(count: int) -> str:
    if count >= 4:
        return "high"
    if count >= 2:
        return "medium"
    return "low"

