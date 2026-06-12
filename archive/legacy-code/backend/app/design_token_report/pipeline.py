from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .colors import collect_color_tokens
from .radius import collect_radius_tokens
from .report import build_summary
from .spacing import collect_spacing_tokens
from .text_styles import collect_text_style_tokens
from .traversal import visible_elements, walk_elements
from .types import M29DesignTokenResult
from .validation import validate_design_token_report


def extract_m29_design_token_report(
    *,
    task_id: str,
    dsl: dict[str, Any],
    materialization_report: dict[str, Any] | None,
    m295_report: dict[str, Any] | None,
    output_dir: Path,
) -> M29DesignTokenResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    elements = visible_elements(walk_elements(dsl.get("root") if isinstance(dsl.get("root"), dict) else None))
    color_tokens = collect_color_tokens(dsl, elements)
    text_style_tokens = collect_text_style_tokens(elements)
    radius_tokens = collect_radius_tokens(elements)
    spacing_tokens = collect_spacing_tokens(dsl)
    warnings: list[str] = []

    report_path = output_dir / "design_token_report.json"
    report = {
        "schemaName": "M29DesignTokenReport",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "dslVersion": dsl.get("version"),
        "materializationSchemaName": (materialization_report or {}).get("schemaName"),
        "materializationSchemaVersion": (materialization_report or {}).get("schemaVersion"),
        "planSchemaName": (m295_report or {}).get("schemaName"),
        "planSchemaVersion": (m295_report or {}).get("schemaVersion"),
        "outputReport": str(report_path),
        "summary": build_summary(
            elements=elements,
            color_tokens=color_tokens,
            text_style_tokens=text_style_tokens,
            radius_tokens=radius_tokens,
            spacing_tokens=spacing_tokens,
            warnings=warnings,
        ),
        "colorTokens": color_tokens,
        "textStyleTokens": text_style_tokens,
        "radiusTokens": radius_tokens,
        "spacingTokens": spacing_tokens,
        "warnings": warnings,
        "meta": {
            "createdAt": datetime.now(UTC).isoformat(),
            "truthSource": "m29_plan_driven_dsl_plus_m29_5_replay_plan",
            "reportOnly": True,
            "singlePageOnly": True,
            "dslChanged": False,
            "assetChanged": False,
            "createdVisibleNodeCount": 0,
            "materializationChanged": False,
            "figmaVariablesBound": False,
            "designSystemChanged": False,
        },
    }
    validate_design_token_report(report)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return M29DesignTokenResult(report=report, output_dir=output_dir)

