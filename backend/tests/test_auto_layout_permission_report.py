from __future__ import annotations

from pathlib import Path

from app.auto_layout_permission_report import extract_m29_auto_layout_permission_report


def test_auto_layout_permission_report_empty_is_permission_only(tmp_path: Path) -> None:
    report = permission_report(tmp_path, [])

    assert report["summary"]["permissionItemCount"] == 0
    assert report["summary"]["permissionOnly"] is True
    assert report["summary"]["dslChanged"] is False
    assert report["summary"]["materializationChanged"] is False
    assert report["summary"]["autoLayoutCreated"] is False
    assert report["meta"]["createdVisibleNodeCount"] == 0


def test_row_layout_energy_allows_horizontal_candidate(tmp_path: Path) -> None:
    report = permission_report(
        tmp_path,
        [
            layout_candidate("candidate_row", "row", 0.12, "high", ["a", "b", "c"]),
        ],
    )

    item = report["permissionItems"][0]
    assert item["permission"] == "allow_candidate"
    assert item["recommendedAxis"] == "horizontal"
    assert item["materializationPermission"] is False
    assert item["autoLayoutCreated"] is False
    assert report["summary"]["allowCandidateCount"] == 1


def test_column_layout_energy_allows_vertical_candidate(tmp_path: Path) -> None:
    report = permission_report(
        tmp_path,
        [
            layout_candidate("candidate_column", "column", 0.18, "medium", ["a", "b"]),
        ],
    )

    item = report["permissionItems"][0]
    assert item["permission"] == "allow_candidate"
    assert item["recommendedAxis"] == "vertical"
    assert item["confidence"] == "medium"


def test_grid_layout_energy_allows_grid_candidate_under_grid_threshold(tmp_path: Path) -> None:
    report = permission_report(
        tmp_path,
        [
            layout_candidate("candidate_grid", "grid", 0.22, "high", ["a", "b", "c", "d"]),
        ],
    )

    item = report["permissionItems"][0]
    assert item["permission"] == "allow_candidate"
    assert item["recommendedAxis"] == "grid"
    assert item["threshold"] == 0.28


def test_high_energy_supported_model_is_deferred(tmp_path: Path) -> None:
    report = permission_report(
        tmp_path,
        [
            layout_candidate("candidate_noisy_row", "row", 0.56, "medium", ["a", "b", "c"], risks=["high_layout_energy"]),
        ],
    )

    item = report["permissionItems"][0]
    assert item["permission"] == "defer"
    assert "layout_energy_above_permission_threshold" in item["reasons"]
    assert "layout_energy_risk_present" in item["reasons"]
    assert report["summary"]["deferCount"] == 1


def test_absolute_layout_model_is_rejected(tmp_path: Path) -> None:
    report = permission_report(
        tmp_path,
        [
            layout_candidate("candidate_absolute", "absolute", 0.82, "low", ["a", "b"], risks=["absolute_layout_fallback"]),
        ],
    )

    item = report["permissionItems"][0]
    assert item["permission"] == "reject"
    assert item["recommendedAxis"] is None
    assert item["confidence"] == "low"
    assert "unsupported_layout_model" in item["risks"] or "absolute_layout_fallback" in item["risks"]
    assert report["summary"]["rejectCount"] == 1


def permission_report(tmp_path: Path, candidates: list[dict]) -> dict:
    result = extract_m29_auto_layout_permission_report(
        task_id="task_auto_layout_permission",
        layout_energy_report=layout_energy_report(candidates),
        output_dir=tmp_path / "m29_auto_layout_permission",
    )
    assert (tmp_path / "m29_auto_layout_permission" / "auto_layout_permission_report.json").exists()
    return result.report


def layout_energy_report(candidates: list[dict]) -> dict:
    return {
        "schemaName": "M29LayoutEnergyReport",
        "schemaVersion": "0.1",
        "layoutEnergyCandidates": candidates,
    }


def layout_candidate(
    candidate_id: str,
    best_model: str,
    energy: float,
    confidence: str,
    members: list[str],
    *,
    risks: list[str] | None = None,
) -> dict:
    return {
        "id": candidate_id,
        "subjectId": f"subject_{candidate_id}",
        "subjectType": "sibling_group",
        "sourceCandidateId": f"group_{candidate_id}",
        "bestModel": best_model,
        "confidence": confidence,
        "energy": energy,
        "memberSourceObjectIds": members,
        "bbox": [0, 0, 100, 40],
        "metrics": {"memberCount": len(members)},
        "risks": risks or [],
    }
