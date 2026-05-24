from __future__ import annotations

from typing import Any


def build_summary(
    *,
    elements: list[dict[str, Any]],
    color_tokens: list[dict[str, Any]],
    text_style_tokens: list[dict[str, Any]],
    radius_tokens: list[dict[str, Any]],
    spacing_tokens: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    style_value_count = sum(token["count"] for token in color_tokens + text_style_tokens + radius_tokens + spacing_tokens)
    return {
        "elementCount": len(elements),
        "colorTokenCount": len(color_tokens),
        "textStyleTokenCount": len(text_style_tokens),
        "radiusTokenCount": len(radius_tokens),
        "spacingTokenCount": len(spacing_tokens),
        "styleValueCount": style_value_count,
        "warningCount": len(warnings),
        "tokenCoverage": 1.0 if style_value_count > 0 else 0.0,
        "dslChanged": False,
        "assetChanged": False,
        "createdVisibleNodeCount": 0,
        "materializationChanged": False,
        "figmaVariablesBound": False,
        "designSystemChanged": False,
        "singlePageOnly": True,
    }

