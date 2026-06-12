from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..image_math import build_scale_profile
from ..png_tools import UnsupportedPngCropError, decode_png_pixels
from .alpha import analyze_transparent_asset_candidate
from .candidates import collect_transparent_asset_candidates
from .normalization import normalize_media_internal_candidates, normalize_ocr_blocks, normalize_source_objects
from .report import build_summary
from .types import M29TransparentAssetResult, REPORT_ONLY_META
from .validation import validate_transparent_asset_report


def extract_m29_transparent_asset_report(
    *,
    task_id: str,
    source_png: bytes,
    ocr_document: dict[str, Any],
    m292_document: dict[str, Any],
    media_internal_report: dict[str, Any] | None,
    output_dir: Path,
) -> M29TransparentAssetResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    try:
        pixels = decode_png_pixels(source_png)
    except UnsupportedPngCropError as error:
        pixels = None
        warnings.append(f"source_png_decode_failed:{error}")

    source_objects, source_warnings = normalize_source_objects(m292_document.get("sourceObjects", []))
    ocr_blocks, ocr_warnings = normalize_ocr_blocks(ocr_document.get("blocks", []))
    internal_candidates, internal_warnings = normalize_media_internal_candidates((media_internal_report or {}).get("internalCandidates", []))
    warnings.extend(source_warnings + ocr_warnings + internal_warnings)

    image_size = {"width": pixels.width, "height": pixels.height} if pixels is not None else image_size_from(ocr_document, m292_document)
    scale_profile = build_scale_profile(image_size=image_size, ocr_blocks=ocr_blocks, source_objects=source_objects)
    candidates = collect_transparent_asset_candidates(
        source_objects=source_objects,
        ocr_blocks=ocr_blocks,
        media_internal_candidates=internal_candidates,
        image_size=image_size,
        scale_profile=scale_profile,
    )
    items = [
        build_report_item(candidate, pixels, output_dir / "assets" / "transparent" / f"{candidate['candidateId']}.png")
        for candidate in candidates
    ]
    report_path = output_dir / "transparent_asset_report.json"
    report = {
        "schemaName": "M29TransparentAssetReport",
        "schemaVersion": "0.1",
        "taskId": task_id,
        "sourceSchemaName": m292_document.get("schemaName"),
        "sourceSchemaVersion": m292_document.get("schemaVersion"),
        "mediaInternalSchemaName": (media_internal_report or {}).get("schemaName"),
        "mediaInternalSchemaVersion": (media_internal_report or {}).get("schemaVersion"),
        "outputReport": str(report_path),
        "summary": build_summary(source_objects=source_objects, candidates=candidates, items=items, warnings=warnings),
        "items": items,
        "warnings": warnings,
        "meta": {
            "createdAt": datetime.now(UTC).isoformat(),
            "truthSource": "source_png_plus_ocr_plus_m29_2_plus_m29_6",
            "scaleProfile": scale_profile.to_dict(),
            **REPORT_ONLY_META,
        },
    }
    validate_transparent_asset_report(report)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return M29TransparentAssetResult(report=report, output_dir=output_dir)


def build_report_item(candidate: dict[str, Any], pixels: Any, asset_path: Path) -> dict[str, Any]:
    if pixels is None:
        analysis = rejected_analysis("source_png_decode_failed")
    elif not candidate["candidateAllowedForAlpha"]:
        analysis = rejected_analysis(candidate["preflightRisks"][0] if candidate["preflightRisks"] else "candidate_preflight_rejected")
    else:
        analysis = analyze_transparent_asset_candidate(
            pixels=pixels,
            bbox=candidate["bbox"],
            output_path=str(asset_path),
            write_asset=True,
            expand_context=candidate["source"] == "m29_6_internal_icon_candidate",
            container_bbox=candidate.get("mediaBbox") if candidate["source"] == "m29_6_internal_icon_candidate" else None,
            alpha_profile=str(candidate.get("alphaProfile") or "default_icon"),
        )
    gate = split_gate_decision(candidate, analysis)
    return {
        "candidateId": candidate["candidateId"],
        "source": candidate["source"],
        "sourceObjectId": candidate["sourceObjectId"],
        "mediaSourceObjectId": candidate["mediaSourceObjectId"],
        "bbox": candidate["bbox"],
        "analysisBbox": analysis.get("analysisBbox"),
        "decision": analysis["decision"],
        "assetPath": relative_asset_path(analysis.get("assetPath"), "m29_transparent_assets"),
        "backgroundRgb": analysis["backgroundRgb"],
        "bgVariance": analysis["bgVariance"],
        "backgroundCoverage": analysis.get("backgroundCoverage", 0.0),
        "foregroundAreaRatio": analysis["foregroundAreaRatio"],
        "alphaCoverage": analysis["alphaCoverage"],
        "largestComponentRatio": analysis["largestComponentRatio"],
        "edgeAlphaMean": analysis["edgeAlphaMean"],
        "edgeAlphaCoverageGt32": analysis["edgeAlphaCoverageGt32"],
        "textOverlap": round(float(candidate["textOverlap"]), 6),
        "inputConfidence": candidate["inputConfidence"],
        "inputScore": candidate["inputScore"],
        "alphaProfile": candidate.get("alphaProfile") or "default_icon",
        "controlRowSupportedExecution": candidate.get("controlRowSupportedExecution") is True,
        "analysisAllowed": gate["analysisAllowed"],
        "assetGenerated": gate["assetGenerated"],
        "visibleReplayEligible": gate["visibleReplayEligible"],
        "cleanupEligible": gate["cleanupEligible"],
        "gateDecision": gate,
        "reasons": candidate["preflightReasons"] + [reason for reason in analysis["reasons"] if reason not in candidate["preflightReasons"]],
        "risks": candidate["preflightRisks"] + [risk for risk in analysis["risks"] if risk not in candidate["preflightRisks"]],
        "reportOnly": True,
    }


def split_gate_decision(candidate: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    analysis_allowed = bool(candidate.get("candidateAllowedForAlpha"))
    asset_generated = analysis.get("decision") == "allow" and bool(analysis.get("assetPath"))
    execution_supported = candidate.get("executionSupportedForVisibleReplay")
    control_row_supported = candidate.get("controlRowSupportedExecution") is True
    control_row_source_crop_eligible = (
        analysis_allowed
        and control_row_supported
        and execution_supported is True
        and not asset_generated
        and analysis.get("decision") == "reject"
        and first_analysis_reason(analysis) in {"edge_alpha_risk", "unstable_background"}
    )
    visible_replay_eligible = (analysis_allowed and asset_generated and (execution_supported is not False)) or control_row_source_crop_eligible
    return {
        "analysisAllowed": analysis_allowed,
        "assetGenerated": asset_generated,
        "visibleReplayEligible": visible_replay_eligible,
        "controlRowSourceCropEligible": control_row_source_crop_eligible,
        "cleanupEligible": False,
        "cleanupEligibilityReason": "m29_5_replay_plan_authorizes_cleanup",
        "visibleReplayReason": visible_replay_reason(
            analysis_allowed=analysis_allowed,
            asset_generated=asset_generated,
            execution_supported=execution_supported,
            control_row_source_crop_eligible=control_row_source_crop_eligible,
            visible_replay_eligible=visible_replay_eligible,
        ),
    }


def visible_replay_reason(
    *,
    analysis_allowed: bool,
    asset_generated: bool,
    execution_supported: Any,
    control_row_source_crop_eligible: bool,
    visible_replay_eligible: bool,
) -> str:
    if visible_replay_eligible and control_row_source_crop_eligible:
        return "control_row_source_crop_visible_replay_alpha_cleanup_blocked"
    if visible_replay_eligible:
        return "asset_generated_and_alpha_quality_passed"
    if not analysis_allowed:
        return "alpha_analysis_not_allowed"
    if not asset_generated:
        return "alpha_asset_not_generated"
    if execution_supported is False:
        return "analysis_only_without_visible_replay_support"
    return "not_visible_replay_eligible"


def first_analysis_reason(analysis: dict[str, Any]) -> str:
    reasons = analysis.get("reasons")
    if isinstance(reasons, list) and reasons:
        return str(reasons[0] or "")
    return ""


def rejected_analysis(reason: str) -> dict[str, Any]:
    return {
        "decision": "reject",
        "assetPath": None,
        "backgroundRgb": [0, 0, 0],
        "bgVariance": 0.0,
        "foregroundAreaRatio": 0.0,
        "alphaCoverage": 0.0,
        "largestComponentRatio": 0.0,
        "edgeAlphaMean": 0.0,
        "edgeAlphaCoverageGt32": 0.0,
        "reasons": [reason],
        "risks": ["transparent_asset_rejected"],
    }


def relative_asset_path(value: Any, output_dir_name: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    marker = f"/{output_dir_name}/"
    if marker in text:
        return text.split(marker, 1)[1]
    return text


def image_size_from(*documents: dict[str, Any]) -> dict[str, int]:
    for document in documents:
        value = document.get("imageSize")
        if not isinstance(value, dict):
            continue
        width = int(value.get("width") or 0)
        height = int(value.get("height") or 0)
        if width > 0 and height > 0:
            return {"width": width, "height": height}
    return {}
