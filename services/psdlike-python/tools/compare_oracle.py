#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools._eval_common import compute_visual_metrics, validate_basic_dsl


METRIC_KEYS = [
    "textLayerCount",
    "visibleTextLayerCount",
    "mediaOwnedTextBlockCount",
    "mediaTextOwnerRasterCount",
    "rasterLayerCount",
    "shapeLayerCount",
    "surfaceShapeLayerCount",
    "controlSurfaceShapeLayerCount",
    "ocrAnchoredControlSurfaceCount",
    "controlOwnedRasterSuppressedCount",
    "textOwnedRasterSuppressedCount",
    "shapeAssetCount",
    "missingAssetCount",
    "tinyRasterFragments",
    "fullPageVisibleRaster",
    "textOverlapRaster",
    "rawTextOverlapRaster",
    "rasterTextKnockoutCount",
    "rasterCoveredTextBlockCount",
]


def main() -> None:
    args = parse_args()
    oracle_dir = Path(args.oracle).expanduser().resolve()
    candidate_dir = Path(args.candidate).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve() if args.out else candidate_dir / "oracle_compare.md"
    report = compare_outputs(oracle_dir, candidate_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_report(report, oracle_dir, candidate_dir), encoding="utf-8")
    json_path = out_path.with_suffix(".json")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"oracle compare: {out_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare old V1 oracle output with clean Python service output.")
    parser.add_argument("--oracle", required=True, help="Old V1 output directory.")
    parser.add_argument("--candidate", required=True, help="New service output directory.")
    parser.add_argument("--out", default="", help="Markdown report path. Defaults to <candidate>/oracle_compare.md.")
    return parser.parse_args()


def compare_outputs(oracle_dir: Path, candidate_dir: Path) -> dict[str, Any]:
    oracle_stack = read_json(oracle_dir / "layer_stack.v1.json")
    candidate_stack = read_json(candidate_dir / "layer_stack.v1.json")
    oracle_dsl_valid, oracle_dsl_errors = validate_basic_dsl(oracle_dir / "draft_runtime.dsl.v1_0.json", oracle_dir)
    candidate_dsl_valid, candidate_dsl_errors = validate_basic_dsl(
        candidate_dir / "draft_runtime.dsl.v1_0.json",
        candidate_dir,
    )
    source_path = Path(str(candidate_stack.get("sourceImage") or oracle_stack.get("sourceImage") or ""))
    visual = {}
    if source_path.exists():
        visual = {
            "oracle": compute_visual_metrics(source_path, oracle_dir / "draft_preview.png"),
            "candidate": compute_visual_metrics(source_path, candidate_dir / "draft_preview.png"),
        }
    oracle_diag = oracle_stack.get("diagnostics", {})
    candidate_diag = candidate_stack.get("diagnostics", {})
    metrics = {
        key: {
            "oracle": oracle_diag.get(key, 0),
            "candidate": candidate_diag.get(key, 0),
            "delta": numeric(candidate_diag.get(key, 0)) - numeric(oracle_diag.get(key, 0)),
        }
        for key in METRIC_KEYS
    }
    return {
        "version": "psdlike_python_oracle_compare.v1",
        "oracleDir": str(oracle_dir),
        "candidateDir": str(candidate_dir),
        "dsl": {
            "oracleValid": oracle_dsl_valid,
            "candidateValid": candidate_dsl_valid,
            "oracleErrors": oracle_dsl_errors,
            "candidateErrors": candidate_dsl_errors,
        },
        "metrics": metrics,
        "layerMatches": layer_match_summary(oracle_stack, candidate_stack),
        "visual": visual,
        "hardGate": hard_gate(metrics, candidate_dsl_valid),
    }


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def numeric(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def layer_match_summary(oracle_stack: dict[str, Any], candidate_stack: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for kind in ["text", "raster", "shape"]:
        oracle_layers = [layer for layer in oracle_stack.get("layers", []) if layer.get("type") == kind]
        candidate_layers = [layer for layer in candidate_stack.get("layers", []) if layer.get("type") == kind]
        matches = greedy_bbox_matches(oracle_layers, candidate_layers)
        summary[kind] = {
            "oracleCount": len(oracle_layers),
            "candidateCount": len(candidate_layers),
            "matchedCount": len(matches),
            "averageIou": round(sum(item["iou"] for item in matches) / max(1, len(matches)), 4),
        }
    return summary


def greedy_bbox_matches(oracle_layers: list[dict[str, Any]], candidate_layers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    used: set[int] = set()
    for oracle in oracle_layers:
        best_index = -1
        best_iou = 0.0
        for index, candidate in enumerate(candidate_layers):
            if index in used:
                continue
            score = bbox_iou(oracle.get("bbox", {}), candidate.get("bbox", {}))
            if score > best_iou:
                best_iou = score
                best_index = index
        if best_index >= 0 and best_iou >= 0.50:
            used.add(best_index)
            pairs.append({"oracleId": oracle.get("id"), "candidateId": candidate_layers[best_index].get("id"), "iou": best_iou})
    return pairs


def bbox_iou(a: dict[str, Any], b: dict[str, Any]) -> float:
    ax1 = numeric(a.get("x"))
    ay1 = numeric(a.get("y"))
    ax2 = ax1 + numeric(a.get("width"))
    ay2 = ay1 + numeric(a.get("height"))
    bx1 = numeric(b.get("x"))
    by1 = numeric(b.get("y"))
    bx2 = bx1 + numeric(b.get("width"))
    by2 = by1 + numeric(b.get("height"))
    inter = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))
    union = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1) + max(0.0, bx2 - bx1) * max(0.0, by2 - by1) - inter
    return 0.0 if union <= 0 else inter / union


def hard_gate(metrics: dict[str, dict[str, Any]], candidate_dsl_valid: bool) -> dict[str, Any]:
    failures: list[str] = []
    if not candidate_dsl_valid:
        failures.append("DSL_INVALID")
    if numeric(metrics["missingAssetCount"]["candidate"]) > 0:
        failures.append("MISSING_ASSET")
    if numeric(metrics["shapeAssetCount"]["candidate"]) > 0:
        failures.append("SHAPE_ASSET")
    if numeric(metrics["fullPageVisibleRaster"]["candidate"]) > 0:
        failures.append("FULL_PAGE_BACKING")
    return {"passed": not failures, "failures": failures}


def render_report(report: dict[str, Any], oracle_dir: Path, candidate_dir: Path) -> str:
    lines = [
        "# PSD-like Python Oracle Compare",
        "",
        f"- oracle: `{oracle_dir}`",
        f"- candidate: `{candidate_dir}`",
        f"- hard gate: `{json.dumps(report['hardGate'], ensure_ascii=False)}`",
        f"- dsl: `{json.dumps(report['dsl'], ensure_ascii=False)}`",
        "",
        "## Metrics",
        "",
        "| metric | oracle | candidate | delta |",
        "|---|---:|---:|---:|",
    ]
    for key, item in report["metrics"].items():
        delta = item["delta"]
        if isinstance(delta, float) and math.isclose(delta, round(delta)):
            delta = int(delta)
        lines.append(f"| {key} | {item['oracle']} | {item['candidate']} | {delta} |")
    lines.extend(["", "## Layer BBox Match", "", "```json", json.dumps(report["layerMatches"], ensure_ascii=False, indent=2), "```"])
    if report.get("visual"):
        lines.extend(["", "## Visual", "", "```json", json.dumps(report["visual"], ensure_ascii=False, indent=2), "```"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
