#!/usr/bin/env python3
"""Batch validate M29 -> Pencil production exports.

The batch runner accepts either:

- directories that already contain m29_physical_evidence.v1.json
- image files/directories with PNG/JPEG/WEBP images

For raw images it runs the Go M29 extractor first, then reuses
m29_pencil_export.py for production packaging. The output is a reproducible
test package with per-case .pen files, manifests, a summary table, and a contact
sheet for quick visual triage.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
BACKEND_GO_DIR = REPO_ROOT / "services" / "backend-go"
EXPORTER = SCRIPT_DIR / "m29_pencil_export.py"
EXPORT_MODE_NAMES = ("clean-editable", "visual-fidelity", "visual-ocr")


@dataclass(frozen=True)
class CaseInput:
    id: str
    kind: str
    path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch validate M29 Pencil production exports.")
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        type=Path,
        help="Image file, image directory, or M29 artifact directory. Repeatable.",
    )
    parser.add_argument(
        "--manifest",
        action="append",
        default=[],
        type=Path,
        help="PSD-like input_manifest.v1.json containing cases[].sourcePath. Repeatable.",
    )
    parser.add_argument("--out", required=True, type=Path, help="Output batch directory.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum cases to run. 0 means no limit.")
    parser.add_argument("--name-prefix", default="M29 Pencil", help="Prefix for generated Pencil page names.")
    parser.add_argument(
        "--mode",
        choices=(*EXPORT_MODE_NAMES, "all"),
        default="clean-editable",
        help="Export one mode or all three delivery modes.",
    )
    parser.add_argument("--ocr-provider", default="", help="Optional OCR provider passed to Go m29extract.")
    parser.add_argument("--include-debug-pen", action="store_true", help="Emit debug .pen for every case.")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip cases whose production manifest already exists.",
    )
    parser.add_argument(
        "--screenshot",
        action="store_true",
        help="Use Pencil CLI to export production screenshots when available.",
    )
    return parser.parse_args()


def stable_case_id(path: Path) -> str:
    stem = path.stem if path.is_file() else path.name
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stem).strip("_") or "case"
    digest = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:8]
    return f"{safe}_{digest}"


def safe_case_id(raw: str, fallback_path: Path) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in raw).strip("_")
    return safe or stable_case_id(fallback_path)


def discover_manifest_cases(manifests: list[Path]) -> list[CaseInput]:
    cases: list[CaseInput] = []
    for raw in manifests:
        manifest = raw.expanduser().resolve()
        data = json.loads(manifest.read_text(encoding="utf-8"))
        for index, item in enumerate(data.get("cases") or [], start=1):
            source = Path(item.get("sourcePath") or "").expanduser().resolve()
            if not source.exists():
                continue
            case_id = safe_case_id(str(item.get("caseId") or f"case_{index:04d}"), source)
            cases.append(CaseInput(case_id, "image", source))
    return cases


def discover_cases(inputs: list[Path], manifests: list[Path]) -> list[CaseInput]:
    cases: list[CaseInput] = []
    seen: set[Path] = set()
    for case in discover_manifest_cases(manifests):
        if case.path in seen:
            continue
        seen.add(case.path)
        cases.append(case)
    for raw in inputs:
        path = raw.expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        if path.is_dir() and (path / "m29_physical_evidence.v1.json").exists():
            if path not in seen:
                seen.add(path)
                cases.append(CaseInput(stable_case_id(path), "artifact", path))
            continue
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            if path not in seen:
                seen.add(path)
                cases.append(CaseInput(stable_case_id(path), "image", path))
            continue
        if path.is_dir():
            for image in sorted(
                item for item in path.rglob("*") if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS
            ):
                if image in seen:
                    continue
                seen.add(image)
                cases.append(CaseInput(stable_case_id(image), "image", image))
    return cases


def run_command(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=str(cwd) if cwd else None, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def ensure_png_source(image_path: Path, case_dir: Path) -> Path:
    if image_path.suffix.lower() == ".png":
        return image_path
    converted = case_dir / "source.png"
    with Image.open(image_path) as image:
        image.convert("RGBA").save(converted)
    return converted


def run_m29_extract(case: CaseInput, case_dir: Path, ocr_provider: str) -> tuple[Path | None, str | None]:
    if case.kind == "artifact":
        return case.path, None

    m29_dir = case_dir / "m29"
    if (m29_dir / "m29_physical_evidence.v1.json").exists():
        return m29_dir, None
    m29_dir.mkdir(parents=True, exist_ok=True)
    source = ensure_png_source(case.path, case_dir)
    cmd = ["go", "run", "./cmd/m29extract", "-input", str(source), "-out", str(m29_dir)]
    if ocr_provider:
        cmd.extend(["-ocr-provider", ocr_provider])
    result = run_command(cmd, cwd=BACKEND_GO_DIR)
    (case_dir / "m29extract.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (case_dir / "m29extract.stderr.txt").write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        return None, f"m29extract_failed: {result.stderr.strip() or result.stdout.strip()}"
    return m29_dir, None


def selected_modes(mode: str) -> list[str]:
    if mode == "all":
        return list(EXPORT_MODE_NAMES)
    return [mode]


def mode_dir_name(mode: str) -> str:
    return "production" if mode == "clean-editable" else mode


def run_export(
    case: CaseInput,
    artifact_dir: Path,
    case_dir: Path,
    name_prefix: str,
    include_debug_pen: bool,
    mode: str,
) -> str | None:
    export_dir = case_dir / "export"
    cmd = [
        sys.executable,
        str(EXPORTER),
        "--input-dir",
        str(artifact_dir),
        "--out",
        str(export_dir),
        "--name",
        f"{name_prefix} {case.id}",
        "--mode",
        mode,
    ]
    if include_debug_pen:
        cmd.append("--include-debug-pen")
    result = run_command(cmd, cwd=REPO_ROOT)
    (case_dir / "export.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (case_dir / "export.stderr.txt").write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        return f"export_failed: {result.stderr.strip() or result.stdout.strip()}"
    return None


def forbidden_refs(pen_path: Path) -> list[str]:
    if not pen_path.exists():
        return ["missing_design_pen"]
    serialized = pen_path.read_text(encoding="utf-8")
    forbidden = ["source.png", "raw-crops", "masks/", "./assets/crops/", "./assets/masks/"]
    return [item for item in forbidden if item in serialized]


def export_screenshot(case_dir: Path, mode: str) -> str | None:
    pencil = shutil.which("pencil")
    if not pencil:
        return "pencil_cli_missing"
    pen_path = case_dir / "export" / mode_dir_name(mode) / "design.pen"
    screenshot = case_dir / f"{mode}.png"
    result = run_command([pencil, "--in", str(pen_path), "--export", str(screenshot), "--export-scale", "1"])
    (case_dir / f"pencil_export.{mode}.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (case_dir / f"pencil_export.{mode}.stderr.txt").write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        return f"pencil_export_failed: {result.stderr.strip() or result.stdout.strip()}"
    return None


def load_manifest(case_dir: Path, mode: str = "clean-editable") -> dict[str, Any]:
    path = case_dir / "export" / mode_dir_name(mode) / "manifest.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def case_row(case: CaseInput, case_dir: Path, status: str, error: str | None, modes: list[str]) -> dict[str, Any]:
    primary_mode = "clean-editable" if "clean-editable" in modes else modes[0]
    manifest = load_manifest(case_dir, primary_mode)
    pen_path = case_dir / "export" / mode_dir_name(primary_mode) / "design.pen"
    refs = forbidden_refs(pen_path) if pen_path.exists() else []
    row: dict[str, Any] = {
        "id": case.id,
        "status": status,
        "kind": case.kind,
        "input": str(case.path),
        "error": error or "",
        "productionPen": str(pen_path) if pen_path.exists() else "",
        "screenshot": str(case_dir / f"{primary_mode}.png") if (case_dir / f"{primary_mode}.png").exists() else "",
        "textNodes": manifest.get("textNodes", 0),
        "cropNodes": manifest.get("cropNodes", 0),
        "textKnockoutCropNodes": manifest.get("textKnockoutCropNodes", 0),
        "artTextCropNodes": manifest.get("artTextCropNodes", 0),
        "cropTextNodes": manifest.get("cropTextNodes", 0),
        "suppressedDuplicateCropNodes": manifest.get("suppressedDuplicateCropNodes", 0),
        "suppressedInternalCropNodes": manifest.get("suppressedInternalCropNodes", 0),
        "assetCount": len(manifest.get("assets", [])) if manifest else 0,
        "forbiddenRefs": ",".join(refs),
        "cropPolicy": manifest.get("cropPolicy", ""),
        "screenshotError": error if status == "screenshot_warning" else "",
    }
    for mode in modes:
        mode_manifest = load_manifest(case_dir, mode)
        prefix = mode.replace("-", "_")
        row[f"{prefix}Pen"] = str(case_dir / "export" / mode_dir_name(mode) / "design.pen") if mode_manifest else ""
        row[f"{prefix}Screenshot"] = str(case_dir / f"{mode}.png") if (case_dir / f"{mode}.png").exists() else ""
        row[f"{prefix}TextNodes"] = mode_manifest.get("textNodes", 0)
        row[f"{prefix}CropNodes"] = mode_manifest.get("cropNodes", 0)
        row[f"{prefix}TextKnockoutCropNodes"] = mode_manifest.get("textKnockoutCropNodes", 0)
        row[f"{prefix}CropTextNodes"] = mode_manifest.get("cropTextNodes", 0)
        row[f"{prefix}SuppressedInternalCropNodes"] = mode_manifest.get("suppressedInternalCropNodes", 0)
    return row


def write_summary(out_dir: Path, rows: list[dict[str, Any]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps({"cases": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not rows:
        return
    with (out_dir / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_report(out_dir: Path, rows: list[dict[str, Any]]) -> None:
    passed = sum(1 for row in rows if row["status"] in {"passed", "screenshot_warning"})
    failed = sum(1 for row in rows if row["status"] == "failed")
    screenshot_warnings = sum(1 for row in rows if row["status"] == "screenshot_warning")
    total_text = sum(int(row.get("textNodes") or 0) for row in rows)
    total_crop = sum(int(row.get("cropNodes") or 0) for row in rows)
    total_suppressed = sum(int(row.get("suppressedInternalCropNodes") or 0) for row in rows)
    lines = [
        "# M29 Pencil Batch Validation",
        "",
        "## Summary",
        "",
        f"- cases: {len(rows)}",
        f"- production passed: {passed}",
        f"- failed: {failed}",
        f"- screenshot warnings: {screenshot_warnings}",
        f"- total text nodes: {total_text}",
        f"- total crop nodes: {total_crop}",
        f"- total internal crops suppressed: {total_suppressed}",
        "",
        "## Artifacts",
        "",
        "- `summary.json`: machine-readable case rows",
        "- `summary.csv`: spreadsheet-friendly case rows",
        "- `contact_sheet.png`: exported clean-editable screenshots when available",
        "- `contact_sheet.<mode>.png`: exported screenshots per delivery mode when available",
        "- `cases/*/export/production/design.pen`: clean-editable Pencil files",
        "- `cases/*/export/visual-fidelity/design.pen`: visual-fidelity Pencil files",
        "- `cases/*/export/visual-ocr/design.pen`: visual-ocr Pencil files",
        "",
        "## Cases",
        "",
        "| status | id | clean T/C/S | visual C | visual-ocr T/C | forbidden refs | screenshot |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for row in rows:
        screenshot = "yes" if row.get("screenshot") else "no"
        lines.append(
            "| {status} | `{id}` | {textNodes}/{cropNodes}/{suppressedInternalCropNodes} | {visual_fidelityCropNodes} | {visual_ocrTextNodes}/{visual_ocrCropNodes} | {forbiddenRefs} | {screenshot} |".format(
                **{
                    **row,
                    "visual_fidelityCropNodes": row.get("visual_fidelityCropNodes", "-"),
                    "visual_ocrTextNodes": row.get("visual_ocrTextNodes", "-"),
                    "visual_ocrCropNodes": row.get("visual_ocrCropNodes", "-"),
                    "forbiddenRefs": row.get("forbiddenRefs") or "-",
                    "screenshot": screenshot,
                }
            )
        )
    issue_rows = [row for row in rows if row.get("error") or row.get("screenshotError")]
    if issue_rows:
        lines.extend(["", "## Issues", ""])
        for row in issue_rows:
            message = row.get("error") or row.get("screenshotError") or ""
            lines.extend([f"### {row['id']}", "", "```text", str(message), "```", ""])
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def contact_sheet(out_dir: Path, rows: list[dict[str, Any]], mode: str = "clean-editable") -> None:
    if mode == "clean-editable":
        screenshot_key = "screenshot"
        out_name = "contact_sheet.png"
    else:
        screenshot_key = f"{mode.replace('-', '_')}Screenshot"
        out_name = f"contact_sheet.{mode}.png"
    screenshots = [
        (row, Path(str(row[screenshot_key])))
        for row in rows
        if row.get(screenshot_key) and Path(str(row[screenshot_key])).exists()
    ]
    if not screenshots:
        return
    thumb_w, thumb_h, label_h = 260, 180, 54
    cols = min(4, max(1, len(screenshots)))
    rows_count = (len(screenshots) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w, rows_count * (thumb_h + label_h)), "#f6f6f6")
    draw = ImageDraw.Draw(sheet)
    for index, (row, path) in enumerate(screenshots):
        x = (index % cols) * thumb_w
        y = (index // cols) * (thumb_h + label_h)
        draw.rectangle([x, y, x + thumb_w - 1, y + thumb_h + label_h - 1], outline="#d5d5d5")
        with Image.open(path) as image:
            thumb = image.convert("RGB")
            thumb.thumbnail((thumb_w - 14, thumb_h - 12), Image.Resampling.LANCZOS)
            sheet.paste(thumb, (x + (thumb_w - thumb.width) // 2, y + (thumb_h - thumb.height) // 2))
        prefix = mode.replace("-", "_")
        if mode == "clean-editable":
            text_nodes = row["textNodes"]
            crop_nodes = row["cropNodes"]
            suppressed = row["suppressedInternalCropNodes"]
        else:
            text_nodes = row.get(f"{prefix}TextNodes", 0)
            crop_nodes = row.get(f"{prefix}CropNodes", 0)
            suppressed = row.get(f"{prefix}SuppressedInternalCropNodes", 0)
        label = f"{row['id']}\n{mode} T{text_nodes} C{crop_nodes} S{suppressed}"
        draw.text((x + 6, y + thumb_h + 5), label, fill="#222222")
    sheet.save(out_dir / out_name)


def main() -> None:
    args = parse_args()
    out_dir = args.out.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if not args.input and not args.manifest:
        raise SystemExit("at least one --input or --manifest is required")
    cases = discover_cases(args.input, args.manifest)
    if args.limit > 0:
        cases = cases[: args.limit]
    modes = selected_modes(args.mode)

    rows: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        case_dir = out_dir / "cases" / f"{index:04d}_{case.id}"
        manifest = case_dir / "export" / mode_dir_name(modes[0]) / "manifest.json"
        if args.skip_existing and manifest.exists():
            rows.append(case_row(case, case_dir, "skipped_existing", None, modes))
            continue
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "input.txt").write_text(str(case.path) + "\n", encoding="utf-8")

        artifact_dir, error = run_m29_extract(case, case_dir, args.ocr_provider)
        if error or artifact_dir is None:
            rows.append(case_row(case, case_dir, "failed", error, modes))
            continue
        error = run_export(case, artifact_dir, case_dir, args.name_prefix, args.include_debug_pen, args.mode)
        if error:
            rows.append(case_row(case, case_dir, "failed", error, modes))
            continue
        if args.screenshot:
            screenshot_errors = []
            for mode in modes:
                screenshot_error = export_screenshot(case_dir, mode)
                if screenshot_error:
                    screenshot_errors.append(f"{mode}: {screenshot_error}")
            if screenshot_errors:
                rows.append(case_row(case, case_dir, "screenshot_warning", "; ".join(screenshot_errors), modes))
                write_summary(out_dir, rows)
                write_report(out_dir, rows)
                continue
        rows.append(case_row(case, case_dir, "passed", None, modes))
        write_summary(out_dir, rows)
        write_report(out_dir, rows)

    write_summary(out_dir, rows)
    for mode in modes:
        contact_sheet(out_dir, rows, mode)
    write_report(out_dir, rows)
    print(
        json.dumps(
            {
                "outDir": str(out_dir),
                "caseCount": len(rows),
                "passed": sum(1 for row in rows if row["status"] in {"passed", "screenshot_warning"}),
                "failed": sum(1 for row in rows if row["status"] == "failed"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
