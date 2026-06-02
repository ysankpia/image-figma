from __future__ import annotations

import argparse
import html
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from collections import Counter

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Mechanical migration from PSD-like V1 oracle. Keep behavior changes out of this stage.


def write_diagnostics(output_path: Path, layer_stack: dict[str, Any]) -> None:
    diagnostics = layer_stack["diagnostics"]
    lines = [
        "# PSD-like Layer Decomposition Diagnostics",
        "",
        f"- source: `{layer_stack['sourceImage']}`",
        f"- ocr: `{layer_stack.get('ocr', '')}`",
        f"- canvas: {layer_stack['canvas']['width']}x{layer_stack['canvas']['height']}",
        f"- layers: {diagnostics['layerCount']}",
        f"- text layers: {diagnostics['textLayerCount']}",
        f"- raster layers: {diagnostics['rasterLayerCount']}",
        f"- shape layers: {diagnostics['shapeLayerCount']}",
        f"- surface shape layers: {diagnostics.get('surfaceShapeLayerCount', 0)}",
        f"- control surface shape layers: {diagnostics.get('controlSurfaceShapeLayerCount', 0)}",
        f"- page background: {diagnostics.get('pageBackground', '')}",
        f"- rejected candidates: {diagnostics['rejectedCandidateCount']}",
        f"- full page visible raster: {diagnostics['fullPageVisibleRaster']}",
        f"- tiny raster fragments: {diagnostics['tinyRasterFragments']}",
        f"- text overlap raster: {diagnostics['textOverlapRaster']}",
        f"- raw text overlap raster: {diagnostics['rawTextOverlapRaster']}",
        f"- raster text knockout: {diagnostics['rasterTextKnockoutCount']}",
        f"- text-owned raster suppressed: {diagnostics.get('textOwnedRasterSuppressedCount', 0)}",
        f"- raster covered text blocks: {diagnostics['rasterCoveredTextBlockCount']}",
        f"- missing assets: {diagnostics['missingAssetCount']}",
        "",
    ]
    semantic = layer_stack.get("semanticEvidence")
    if semantic:
        lines.extend(
            [
                "## Model Semantic Evidence",
                "",
                f"- present: {diagnostics.get('modelEvidencePresent', False)}",
                f"- detections: {diagnostics.get('modelDetectionCount', 0)}",
                f"- control detections: {diagnostics.get('modelControlDetectionCount', 0)}",
                f"- media detections: {diagnostics.get('modelMediaDetectionCount', 0)}",
                f"- structure detections: {diagnostics.get('modelStructureDetectionCount', 0)}",
                f"- semantic tags: {diagnostics.get('semanticTagCount', 0)}",
                f"- OCR overlap risks: {diagnostics.get('modelOcrOverlapRiskCount', 0)}",
                f"- model control accepted/rejected: {diagnostics.get('modelControlAcceptedCount', 0)}/{diagnostics.get('modelControlRejectedCount', 0)}",
                f"- model media accepted/rejected: {diagnostics.get('modelMediaAcceptedCount', 0)}/{diagnostics.get('modelMediaRejectedCount', 0)}",
                f"- model media added/merged/limited: {diagnostics.get('modelMediaAddedRasterCount', 0)}/{diagnostics.get('modelMediaMergedRasterCount', 0)}/{diagnostics.get('modelMediaLimitedRasterCount', 0)}",
                f"- model media-owned text suppressed: {diagnostics.get('modelMediaOwnedTextSuppressedCount', 0)}",
                f"- ignored reason: `{diagnostics.get('modelEvidenceIgnoredReason', '')}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Rejection Reasons",
            "",
        ]
    )
    counts: dict[str, int] = {}
    for item in layer_stack.get("rejected", []):
        key = f"{item.get('kind')}:{item.get('reason')}"
        counts[key] = counts.get(key, 0) + 1
    if counts:
        for key, count in sorted(counts.items()):
            lines.append(f"- {key}: {count}")
    else:
        lines.append("- none")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_ownership_report(output_path: Path, layer_stack: dict[str, Any]) -> None:
    raster_layers = [layer for layer in layer_stack["layers"] if layer["type"] == "raster"]
    text_layers = [layer for layer in layer_stack["layers"] if layer["type"] == "text"]
    coverage_by_text: dict[str, list[dict[str, Any]]] = {layer["id"]: [] for layer in text_layers}

    for raster in raster_layers:
        ownership = raster.get("ownership", {})
        for block in ownership.get("coveredTextBlocks", []):
            text_id = str(block.get("id", ""))
            if text_id in coverage_by_text:
                coverage_by_text[text_id].append(
                    {
                        "rasterId": raster["id"],
                        "coverage": block.get("coverage", 0),
                    }
                )

    report = {
        "version": "psd_like_ownership_report.v1",
        "diagnostics": {
            "rasterLayerCount": len(raster_layers),
            "textLayerCount": len(text_layers),
            "visibleTextOwnershipConflict": layer_stack["diagnostics"]["textOverlapRaster"],
            "rasterTextKnockoutCount": layer_stack["diagnostics"]["rasterTextKnockoutCount"],
            "rasterCoveredTextBlockCount": layer_stack["diagnostics"]["rasterCoveredTextBlockCount"],
        },
        "rasterOwnership": [
            {
                "id": layer["id"],
                "bbox": layer["bbox"],
                "asset": layer.get("asset", ""),
                "ownership": layer.get("ownership", {}),
            }
            for layer in raster_layers
        ],
        "textCoverage": coverage_by_text,
    }
    if layer_stack.get("semanticEvidence"):
        report["diagnostics"]["semanticTagCount"] = layer_stack["diagnostics"].get("semanticTagCount", 0)
        report["diagnostics"]["modelOcrOverlapRiskCount"] = layer_stack["diagnostics"].get("modelOcrOverlapRiskCount", 0)
        report["semanticEvidence"] = layer_stack["semanticEvidence"]
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_semantic_audit_artifacts(out_dir: Path, layer_stack: dict[str, Any], semantic_evidence_path: Path | None) -> None:
    if semantic_evidence_path is None or not semantic_evidence_path.exists():
        return
    try:
        artifact = json.loads(semantic_evidence_path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(artifact, dict) or artifact.get("version") != "semantic_evidence.v1":
        return

    detections = list(artifact.get("detections") or [])
    matches = list(artifact.get("matches") or [])
    layer_tags = artifact.get("layerTags") or {}
    ownership_decisions = list(artifact.get("ownershipDecisions") or [])
    diagnostics = layer_stack.get("diagnostics", {})

    decision_counts = Counter(str(item.get("decision", "")) for item in ownership_decisions)
    reason_counts = Counter(str(item.get("reason", "")) for item in ownership_decisions if item.get("reason"))
    class_counts = Counter(str(item.get("className", "")) for item in detections)
    tag_counts = Counter(str(tag.get("tag", "")) for tags in layer_tags.values() for tag in tags)
    match_decision_counts = Counter(str(item.get("decision", "")) for item in matches)

    tags_summary = {
        "version": "semantic_tags_summary.v1",
        "source": artifact.get("source", ""),
        "diagnostics": {
            "modelDetectionCount": len(detections),
            "semanticTagCount": sum(len(tags) for tags in layer_tags.values()),
            "matchedLayerCount": len(layer_tags),
            "modelOwnershipDecisionCount": len(ownership_decisions),
            "modelOcrOverlapRiskCount": diagnostics.get("modelOcrOverlapRiskCount", 0),
            "modelControlAcceptedCount": diagnostics.get("modelControlAcceptedCount", 0),
            "modelMediaAcceptedCount": diagnostics.get("modelMediaAcceptedCount", 0),
        },
        "rawDetectionClassCounts": dict(sorted(class_counts.items())),
        "semanticTagCounts": dict(sorted(tag_counts.items())),
        "matchDecisionCounts": dict(sorted(match_decision_counts.items())),
        "ownershipDecisionCounts": dict(sorted(decision_counts.items())),
        "ownershipReasonCounts": dict(sorted(reason_counts.items())),
    }
    (out_dir / "semantic_tags_summary.json").write_text(
        json.dumps(tags_summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    decisions_payload = {
        "version": "model_ownership_decisions.v1",
        "source": artifact.get("source", ""),
        "summary": {
            "decisionCounts": dict(sorted(decision_counts.items())),
            "reasonCounts": dict(sorted(reason_counts.items())),
            "acceptedCount": sum(1 for item in ownership_decisions if str(item.get("decision", "")).startswith("accepted_")),
            "rejectedCount": sum(1 for item in ownership_decisions if str(item.get("decision", "")).startswith("rejected_")),
        },
        "decisions": ownership_decisions,
    }
    (out_dir / "model_ownership_decisions.v1.json").write_text(
        json.dumps(decisions_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    write_semantic_evidence_report(
        out_dir / "semantic_evidence_report.md",
        layer_stack=layer_stack,
        artifact=artifact,
        tags_summary=tags_summary,
        decisions_payload=decisions_payload,
    )


def write_semantic_evidence_report(
    output_path: Path,
    layer_stack: dict[str, Any],
    artifact: dict[str, Any],
    tags_summary: dict[str, Any],
    decisions_payload: dict[str, Any],
) -> None:
    diagnostics = layer_stack.get("diagnostics", {})
    lines = [
        "# Semantic Evidence Report",
        "",
        f"- source: `{artifact.get('source', '')}`",
        f"- model detections: {tags_summary['diagnostics']['modelDetectionCount']}",
        f"- semantic tags: {tags_summary['diagnostics']['semanticTagCount']}",
        f"- matched layers: {tags_summary['diagnostics']['matchedLayerCount']}",
        f"- ownership decisions: {tags_summary['diagnostics']['modelOwnershipDecisionCount']}",
        f"- OCR overlap risks: {tags_summary['diagnostics']['modelOcrOverlapRiskCount']}",
        "",
        "## Raw Model Detections",
        "",
    ]
    append_counts(lines, tags_summary.get("rawDetectionClassCounts", {}))
    lines.extend(["", "## Matched Semantic Tags", ""])
    append_counts(lines, tags_summary.get("semanticTagCounts", {}))
    lines.extend(["", "## Match Decisions", ""])
    append_counts(lines, tags_summary.get("matchDecisionCounts", {}))
    lines.extend(["", "## Visible Ownership Decisions", ""])
    append_counts(lines, decisions_payload.get("summary", {}).get("decisionCounts", {}))
    lines.extend(["", "## Accepted And Rejected Reasons", ""])
    append_counts(lines, decisions_payload.get("summary", {}).get("reasonCounts", {}))
    lines.extend(
        [
            "",
            "## Visible Change Summary",
            "",
            f"- model control accepted: {diagnostics.get('modelControlAcceptedCount', 0)}",
            f"- model control rejected: {diagnostics.get('modelControlRejectedCount', 0)}",
            f"- model media accepted: {diagnostics.get('modelMediaAcceptedCount', 0)}",
            f"- model media rejected: {diagnostics.get('modelMediaRejectedCount', 0)}",
            f"- model media added raster: {diagnostics.get('modelMediaAddedRasterCount', 0)}",
            f"- model media merged raster: {diagnostics.get('modelMediaMergedRasterCount', 0)}",
            f"- model media limited raster: {diagnostics.get('modelMediaLimitedRasterCount', 0)}",
            f"- model media-owned text suppressed: {diagnostics.get('modelMediaOwnedTextSuppressedCount', 0)}",
            "",
            "## Guardrail Signals",
            "",
            f"- missing assets: {diagnostics.get('missingAssetCount', 0)}",
            f"- shape assets: {diagnostics.get('shapeAssetCount', 0)}",
            f"- full-page visible raster: {diagnostics.get('fullPageVisibleRaster', 0)}",
            f"- raw text overlap raster: {diagnostics.get('rawTextOverlapRaster', 0)}",
            f"- raster text knockout: {diagnostics.get('rasterTextKnockoutCount', 0)}",
        ]
    )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_counts(lines: list[str], counts: dict[str, Any]) -> None:
    if not counts:
        lines.append("- none")
        return
    for key, count in sorted(counts.items()):
        lines.append(f"- {key or 'unknown'}: {count}")
