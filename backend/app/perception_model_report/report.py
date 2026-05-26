from __future__ import annotations

from typing import Any

from .types import REPORT_ONLY_META


def normalize_candidates(raw_candidates: list[dict[str, Any]], *, provider: str) -> list[dict[str, Any]]:
    return [
        {
            "candidateId": f"perception_candidate_{index:04d}",
            "sourceProvider": provider,
            "roleHint": "unknown_ui_object",
            "bbox": candidate["bbox"],
            "score": candidate["score"],
            "areaRatio": candidate["areaRatio"],
            "rawOutputRef": {
                "anchorIndex": candidate.get("rawAnchorIndex"),
            },
            "decision": "report_only",
            "replayAuthorized": False,
            "cleanupAuthorized": False,
        }
        for index, candidate in enumerate(raw_candidates, start=1)
    ]


def build_summary(*, candidates: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    return {
        "candidateCount": len(candidates),
        "warningCount": len(warnings),
        "scoreMax": max((item["score"] for item in candidates), default=0.0),
        "scoreMean": round(sum(item["score"] for item in candidates) / len(candidates), 6) if candidates else 0.0,
        "roleHintCounts": count_values(item.get("roleHint") for item in candidates),
        **REPORT_ONLY_META,
    }


def count_values(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))
