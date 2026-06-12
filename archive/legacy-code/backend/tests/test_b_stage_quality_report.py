from __future__ import annotations

from pathlib import Path

from app.b_stage_quality_report import extract_m29_b_stage_quality_report


def test_b_stage_quality_report_empty_is_report_only(tmp_path: Path) -> None:
    report = quality_report(tmp_path)

    assert report["summary"]["reportOnly"] is True
    assert report["summary"]["dslChanged"] is False
    assert report["summary"]["materializationChanged"] is False
    assert report["summary"]["blockingUpload"] is False
    assert report["summary"]["createdVisibleNodeCount"] == 0
    assert report["qualitySummary"]["grade"] == "high"


def test_ownership_conflict_penalizes_quality_and_repair_cost(tmp_path: Path) -> None:
    report = quality_report(
        tmp_path,
        ownership={"summary": {"visibleReplayClaimCount": 3, "conflictCount": 2, "errorCount": 1, "warningCount": 0}},
    )

    assert report["riskSummary"]["ownershipErrorCount"] == 1
    assert report["riskSummary"]["ownershipConflictCount"] == 2
    assert report["repairCost"]["totalCost"] >= 16
    assert report["qualitySummary"]["score"] < 1.0


def test_deferred_permission_adds_repair_cost(tmp_path: Path) -> None:
    report = quality_report(
        tmp_path,
        permission={"summary": {"allowCandidateCount": 2, "deferCount": 3, "rejectCount": 1}},
    )

    assert report["riskSummary"]["deferredAutoLayoutCount"] == 3
    assert report["riskSummary"]["rejectedAutoLayoutCount"] == 1
    assert {"kind": "deferred_auto_layout", "count": 3, "weight": 1, "cost": 3} in report["repairCost"]["items"]


def test_design_token_summary_counts_candidates_and_coverage(tmp_path: Path) -> None:
    report = quality_report(
        tmp_path,
        tokens={"summary": {"colorTokenCount": 2, "textStyleTokenCount": 1, "radiusTokenCount": 1, "spacingTokenCount": 3, "tokenCoverage": 1.0}},
    )

    assert report["qualitySummary"]["designTokenCandidateCount"] == 7
    assert report["qualitySummary"]["tokenCoverage"] == 1.0
    assert report["riskSummary"]["tokenGapCount"] == 0


def test_missing_tokens_create_small_token_gap_cost(tmp_path: Path) -> None:
    report = quality_report(tmp_path, tokens={"summary": {}})

    assert report["riskSummary"]["tokenGapCount"] == 1
    assert {"kind": "token_gaps", "count": 1, "weight": 1, "cost": 1} in report["repairCost"]["items"]


def test_materialization_warnings_and_skips_add_cost(tmp_path: Path) -> None:
    report = quality_report(
        tmp_path,
        materialization={"summary": {"visibleNodeCount": 4, "skippedReasons": {"missing_text": 2}}, "warnings": ["ocr_warning"]},
    )

    assert report["riskSummary"]["materializationWarningCount"] == 1
    assert report["riskSummary"]["materializationSkippedCount"] == 2
    assert {"kind": "materialization_warnings", "count": 1, "weight": 3, "cost": 3} in report["repairCost"]["items"]
    assert {"kind": "materialization_skips", "count": 2, "weight": 2, "cost": 4} in report["repairCost"]["items"]


def test_non_actionable_materialization_skips_do_not_add_repair_cost(tmp_path: Path) -> None:
    report = quality_report(
        tmp_path,
        materialization={
            "summary": {
                "visibleNodeCount": 4,
                "skippedReasons": {
                    "diagnostic_only": 93,
                    "suppress_duplicate": 2,
                    "preserve_in_parent_raster": 3,
                    "missing_text": 1,
                },
            }
        },
    )

    assert report["riskSummary"]["materializationTotalSkippedCount"] == 99
    assert report["riskSummary"]["materializationNonActionableSkippedCount"] == 98
    assert report["riskSummary"]["materializationSkippedCount"] == 1
    assert {"kind": "materialization_skips", "count": 1, "weight": 2, "cost": 2} in report["repairCost"]["items"]


def quality_report(
    tmp_path: Path,
    *,
    ownership: dict | None = None,
    hierarchy: dict | None = None,
    sibling: dict | None = None,
    layout: dict | None = None,
    permission: dict | None = None,
    tokens: dict | None = None,
    materialization: dict | None = None,
) -> dict:
    result = extract_m29_b_stage_quality_report(
        task_id="task_b_stage_quality",
        ownership_report=ownership or {"summary": {}},
        hierarchy_report=hierarchy or {"summary": {}},
        sibling_group_report=sibling or {"summary": {}},
        layout_energy_report=layout or {"summary": {}},
        auto_layout_permission_report=permission or {"summary": {}},
        design_token_report=tokens or {"summary": {"colorTokenCount": 1}},
        materialization_report=materialization or {"summary": {}},
        output_dir=tmp_path / "m29_b_stage_quality",
    )
    assert (tmp_path / "m29_b_stage_quality" / "b_stage_quality_report.json").exists()
    return result.report
