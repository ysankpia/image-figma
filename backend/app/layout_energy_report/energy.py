from __future__ import annotations

from statistics import mean
from typing import Any

from .geometry import (
    center_x,
    center_y,
    distinct_tracks,
    gaps_for_column,
    gaps_for_row,
    normalized_variance,
    overlap_penalty,
)


def build_layout_energy_candidates(subjects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for subject in subjects:
        models = score_models(subject)
        best = min(models, key=lambda item: (item["energy"], item["model"]))
        confidence = confidence_label(best["energy"], len(subject["_memberItems"]))
        risks = subject_risks(subject, best)
        candidates.append(
            {
                "id": f"{subject['id']}_energy",
                "subjectId": subject["id"],
                "subjectType": subject["subjectType"],
                "sourceCandidateId": subject["sourceCandidateId"],
                "bestModel": best["model"],
                "confidence": confidence,
                "energy": best["energy"],
                "modelEnergies": models,
                "memberSourceObjectIds": subject["memberSourceObjectIds"],
                "bbox": subject["bbox"],
                "metrics": subject_metrics(subject),
                "reasons": [f"{best['model']}_lowest_energy", "report_only_layout_candidate"],
                "risks": risks,
            }
        )
    return candidates


def score_models(subject: dict[str, Any]) -> list[dict[str, Any]]:
    items = subject["_memberItems"]
    return sorted(
        [
            {"model": "row", "energy": row_energy(items)},
            {"model": "column", "energy": column_energy(items)},
            {"model": "grid", "energy": grid_energy(items)},
            {"model": "overlay", "energy": overlay_energy(items)},
            {"model": "absolute", "energy": absolute_energy(items)},
        ],
        key=lambda item: item["model"],
    )


def row_energy(items: list[dict[str, Any]]) -> float:
    bboxes = [item["bbox"] for item in items]
    y_centers = [center_y(bbox) for bbox in bboxes]
    heights = [bbox[3] for bbox in bboxes]
    gaps = gaps_for_row(items)
    energy = normalized_variance(y_centers, max(1.0, mean(heights))) * 0.34
    energy += normalized_variance(gaps, max(1.0, mean([bbox[2] for bbox in bboxes]))) * 0.22
    energy += normalized_variance(heights, max(1.0, mean(heights))) * 0.18
    energy += overlap_penalty(items) * 0.26
    return round(min(1.0, energy), 3)


def column_energy(items: list[dict[str, Any]]) -> float:
    bboxes = [item["bbox"] for item in items]
    x_centers = [center_x(bbox) for bbox in bboxes]
    widths = [bbox[2] for bbox in bboxes]
    gaps = gaps_for_column(items)
    energy = normalized_variance(x_centers, max(1.0, mean(widths))) * 0.34
    energy += normalized_variance(gaps, max(1.0, mean([bbox[3] for bbox in bboxes]))) * 0.22
    energy += normalized_variance(widths, max(1.0, mean(widths))) * 0.18
    energy += overlap_penalty(items) * 0.26
    return round(min(1.0, energy), 3)


def grid_energy(items: list[dict[str, Any]]) -> float:
    if len(items) < 4:
        return 1.0
    bboxes = [item["bbox"] for item in items]
    avg_width = mean([bbox[2] for bbox in bboxes])
    avg_height = mean([bbox[3] for bbox in bboxes])
    col_count = distinct_tracks([center_x(bbox) for bbox in bboxes], max(2.0, avg_width * 0.25))
    row_count = distinct_tracks([center_y(bbox) for bbox in bboxes], max(2.0, avg_height * 0.25))
    if col_count < 2 or row_count < 2:
        return 1.0
    missing_penalty = abs(len(items) - (col_count * row_count)) / max(1, col_count * row_count)
    energy = normalized_variance([bbox[2] for bbox in bboxes], max(1.0, avg_width)) * 0.20
    energy += normalized_variance([bbox[3] for bbox in bboxes], max(1.0, avg_height)) * 0.20
    energy += missing_penalty * 0.34
    energy += overlap_penalty(items) * 0.26
    return round(min(1.0, energy), 3)


def overlay_energy(items: list[dict[str, Any]]) -> float:
    overlap = overlap_penalty(items)
    return round(min(1.0, 1.0 - overlap), 3)


def absolute_energy(items: list[dict[str, Any]]) -> float:
    # Absolute layout is always possible but not informative; keep it as a fallback model.
    return 0.82 if len(items) >= 2 else 1.0


def confidence_label(energy: float, member_count: int) -> str:
    if energy <= 0.20 and member_count >= 3:
        return "high"
    if energy <= 0.38:
        return "medium"
    return "low"


def subject_metrics(subject: dict[str, Any]) -> dict[str, Any]:
    items = subject["_memberItems"]
    bboxes = [item["bbox"] for item in items]
    return {
        "memberCount": len(items),
        "bboxWidth": subject["bbox"][2],
        "bboxHeight": subject["bbox"][3],
        "overlapPenalty": overlap_penalty(items),
        "meanWidth": round(mean([bbox[2] for bbox in bboxes]), 3),
        "meanHeight": round(mean([bbox[3] for bbox in bboxes]), 3),
    }


def subject_risks(subject: dict[str, Any], best: dict[str, Any]) -> list[str]:
    risks: list[str] = []
    if len(subject["_memberItems"]) == 2:
        risks.append("two_member_layout_candidate")
    if best["model"] == "absolute":
        risks.append("absolute_layout_fallback")
    if best["energy"] > 0.38:
        risks.append("high_layout_energy")
    if subject["subjectType"] == "hierarchy_children":
        risks.append("container_children_subject_not_materialization_permission")
    return risks
