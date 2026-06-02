#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path
import sys
from typing import Any

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools._eval_common import InputCase, cases_from_manifest


CONTROL_CLASSES = {"TextButton", "EditText", "Spinner", "Switch", "CheckedTextView", "Multi_Tab", "Bottom_Navigation"}
MEDIA_CLASSES = {"Image", "Icon", "BackgroundImage", "Map"}
STRUCTURE_CLASSES = {"Card", "Toolbar", "Modal", "Drawer", "UpperTaskBar", "Bottom_Navigation"}
DANGEROUS_TEXT_CLASSES = {"Text", "TextButton", "EditText", "CheckedTextView"}


def main() -> None:
    args = parse_args()
    model_path = Path(args.model).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    current_output = Path(args.current_output).expanduser().resolve()
    manifest_path = Path(args.manifest).expanduser().resolve()
    cases = cases_from_manifest(manifest_path)
    if args.limit:
        cases = cases[: args.limit]

    model = load_model(model_path)
    rows: list[dict[str, Any]] = []
    print(f"model evidence eval: cases={len(cases)} model={model_path} out={out_dir}", flush=True)
    for index, case in enumerate(cases, start=1):
        started = time.monotonic()
        print(f"[{index}/{len(cases)}] {case.case_id} {case.source_path}", flush=True)
        row = run_case(case, model, model_path, current_output, out_dir, args)
        row["runtimeSeconds"] = round(time.monotonic() - started, 2)
        rows.append(row)
        write_summary(out_dir, rows, model_path)
    write_contact_sheet(out_dir / "source_draft_overlay_model_contact_sheet.png", rows, current_output, out_dir)
    print(f"done: {out_dir / 'model_assist_summary.md'}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate YOLO model evidence against PSD-like physical layers.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--current-output", required=True, help="PSD-like batch output root containing <case>/layer_stack.v1.json.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.20)
    parser.add_argument("--iou", type=float, default=0.50)
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def load_model(model_path: Path) -> Any:
    try:
        from ultralytics import YOLO
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("ultralytics is required for model evidence eval") from exc
    return YOLO(str(model_path))


def run_case(
    case: InputCase,
    model: Any,
    model_path: Path,
    current_output: Path,
    out_root: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    case_out = out_root / case.case_id
    case_out.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {
        "case": case.case_id,
        "sourcePath": str(case.source_path),
        "sha256": case.sha256,
        "ok": False,
        "error": "",
    }
    try:
        layer_stack_path = current_output / case.case_id / "layer_stack.v1.json"
        layer_stack = json.loads(layer_stack_path.read_text(encoding="utf-8"))
        with Image.open(case.source_path) as image:
            width, height = image.size
        detections = run_model(case.source_path, model, args)
        layers = normalize_layers(layer_stack)
        matches = match_detections_to_layers(detections, layers)
        evidence = build_evidence_payload(case, model_path, width, height, detections, matches, layer_stack)
        (case_out / "model_evidence.v1.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        draw_model_overlay(case.source_path, case_out / "model_overlay.png", detections, matches)
        write_match_report(case_out / "model_match_report.md", evidence)
        metrics = case_metrics(layer_stack, detections, matches)
        row.update(metrics)
        row["ok"] = True
        return row
    except Exception as exc:  # noqa: BLE001
        error_payload = {
            "version": "model_evidence_error.v1",
            "case": case.case_id,
            "errorType": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        (case_out / "model_error.v1.json").write_text(
            json.dumps(error_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        row["error"] = f"{type(exc).__name__}: {exc}"
        return row


def run_model(image_path: Path, model: Any, args: argparse.Namespace) -> list[dict[str, Any]]:
    results = model.predict(
        source=str(image_path),
        imgsz=args.imgsz,
        conf=args.conf,
        iou=args.iou,
        device=args.device,
        verbose=False,
    )
    result = results[0]
    names = result.names
    detections: list[dict[str, Any]] = []
    for index, box in enumerate(result.boxes, start=1):
        xyxy = box.xyxy[0].cpu().numpy()
        cls_id = int(box.cls[0].cpu().item())
        detections.append(
            {
                "id": f"det_{index:04d}",
                "classId": cls_id,
                "className": str(names.get(cls_id, cls_id)),
                "confidence": round(float(box.conf[0].cpu().item()), 4),
                "bbox": {
                    "x": int(round(float(xyxy[0]))),
                    "y": int(round(float(xyxy[1]))),
                    "width": max(1, int(round(float(xyxy[2] - xyxy[0])))),
                    "height": max(1, int(round(float(xyxy[3] - xyxy[1])))),
                },
            }
        )
    return detections


def normalize_layers(layer_stack: dict[str, Any]) -> list[dict[str, Any]]:
    layers: list[dict[str, Any]] = []
    for layer in layer_stack.get("layers", []):
        layer_type = str(layer.get("type", ""))
        if layer_type not in {"shape", "raster", "text"}:
            continue
        bbox = layer.get("bbox") or {}
        layers.append(
            {
                "id": str(layer.get("id", "")),
                "type": layer_type,
                "reason": str(layer.get("reason", "")),
                "bbox": {
                    "x": int(bbox.get("x", 0)),
                    "y": int(bbox.get("y", 0)),
                    "width": int(bbox.get("width", 0)),
                    "height": int(bbox.get("height", 0)),
                },
            }
        )
    return layers


def match_detections_to_layers(detections: list[dict[str, Any]], layers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for det in detections:
        best_by_type: dict[str, tuple[float, float, dict[str, Any] | None]] = {}
        for layer in layers:
            iou_score = bbox_iou(det["bbox"], layer["bbox"])
            det_ioa = bbox_ioa(det["bbox"], layer["bbox"])
            layer_ioa = bbox_ioa(layer["bbox"], det["bbox"])
            score = max(iou_score, det_ioa * 0.85, layer_ioa * 0.75)
            current = best_by_type.get(layer["type"])
            if current is None or score > current[0]:
                best_by_type[layer["type"]] = (score, iou_score, layer)
        for layer_type, (score, iou_score, layer) in best_by_type.items():
            if layer is None:
                continue
            det_ioa = bbox_ioa(det["bbox"], layer["bbox"])
            layer_ioa = bbox_ioa(layer["bbox"], det["bbox"])
            if score < 0.20:
                continue
            matches.append(
                {
                    "detectionId": det["id"],
                    "className": det["className"],
                    "layerId": layer["id"],
                    "layerKind": layer_type,
                    "layerReason": layer["reason"],
                    "iou": round(iou_score, 4),
                    "detectionCoverageByLayer": round(det_ioa, 4),
                    "layerCoverageByDetection": round(layer_ioa, 4),
                    "score": round(score, 4),
                    "decision": match_decision(det, layer, score, iou_score, det_ioa, layer_ioa),
                }
            )
    return matches


def match_decision(
    det: dict[str, Any],
    layer: dict[str, Any],
    score: float,
    iou_score: float,
    det_ioa: float,
    layer_ioa: float,
) -> str:
    class_name = det["className"]
    layer_type = layer["type"]
    if class_name in CONTROL_CLASSES and layer_type == "shape" and score >= 0.35:
        return "control_semantic_tag"
    if class_name in CONTROL_CLASSES and layer_type == "text" and layer_ioa >= 0.65:
        return "control_search_window_candidate"
    if class_name in MEDIA_CLASSES and layer_type == "raster" and score >= 0.30:
        return "media_semantic_tag"
    if class_name in MEDIA_CLASSES and layer_type != "raster" and det_ioa < 0.50:
        return "media_missing_physical_candidate"
    if class_name in STRUCTURE_CLASSES and score >= 0.30:
        return "structure_semantic_tag"
    if class_name in DANGEROUS_TEXT_CLASSES and layer_type == "raster" and det_ioa >= 0.35:
        return "ocr_overlap_risk"
    if iou_score >= 0.50:
        return "bbox_aligned"
    return "weak_match"


def build_evidence_payload(
    case: InputCase,
    model_path: Path,
    width: int,
    height: int,
    detections: list[dict[str, Any]],
    matches: list[dict[str, Any]],
    layer_stack: dict[str, Any],
) -> dict[str, Any]:
    return {
        "version": "model_evidence.v1",
        "model": {"path": str(model_path)},
        "sourceImage": str(case.source_path),
        "caseId": case.case_id,
        "sha256": case.sha256,
        "canvas": {"width": width, "height": height},
        "diagnostics": layer_stack.get("diagnostics", {}),
        "detections": detections,
        "matches": matches,
        "summary": summarize_case(detections, matches, layer_stack),
    }


def summarize_case(
    detections: list[dict[str, Any]],
    matches: list[dict[str, Any]],
    layer_stack: dict[str, Any],
) -> dict[str, Any]:
    class_counts = Counter(det["className"] for det in detections)
    decision_counts = Counter(match["decision"] for match in matches)
    matched_detection_ids = {match["detectionId"] for match in matches if match["decision"] not in {"weak_match"}}
    diagnostics = layer_stack.get("diagnostics", {})
    return {
        "detectionCount": len(detections),
        "classCounts": dict(sorted(class_counts.items())),
        "matchedDetectionCount": len(matched_detection_ids),
        "decisionCounts": dict(sorted(decision_counts.items())),
        "controlDetectionCount": sum(class_counts.get(name, 0) for name in CONTROL_CLASSES),
        "mediaDetectionCount": sum(class_counts.get(name, 0) for name in MEDIA_CLASSES),
        "structureDetectionCount": sum(class_counts.get(name, 0) for name in STRUCTURE_CLASSES),
        "currentControlSurfaceShapeLayerCount": diagnostics.get("controlSurfaceShapeLayerCount", 0),
        "currentRasterLayerCount": diagnostics.get("rasterLayerCount", 0),
        "rawTextOverlapRaster": diagnostics.get("rawTextOverlapRaster", 0),
        "rasterTextKnockoutCount": diagnostics.get("rasterTextKnockoutCount", 0),
    }


def case_metrics(
    layer_stack: dict[str, Any],
    detections: list[dict[str, Any]],
    matches: list[dict[str, Any]],
) -> dict[str, Any]:
    summary = summarize_case(detections, matches, layer_stack)
    decision_counts = Counter(match["decision"] for match in matches)
    class_counts = Counter(det["className"] for det in detections)
    diagnostics = layer_stack.get("diagnostics", {})
    return {
        "detectionCount": summary["detectionCount"],
        "controlDetectionCount": summary["controlDetectionCount"],
        "mediaDetectionCount": summary["mediaDetectionCount"],
        "structureDetectionCount": summary["structureDetectionCount"],
        "currentControlSurfaceShapeLayerCount": diagnostics.get("controlSurfaceShapeLayerCount", 0),
        "currentRasterLayerCount": diagnostics.get("rasterLayerCount", 0),
        "rawTextOverlapRaster": diagnostics.get("rawTextOverlapRaster", 0),
        "rasterTextKnockoutCount": diagnostics.get("rasterTextKnockoutCount", 0),
        "controlSemanticTagCount": decision_counts.get("control_semantic_tag", 0),
        "controlSearchWindowCandidateCount": decision_counts.get("control_search_window_candidate", 0),
        "mediaSemanticTagCount": decision_counts.get("media_semantic_tag", 0),
        "mediaMissingPhysicalCandidateCount": decision_counts.get("media_missing_physical_candidate", 0),
        "ocrOverlapRiskCount": decision_counts.get("ocr_overlap_risk", 0),
        "classCounts": dict(sorted(class_counts.items())),
        "decisionCounts": dict(sorted(decision_counts.items())),
    }


def draw_model_overlay(image_path: Path, output_path: Path, detections: list[dict[str, Any]], matches: list[dict[str, Any]]) -> None:
    with Image.open(image_path) as image:
        canvas = image.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    decisions_by_det: dict[str, list[str]] = defaultdict(list)
    for match in matches:
        decisions_by_det[match["detectionId"]].append(match["decision"])
    for det in detections:
        bbox = det["bbox"]
        cls = det["className"]
        color = class_color(cls)
        x1 = bbox["x"]
        y1 = bbox["y"]
        x2 = x1 + bbox["width"]
        y2 = y1 + bbox["height"]
        width = 3 if cls in CONTROL_CLASSES | MEDIA_CLASSES else 2
        draw.rectangle([x1, y1, x2, y2], outline=color, width=width)
        label = f"{cls} {det['confidence']:.2f}"
        decisions = decisions_by_det.get(det["id"], [])
        if decisions:
            label += f" {decisions[0]}"
        draw.rectangle([x1, max(0, y1 - 16), x1 + min(360, len(label) * 7), y1], fill=color)
        draw.text((x1 + 2, max(0, y1 - 15)), label, fill=(0, 0, 0))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def class_color(class_name: str) -> tuple[int, int, int]:
    if class_name in CONTROL_CLASSES:
        return (255, 80, 60)
    if class_name in MEDIA_CLASSES:
        return (40, 210, 220)
    if class_name in STRUCTURE_CLASSES:
        return (160, 100, 255)
    if class_name == "Text":
        return (255, 80, 220)
    return (80, 220, 80)


def write_match_report(path: Path, evidence: dict[str, Any]) -> None:
    summary = evidence["summary"]
    lines = [
        "# Model Evidence Match Report",
        "",
        f"- case: `{evidence['caseId']}`",
        f"- source: `{evidence['sourceImage']}`",
        f"- detections: {summary['detectionCount']}",
        f"- controls: {summary['controlDetectionCount']}",
        f"- media: {summary['mediaDetectionCount']}",
        f"- current control shapes: {summary['currentControlSurfaceShapeLayerCount']}",
        f"- rawTextOverlapRaster: {summary['rawTextOverlapRaster']}",
        f"- rasterTextKnockoutCount: {summary['rasterTextKnockoutCount']}",
        "",
        "## Class Counts",
        "",
        "```json",
        json.dumps(summary["classCounts"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Decision Counts",
        "",
        "```json",
        json.dumps(summary["decisionCounts"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Matches",
        "",
        "| detection | class | layer | kind | iou | detCoverage | layerCoverage | decision |",
        "|---|---|---|---|---:|---:|---:|---|",
    ]
    for match in evidence["matches"][:200]:
        lines.append(
            "|{detectionId}|{className}|{layerId}|{layerKind}|{iou}|{detectionCoverageByLayer}|{layerCoverageByDetection}|{decision}|".format(
                **match
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary(out_dir: Path, rows: list[dict[str, Any]], model_path: Path) -> None:
    aggregate = aggregate_rows(rows)
    payload = {
        "version": "model_assist_summary.v1",
        "model": str(model_path),
        "caseCount": len(rows),
        "okCaseCount": sum(1 for row in rows if row.get("ok")),
        "failedCaseCount": sum(1 for row in rows if not row.get("ok")),
        "aggregate": aggregate,
        "rows": rows,
    }
    (out_dir / "model_assist_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_summary_md(out_dir / "model_assist_summary.md", payload)


def aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok_rows = [row for row in rows if row.get("ok")]
    class_counts: Counter[str] = Counter()
    decision_counts: Counter[str] = Counter()
    for row in ok_rows:
        class_counts.update(row.get("classCounts", {}))
        decision_counts.update(row.get("decisionCounts", {}))
    low_control = [
        row
        for row in ok_rows
        if int(row.get("currentControlSurfaceShapeLayerCount", 0)) <= 1
        and int(row.get("controlDetectionCount", 0)) > 0
    ]
    high_risk = [
        row
        for row in ok_rows
        if int(row.get("rawTextOverlapRaster", 0)) > 0 or int(row.get("rasterTextKnockoutCount", 0)) > 0
    ]
    return {
        "detectionTotal": sum(int(row.get("detectionCount", 0)) for row in ok_rows),
        "controlDetectionTotal": sum(int(row.get("controlDetectionCount", 0)) for row in ok_rows),
        "mediaDetectionTotal": sum(int(row.get("mediaDetectionCount", 0)) for row in ok_rows),
        "classCounts": dict(sorted(class_counts.items())),
        "decisionCounts": dict(sorted(decision_counts.items())),
        "lowControlCasesWithModelControls": len(low_control),
        "highRiskCases": len(high_risk),
        "ocrOverlapRiskTotal": sum(int(row.get("ocrOverlapRiskCount", 0)) for row in ok_rows),
        "mediaMissingPhysicalCandidateTotal": sum(int(row.get("mediaMissingPhysicalCandidateCount", 0)) for row in ok_rows),
    }


def write_summary_md(path: Path, payload: dict[str, Any]) -> None:
    rows = payload["rows"]
    aggregate = payload["aggregate"]
    lines = [
        "# PSD-like Model Evidence Assist Summary",
        "",
        f"- model: `{payload['model']}`",
        f"- cases: {payload['caseCount']}",
        f"- ok cases: {payload['okCaseCount']}",
        f"- failed cases: {payload['failedCaseCount']}",
        f"- total detections: {aggregate['detectionTotal']}",
        f"- control detections: {aggregate['controlDetectionTotal']}",
        f"- media detections: {aggregate['mediaDetectionTotal']}",
        f"- low-control cases with model controls: {aggregate['lowControlCasesWithModelControls']}",
        f"- media missing physical candidates: {aggregate['mediaMissingPhysicalCandidateTotal']}",
        f"- OCR overlap risk: {aggregate['ocrOverlapRiskTotal']}",
        "",
        "## Class Counts",
        "",
        "```json",
        json.dumps(aggregate["classCounts"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Decision Counts",
        "",
        "```json",
        json.dumps(aggregate["decisionCounts"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Rows",
        "",
        "| case | det | controlDet | mediaDet | currentCtrl | controlTag | searchWin | mediaTag | mediaMissing | ocrRisk | raw | knockout | error |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "|{case}|{detectionCount}|{controlDetectionCount}|{mediaDetectionCount}|{currentControlSurfaceShapeLayerCount}|"
            "{controlSemanticTagCount}|{controlSearchWindowCandidateCount}|{mediaSemanticTagCount}|"
            "{mediaMissingPhysicalCandidateCount}|{ocrOverlapRiskCount}|{rawTextOverlapRaster}|"
            "{rasterTextKnockoutCount}|{error}|".format(
                case=row.get("case", ""),
                detectionCount=row.get("detectionCount", 0),
                controlDetectionCount=row.get("controlDetectionCount", 0),
                mediaDetectionCount=row.get("mediaDetectionCount", 0),
                currentControlSurfaceShapeLayerCount=row.get("currentControlSurfaceShapeLayerCount", 0),
                controlSemanticTagCount=row.get("controlSemanticTagCount", 0),
                controlSearchWindowCandidateCount=row.get("controlSearchWindowCandidateCount", 0),
                mediaSemanticTagCount=row.get("mediaSemanticTagCount", 0),
                mediaMissingPhysicalCandidateCount=row.get("mediaMissingPhysicalCandidateCount", 0),
                ocrOverlapRiskCount=row.get("ocrOverlapRiskCount", 0),
                rawTextOverlapRaster=row.get("rawTextOverlapRaster", 0),
                rasterTextKnockoutCount=row.get("rasterTextKnockoutCount", 0),
                error=str(row.get("error", "")).replace("|", "\\|"),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_contact_sheet(path: Path, rows: list[dict[str, Any]], current_output: Path, out_dir: Path) -> None:
    ok_rows = [row for row in rows if row.get("ok")]
    priority = sorted(
        ok_rows,
        key=lambda row: (
            int(row.get("mediaMissingPhysicalCandidateCount", 0))
            + int(row.get("controlSearchWindowCandidateCount", 0))
            + int(row.get("ocrOverlapRiskCount", 0)),
            int(row.get("detectionCount", 0)),
        ),
        reverse=True,
    )[:24]
    if not priority:
        return
    cell_w = 260
    cell_h = 420
    columns = 4
    sheet = Image.new("RGB", (cell_w * columns, cell_h * math.ceil(len(priority) / columns)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, row in enumerate(priority):
        case = row["case"]
        x = (index % columns) * cell_w
        y = (index // columns) * cell_h
        title = (
            f"{case} det={row.get('detectionCount', 0)} ctrl={row.get('controlDetectionCount', 0)} "
            f"miss={row.get('mediaMissingPhysicalCandidateCount', 0)} risk={row.get('ocrOverlapRiskCount', 0)}"
        )
        draw.text((x + 6, y + 5), title[:42], fill=(0, 0, 0))
        images = [
            ("draft", current_output / case / "draft_preview.png"),
            ("model", out_dir / case / "model_overlay.png"),
        ]
        for image_index, (label, image_path) in enumerate(images):
            ix = x + 8 + image_index * 124
            iy = y + 28
            draw.text((ix, iy), label, fill=(30, 30, 30))
            if not image_path.exists():
                draw.rectangle([ix, iy + 18, ix + 112, iy + 370], outline=(200, 0, 0))
                continue
            with Image.open(image_path) as image:
                thumb = image.convert("RGB")
                thumb.thumbnail((116, 360))
                sheet.paste(thumb, (ix, iy + 18))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


def bbox_iou(a: dict[str, Any], b: dict[str, Any]) -> float:
    inter = intersection_area(a, b)
    union = area(a) + area(b) - inter
    return 0.0 if union <= 0 else inter / union


def bbox_ioa(inner: dict[str, Any], outer: dict[str, Any]) -> float:
    inner_area = area(inner)
    if inner_area <= 0:
        return 0.0
    return intersection_area(inner, outer) / inner_area


def intersection_area(a: dict[str, Any], b: dict[str, Any]) -> float:
    ax1 = float(a.get("x", 0))
    ay1 = float(a.get("y", 0))
    ax2 = ax1 + float(a.get("width", 0))
    ay2 = ay1 + float(a.get("height", 0))
    bx1 = float(b.get("x", 0))
    by1 = float(b.get("y", 0))
    bx2 = bx1 + float(b.get("width", 0))
    by2 = by1 + float(b.get("height", 0))
    return max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))


def area(box: dict[str, Any]) -> float:
    return max(0.0, float(box.get("width", 0))) * max(0.0, float(box.get("height", 0)))


if __name__ == "__main__":
    main()
