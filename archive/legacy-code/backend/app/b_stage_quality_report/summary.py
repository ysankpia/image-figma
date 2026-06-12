from __future__ import annotations

from typing import Any


def summary_from(report: dict[str, Any] | None) -> dict[str, Any]:
    summary = (report or {}).get("summary")
    return summary if isinstance(summary, dict) else {}


def int_value(summary: dict[str, Any], key: str) -> int:
    try:
        return int(summary.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def float_value(summary: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(summary.get(key))
    except (TypeError, ValueError):
        return default


def warning_count(report: dict[str, Any] | None) -> int:
    summary = summary_from(report)
    count = int_value(summary, "warningCount")
    warnings = (report or {}).get("warnings")
    if isinstance(warnings, list):
        count += len(warnings)
    return count
