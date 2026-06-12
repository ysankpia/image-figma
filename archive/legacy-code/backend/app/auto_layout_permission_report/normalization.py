from __future__ import annotations

from typing import Any

from ..region_relation_kernel import normalize_bbox


def normalize_layout_candidates(raw_candidates: Any) -> tuple[list[dict[str, Any]], list[str]]:
    candidates: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_candidates if isinstance(raw_candidates, list) else []):
        if not isinstance(item, dict):
            warnings.append(f"skipped_invalid_layout_energy_candidate:{index}")
            continue
        candidate_id = str(item.get("id") or f"m29_layout_energy_{index + 1:04d}")
        if candidate_id in seen:
            warnings.append(f"skipped_duplicate_layout_energy_candidate:{candidate_id}")
            continue
        try:
            bbox = normalize_bbox(item.get("bbox"), f"layoutEnergyCandidates[{index}].bbox")
        except ValueError:
            warnings.append(f"skipped_invalid_layout_energy_bbox:{candidate_id}")
            continue
        member_ids = [str(value) for value in item.get("memberSourceObjectIds", []) if isinstance(value, str)]
        if len(member_ids) < 2:
            warnings.append(f"skipped_layout_energy_too_few_members:{candidate_id}")
            continue
        metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
        seen.add(candidate_id)
        candidates.append(
            {
                "layoutEnergyCandidateId": candidate_id,
                "subjectId": str(item.get("subjectId") or ""),
                "subjectType": str(item.get("subjectType") or ""),
                "sourceCandidateId": str(item.get("sourceCandidateId") or ""),
                "bestModel": str(item.get("bestModel") or ""),
                "confidence": str(item.get("confidence") or "low"),
                "energy": safe_float(item.get("energy")),
                "memberSourceObjectIds": sorted(member_ids),
                "bbox": bbox,
                "metrics": metrics,
                "risks": [str(value) for value in item.get("risks", []) if isinstance(value, str)]
                if isinstance(item.get("risks"), list)
                else [],
            }
        )
    return sorted(candidates, key=lambda item: item["layoutEnergyCandidateId"]), warnings


def safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 1.0
