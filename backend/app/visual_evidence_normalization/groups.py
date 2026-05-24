from __future__ import annotations

from typing import Any

from .types import VisualEvidenceItem


def build_groups(items: list[VisualEvidenceItem]) -> dict[str, Any]:
    by_kind: dict[str, int] = {}
    by_decision: dict[str, int] = {}
    by_region: dict[str, dict[str, int]] = {}
    for item in items:
        by_kind[item.visual_kind] = by_kind.get(item.visual_kind, 0) + 1
        by_decision[item.decision] = by_decision.get(item.decision, 0) + 1
        region = by_region.setdefault(item.region_name, {})
        region[item.visual_kind] = region.get(item.visual_kind, 0) + 1
    return {
        "byVisualKind": dict(sorted(by_kind.items())),
        "byDecision": dict(sorted(by_decision.items())),
        "byRegion": {region: dict(sorted(counts.items())) for region, counts in sorted(by_region.items())},
    }
