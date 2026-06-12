from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .normalization import normalize_layout_candidates
from .permission import build_permission_items
from .report import build_summary
from .types import M29AutoLayoutPermissionOptions, M29AutoLayoutPermissionResult
from .validation import validate_auto_layout_permission_report


def extract_m29_auto_layout_permission_report(
    *,
    task_id: str,
    layout_energy_report: dict[str, Any] | None,
    output_dir: Path,
    options: M29AutoLayoutPermissionOptions | None = None,
) -> M29AutoLayoutPermissionResult:
    options = options or M29AutoLayoutPermissionOptions()
    output_dir.mkdir(parents=True, exist_ok=True)

    layout_candidates, warnings = normalize_layout_candidates((layout_energy_report or {}).get("layoutEnergyCandidates", []))
    permission_items = build_permission_items(layout_candidates, options)

    report_path = output_dir / "auto_layout_permission_report.json"
    report = {
        "schemaName": "M29AutoLayoutPermissionReport",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "layoutEnergySchemaName": (layout_energy_report or {}).get("schemaName"),
        "layoutEnergySchemaVersion": (layout_energy_report or {}).get("schemaVersion"),
        "outputReport": str(report_path),
        "summary": build_summary(
            layout_candidates=layout_candidates,
            permission_items=permission_items,
            warnings=warnings,
        ),
        "options": {
            "maxRowColumnEnergy": options.max_row_column_energy,
            "maxGridEnergy": options.max_grid_energy,
        },
        "permissionItems": permission_items,
        "warnings": warnings,
        "meta": {
            "createdAt": datetime.now(UTC).isoformat(),
            "truthSource": "m29_layout_energy_report",
            "permissionOnly": True,
            "dslChanged": False,
            "assetChanged": False,
            "createdVisibleNodeCount": 0,
            "materializationChanged": False,
            "autoLayoutCreated": False,
        },
    }
    validate_auto_layout_permission_report(report)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return M29AutoLayoutPermissionResult(report=report, output_dir=output_dir)
