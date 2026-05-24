from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .claims import build_cleanup_claims, build_source_object_claims, build_visible_replay_claims
from .conflicts import detect_conflicts
from .normalization import normalize_plan_items, normalize_source_objects
from .relations import build_edge_lookup
from .report import build_summary
from .types import M29OwnershipConservationResult
from .validation import validate_ownership_conservation_report


def extract_m29_ownership_conservation_report(
    *,
    task_id: str,
    m292_document: dict[str, Any],
    m2931_report: dict[str, Any] | None,
    m295_report: dict[str, Any],
    output_dir: Path,
) -> M29OwnershipConservationResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_objects, source_warnings = normalize_source_objects(m292_document.get("sourceObjects", []))
    plan_items, plan_warnings = normalize_plan_items(m295_report.get("planItems", []))
    edge_lookup = build_edge_lookup(m2931_report)

    source_claims = build_source_object_claims(source_objects)
    visible_claims = build_visible_replay_claims(plan_items)
    cleanup_claims = build_cleanup_claims(plan_items)
    warnings = source_warnings + plan_warnings
    conflicts = detect_conflicts(
        source_objects=source_objects,
        plan_items=plan_items,
        visible_claims=visible_claims,
        cleanup_claims=cleanup_claims,
        edge_lookup=edge_lookup,
    )
    report_path = output_dir / "ownership_conservation_report.json"
    report = {
        "schemaName": "M29OwnershipConservationReport",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "sourceSchemaName": m292_document.get("schemaName"),
        "sourceSchemaVersion": m292_document.get("schemaVersion"),
        "planSchemaName": m295_report.get("schemaName"),
        "planSchemaVersion": m295_report.get("schemaVersion"),
        "outputReport": str(report_path),
        "summary": build_summary(
            source_objects=source_objects,
            visible_claims=visible_claims,
            cleanup_claims=cleanup_claims,
            conflicts=conflicts,
            warnings=warnings,
        ),
        "sourceObjectClaims": source_claims,
        "visibleReplayClaims": visible_claims,
        "cleanupClaims": cleanup_claims,
        "conflicts": conflicts,
        "warnings": warnings,
        "meta": {
            "createdAt": datetime.now(UTC).isoformat(),
            "dslChanged": False,
            "assetChanged": False,
            "createdVisibleNodeCount": 0,
            "truthSource": "m29_2_plus_m29_3_1_plus_m29_5",
            "reportOnly": True,
            "materializationChanged": False,
        },
    }
    validate_ownership_conservation_report(report)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return M29OwnershipConservationResult(report=report, output_dir=output_dir)

