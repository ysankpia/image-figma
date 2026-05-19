from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.residual_mixed_boundary_review import (  # noqa: E402
    M29032Options,
    build_batch_summary,
    extract_residual_mixed_boundary_review,
)


DEFAULT_INPUT_DIRS = [
    Path("/Users/luhui/Downloads/测试/images"),
    Path("/Users/luhui/Downloads/测试/images 2"),
]


def main() -> int:
    args = parse_args()
    if args.full_batch:
        return run_full_batch(args)
    if args.batch_root:
        return run_existing_batch(args)
    document, output_dir = run_single(args, Path(args.m29_output).expanduser().resolve(), explicit_input=args.input, image_id=args.image_id or "image_001")
    print_single_result(document, output_dir)
    return 0


def run_full_batch(args: argparse.Namespace) -> int:
    input_dirs = args.input_dirs if args.input_dirs is not None else [str(path) for path in DEFAULT_INPUT_DIRS]
    sources = collect_batch_sources([Path(value).expanduser().resolve() for value in input_dirs], max_images=args.max_images)
    batch_root = resolve_new_batch_root(args)
    batch_root.mkdir(parents=True, exist_ok=True)
    documents = []
    failures: list[dict] = []
    m2905_by_image: dict[str, dict] = {}
    m2906_by_image: dict[str, dict] = {}
    for index, source in enumerate(sources, start=1):
        image_id = f"image_{index:03d}"
        image_dir = batch_root / image_id
        image_dir.mkdir(parents=True, exist_ok=True)
        print(f"== {image_id} == {source}")
        try:
            run_full_chain_for_image(args, source, image_dir)
            document, output_dir = run_single(args, image_dir, explicit_input=str(source), image_id=image_id)
            print_single_result(document, output_dir)
            documents.append((image_id, document))
            if m2905_json := resolve_optional_json("", image_dir, "m29_0_5", "refined_visual_objects.json", required=False):
                m2905_by_image[image_id] = load_json(m2905_json) or {}
            if m2906_json := resolve_optional_json("", image_dir, "m29_0_6", "member_boundary_quality_audit.json", required=False):
                m2906_by_image[image_id] = load_json(m2906_json) or {}
        except Exception as exc:  # noqa: BLE001 - batch runner records per-image failures.
            failure = {
                "imageId": image_id,
                "sourceImage": str(source),
                "failedStage": getattr(exc, "stage", "unknown"),
                "error": str(exc),
            }
            print(f"FAILED {image_id}: {failure['failedStage']} {failure['error']}")
            failures.append(failure)
    payload = build_batch_summary(documents, batch_root, failures=failures, m2905_by_image=m2905_by_image, m2906_by_image=m2906_by_image)
    print(f"Wrote {batch_root / 'm29_0_3_2_batch_summary.json'}")
    print(f"Wrote {batch_root / 'm29_0_3_2_batch_summary.csv'}")
    print(f"M29.0.3.2 batch totals: {payload['totals']}")
    return 0 if not failures else 1


def run_existing_batch(args: argparse.Namespace) -> int:
    batch_root = Path(args.batch_root).expanduser().resolve()
    if not batch_root.exists():
        raise FileNotFoundError(f"batch root not found: {batch_root}")
    input_root = Path(args.input_root).expanduser().resolve() if args.input_root else None
    documents = []
    failures: list[dict] = []
    m2905_by_image: dict[str, dict] = {}
    m2906_by_image: dict[str, dict] = {}
    for image_dir in sorted(path for path in batch_root.glob("image_*") if path.is_dir()):
        image_id = image_dir.name
        try:
            source = resolve_batch_source(image_dir, input_root)
            print(f"== {image_id} == {source}")
            document, output_dir = run_single(args, image_dir, explicit_input=str(source), image_id=image_id)
            print_single_result(document, output_dir)
            documents.append((image_id, document))
            if m2905_json := resolve_optional_json(args.m2905_output, image_dir, "m29_0_5", "refined_visual_objects.json", required=False):
                m2905_by_image[image_id] = load_json(m2905_json) or {}
            if m2906_json := resolve_optional_json(args.m2906_output, image_dir, "m29_0_6", "member_boundary_quality_audit.json", required=False):
                m2906_by_image[image_id] = load_json(m2906_json) or {}
        except Exception as exc:  # noqa: BLE001 - batch runner records per-image failures.
            failures.append({"imageId": image_id, "sourceImage": "", "failedStage": getattr(exc, "stage", "unknown"), "error": str(exc)})
    build_batch_summary(documents, batch_root, failures=failures, m2905_by_image=m2905_by_image, m2906_by_image=m2906_by_image)
    print(f"Wrote {batch_root / 'm29_0_3_2_batch_summary.json'}")
    print(f"Wrote {batch_root / 'm29_0_3_2_batch_summary.csv'}")
    return 0 if not failures else 1


def run_single(args: argparse.Namespace, m29_output: Path, *, explicit_input: str, image_id: str) -> tuple[object, Path]:
    if not explicit_input:
        raise ValueError("--input is required unless --batch-root or --full-batch is used")
    source = Path(explicit_input).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"source image not found: {source}")
    m2903_json = resolve_optional_json(args.m2903_output, m29_output, "m29_0_3", "visual_evidence.json", required=True)
    m2913_json = resolve_optional_json(args.m2913_output, m29_output, "m29_1_3", "mixed_symbol_text_conflict_audit.json", required=False)
    m2907_json = resolve_optional_json(args.m2907_output, m29_output, "m29_0_7", "text_visual_ownership_gate.json", required=False)
    m2902_json = resolve_optional_json(args.m2902_output, m29_output, "m29_0_2", "text_masked_media_audit.json", required=False)
    m291_json = resolve_optional_json(args.m291_output, m29_output, "m29_1", "group_nodes.json", required=False)
    m2911_json = resolve_optional_json(args.m2911_output, m29_output, "m29_1_1", "pre_ocr_symbol_lineage_audit.json", required=False)
    output_dir = resolve_output_dir(m29_output / "m29_0_3_2", overwrite=args.overwrite)
    document = extract_residual_mixed_boundary_review(
        png_data=source.read_bytes(),
        source_image=str(source),
        source_image_id=image_id,
        m2903_document=load_json(m2903_json) or {},
        m2903_visual_evidence_json_path=str(m2903_json),
        output_dir=output_dir,
        m2913_document=load_json(m2913_json),
        m2913_conflict_audit_json_path=str(m2913_json) if m2913_json else None,
        m2907_document=load_json(m2907_json),
        m2907_ownership_json_path=str(m2907_json) if m2907_json else None,
        m2902_document=load_json(m2902_json),
        m2902_audit_json_path=str(m2902_json) if m2902_json else None,
        m291_document=load_json(m291_json),
        m291_group_nodes_json_path=str(m291_json) if m291_json else None,
        m2911_document=load_json(m2911_json),
        m2911_lineage_audit_json_path=str(m2911_json) if m2911_json else None,
        options=M29032Options(
            full_ocr_coverage_min=args.full_ocr_coverage_min,
            partial_ocr_overlap_min=args.partial_ocr_overlap_min,
            text_like_aspect_min=args.text_like_aspect_min,
            compact_max_edge=args.compact_max_edge,
            compact_max_area=args.compact_max_area,
            repeated_alignment_tolerance=args.repeated_alignment_tolerance,
            label_adjacency_max_gap=args.label_adjacency_max_gap,
            duplicate_iou_min=args.duplicate_iou_min,
            max_examples_per_conclusion=args.max_examples_per_conclusion,
        ),
    )
    return document, output_dir


def run_full_chain_for_image(args: argparse.Namespace, source: Path, image_dir: Path) -> None:
    stage_commands = [
        ("m29", [sys.executable, "scripts/run_m29_visual_primitive_graph.py", "--input", str(source), "--output-dir", str(image_dir), "--overwrite"]),
        ("m29_1", [sys.executable, "scripts/run_m29_1_symbol_grouping.py", "--input", str(source), "--m29-output", str(image_dir), "--overwrite"]),
        ("m29_1_1", [sys.executable, "scripts/run_m29_1_1_pre_ocr_symbol_lineage_audit.py", "--input", str(source), "--m29-output", str(image_dir), "--overwrite"]),
        ("m29_0_2", [sys.executable, "scripts/run_m29_0_2_text_masked_media_audit.py", "--input", str(source), "--m29-output", str(image_dir), "--overwrite"]),
        ("m29_0_3", [sys.executable, "scripts/run_m29_0_3_visual_evidence_normalization.py", "--input", str(source), "--m29-output", str(image_dir), "--m291-lineage-json", str(image_dir / "m29_1" / "group_nodes.json"), "--overwrite"]),
        ("m29_0_7", [sys.executable, "scripts/run_m29_0_7_text_visual_ownership_gate.py", "--input", str(source), "--m29-output", str(image_dir), "--overwrite"]),
        ("m29_0_4", [sys.executable, "scripts/run_m29_0_4_visual_object_candidate_audit.py", "--input", str(source), "--m29-output", str(image_dir), "--m2907-ownership-json", str(image_dir / "m29_0_7" / "text_visual_ownership_gate.json"), "--overwrite"]),
        ("m29_0_5", [sys.executable, "scripts/run_m29_0_5_text_aware_visual_object_refinement.py", "--input", str(source), "--m29-output", str(image_dir), "--overwrite"]),
        ("m29_0_6", [sys.executable, "scripts/run_m29_0_6_member_boundary_quality_audit.py", "--input", str(source), "--m29-output", str(image_dir), "--overwrite"]),
        ("m29_1_3", [sys.executable, "scripts/run_m29_1_3_mixed_symbol_text_conflict_audit.py", "--input", str(source), "--m29-output", str(image_dir), "--overwrite"]),
    ]
    if args.ocr_provider:
        stage_commands[3][1].extend(["--ocr-provider", args.ocr_provider])
    for stage, command in stage_commands:
        try:
            subprocess.run(command, cwd=BACKEND_ROOT, check=True)
        except subprocess.CalledProcessError as exc:
            raise StageFailure(stage, f"command exited with {exc.returncode}") from exc


class StageFailure(RuntimeError):
    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run M29.0.3.2 residual mixed boundary review.")
    parser.add_argument("--input", default="")
    parser.add_argument("--m29-output", default="storage/m29_visual_primitive_graph")
    parser.add_argument("--image-id", default="")
    parser.add_argument("--batch-root", default="")
    parser.add_argument("--full-batch", action="store_true")
    parser.add_argument("--input-root", default="")
    parser.add_argument("--input-dir", dest="input_dirs", action="append", default=None)
    parser.add_argument("--output-root", default="")
    parser.add_argument("--max-images", type=int, default=0)
    parser.add_argument("--ocr-provider", choices=["", "baidu_ppocrv5"], default="baidu_ppocrv5")
    parser.add_argument("--m2903-output", default="")
    parser.add_argument("--m2913-output", default="")
    parser.add_argument("--m2907-output", default="")
    parser.add_argument("--m2902-output", default="")
    parser.add_argument("--m291-output", default="")
    parser.add_argument("--m2911-output", default="")
    parser.add_argument("--m2905-output", default="")
    parser.add_argument("--m2906-output", default="")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--full-ocr-coverage-min", type=float, default=M29032Options.full_ocr_coverage_min)
    parser.add_argument("--partial-ocr-overlap-min", type=float, default=M29032Options.partial_ocr_overlap_min)
    parser.add_argument("--text-like-aspect-min", type=float, default=M29032Options.text_like_aspect_min)
    parser.add_argument("--compact-max-edge", type=int, default=M29032Options.compact_max_edge)
    parser.add_argument("--compact-max-area", type=int, default=M29032Options.compact_max_area)
    parser.add_argument("--repeated-alignment-tolerance", type=int, default=M29032Options.repeated_alignment_tolerance)
    parser.add_argument("--label-adjacency-max-gap", type=int, default=M29032Options.label_adjacency_max_gap)
    parser.add_argument("--duplicate-iou-min", type=float, default=M29032Options.duplicate_iou_min)
    parser.add_argument("--max-examples-per-conclusion", type=int, default=M29032Options.max_examples_per_conclusion)
    return parser.parse_args()


def collect_batch_sources(input_dirs: list[Path], *, max_images: int) -> list[Path]:
    sources: list[Path] = []
    for input_dir in input_dirs:
        if not input_dir.exists():
            raise FileNotFoundError(f"input dir not found: {input_dir}")
        sources.extend(path for path in sorted(input_dir.iterdir()) if path.suffix.lower() == ".png" and path.is_file())
    sources = sorted(sources, key=lambda path: str(path))
    return sources[:max_images] if max_images > 0 else sources


def resolve_new_batch_root(args: argparse.Namespace) -> Path:
    if args.output_root:
        root = Path(args.output_root).expanduser().resolve()
        if root.exists() and not args.overwrite:
            suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
            return root.with_name(f"{root.name}_{suffix}")
        if root.exists() and args.overwrite:
            shutil.rmtree(root)
        return root
    suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    return BACKEND_ROOT / "storage" / f"m29_0_3_2_residual_mixed_boundary_review_batch_{suffix}"


def resolve_optional_json(arg_value: str, m29_output: Path, prefix: str, filename: str, *, required: bool) -> Path | None:
    if arg_value:
        path = Path(arg_value).expanduser().resolve()
        candidate = path / filename if path.is_dir() else path
        if not candidate.exists():
            raise FileNotFoundError(f"required M29 input not found: {candidate}")
        return candidate
    candidates = [path for path in m29_output.glob(f"{prefix}*") if path.is_dir() and (path / filename).exists()]
    if not candidates:
        if required:
            raise FileNotFoundError(f"No {prefix} output found under {m29_output}")
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime) / filename


def load_json(path: Path | None) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path is not None else None


def resolve_output_dir(path: Path, *, overwrite: bool) -> Path:
    resolved = path.expanduser().resolve()
    if overwrite:
        if resolved.exists():
            shutil.rmtree(resolved)
        return resolved
    if not resolved.exists():
        return resolved
    suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    return resolved.with_name(f"{resolved.name}_{suffix}")


def resolve_batch_source(image_dir: Path, input_root: Path | None) -> Path:
    for relative in [
        Path("m29_0_3_2") / "residual_mixed_boundary_review.json",
        Path("m29_1_3") / "mixed_symbol_text_conflict_audit.json",
        Path("m29_0_3") / "visual_evidence.json",
        Path("nodes.json"),
    ]:
        source_json = image_dir / relative
        if not source_json.exists():
            continue
        value = (load_json(source_json) or {}).get("sourceImage")
        if not value:
            continue
        path = Path(str(value).split("#", 1)[0]).expanduser()
        if path.exists():
            return path.resolve()
        if input_root is not None:
            candidate = input_root / path.name
            if candidate.exists():
                return candidate.resolve()
    raise FileNotFoundError(f"cannot resolve source image for {image_dir}")


def print_single_result(document: object, output_dir: Path) -> None:
    print(f"Resolved M29.0.3 visual evidence: {document.source_m2903_visual_evidence_json}")
    print(f"Wrote {output_dir / 'residual_mixed_boundary_review.json'}")
    print(f"Wrote {output_dir / 'review_sheet_remaining_mixed.png'}")
    print(f"M29.0.3.2 reviews: {document.summary.get('byReviewConclusion', {})}")


if __name__ == "__main__":
    raise SystemExit(main())
