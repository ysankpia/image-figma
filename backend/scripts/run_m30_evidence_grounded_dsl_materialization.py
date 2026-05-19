from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.evidence_grounded_dsl_materialization import (  # noqa: E402
    M30Options,
    materialize_evidence_grounded_dsl,
)


def main() -> int:
    args = parse_args()
    if args.batch_root:
        return run_batch(args)
    result = run_single(args, Path(args.m29_output).expanduser().resolve(), source_image=args.source_image)
    print_single_result(result.report, result.output_dir)
    return 0


def run_batch(args: argparse.Namespace) -> int:
    batch_root = Path(args.batch_root).expanduser().resolve()
    if not batch_root.exists():
        raise FileNotFoundError(f"batch root not found: {batch_root}")
    image_dirs = sorted(path for path in batch_root.glob("image_*") if path.is_dir())
    if args.limit > 0:
        image_dirs = image_dirs[: args.limit]
    failures: list[dict[str, str]] = []
    completed = 0
    for image_dir in image_dirs:
        try:
            source_image = args.source_image or resolve_source_image(image_dir)
            print(f"== {image_dir.name} == {source_image}")
            result = run_single(args, image_dir, source_image=source_image)
            print_single_result(result.report, result.output_dir)
            completed += 1
        except Exception as exc:  # noqa: BLE001 - smoke batch records per-image failures.
            failure = {"imageId": image_dir.name, "failedStage": "m30", "error": str(exc)}
            failures.append(failure)
            print(f"FAILED {image_dir.name}: {failure['error']}")
    summary = {
        "schemaName": "M30EvidenceGroundedDslMaterializationBatchSummary",
        "schemaVersion": "0.1",
        "batchRoot": str(batch_root),
        "totalImages": len(image_dirs),
        "completedImages": completed,
        "failedImages": len(failures),
        "failures": failures,
    }
    (batch_root / "m30_materialization_batch_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {batch_root / 'm30_materialization_batch_summary.json'}")
    return 0 if not failures else 1


def run_single(args: argparse.Namespace, m29_output: Path, *, source_image: str) -> object:
    if not source_image:
        source_image = resolve_source_image(m29_output)
    source_path = Path(source_image).expanduser().resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"source image not found: {source_path}")
    m2905_json = resolve_m2905_json(args.m2905_output, m29_output)
    base_dsl_path = Path(args.base_dsl).expanduser().resolve() if args.base_dsl else None
    mode = resolve_mode(args.mode, base_dsl_path)
    output_dir = resolve_output_dir(Path(args.out).expanduser().resolve() if args.out else m29_output / "m30", overwrite=args.overwrite)
    result = materialize_evidence_grounded_dsl(
        source_image_path=str(source_path),
        m2905_document=load_json(m2905_json),
        m2905_json_path=str(m2905_json),
        output_dir=output_dir,
        mode=mode,
        base_dsl=load_json(base_dsl_path) if base_dsl_path else None,
        base_dsl_path=str(base_dsl_path) if base_dsl_path else None,
        options=M30Options(
            safe_visual_text_overlap_max=args.safe_visual_text_overlap_max,
            safe_shape_text_overlap_max=args.safe_shape_text_overlap_max,
        ),
    )
    return result


def resolve_mode(mode_arg: str, base_dsl_path: Path | None) -> str:
    if mode_arg:
        if mode_arg == "augment-existing-dsl" and base_dsl_path is None:
            raise ValueError("--mode augment-existing-dsl requires --base-dsl")
        if mode_arg == "bootstrap-dsl-from-m29" and base_dsl_path is not None:
            raise ValueError("--mode bootstrap-dsl-from-m29 cannot be combined with --base-dsl")
        return mode_arg
    return "augment-existing-dsl" if base_dsl_path else "bootstrap-dsl-from-m29"


def resolve_m2905_json(arg_value: str, m29_output: Path) -> Path:
    if arg_value:
        path = Path(arg_value).expanduser().resolve()
        candidate = path / "refined_visual_objects.json" if path.is_dir() else path
        if not candidate.exists():
            raise FileNotFoundError(f"M29.0.5 refined visual objects JSON not found: {candidate}")
        return candidate
    candidates = [path for path in m29_output.glob("m29_0_5*") if path.is_dir() and (path / "refined_visual_objects.json").exists()]
    if not candidates:
        raise FileNotFoundError(f"No M29.0.5 output found under {m29_output}")
    return max(candidates, key=lambda path: path.stat().st_mtime) / "refined_visual_objects.json"


def resolve_source_image(image_dir: Path) -> str:
    for relative in [
        Path("m30") / "m30_materialization_report.json",
        Path("m29_0_5") / "refined_visual_objects.json",
        Path("m29_0_3") / "visual_evidence.json",
        Path("nodes.json"),
    ]:
        source_json = image_dir / relative
        if not source_json.exists():
            continue
        value = load_json(source_json).get("sourceImage")
        if value:
            return str(value).split("#", 1)[0]
    raise FileNotFoundError(f"cannot resolve source image for {image_dir}")


def load_json(path: Path | None) -> dict:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def print_single_result(report: object, output_dir: Path) -> None:
    print(f"Mode: {report.mode}")
    print(f"Source M29.0.5: {report.source_m2905_refined_visual_objects_json}")
    print(f"Wrote {output_dir / 'm30_materialized_dsl.json'}")
    print(f"Wrote {output_dir / 'm30_materialization_report.json'}")
    print(f"Wrote {output_dir / 'm30_materialization_preview.png'}")
    print(
        "M30 materialized counts: "
        f"text={report.summary.get('materializedTextCount', 0)} "
        f"shape={report.summary.get('materializedShapeCount', 0)} "
        f"image={report.summary.get('materializedImageCount', 0)}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run M30 evidence-grounded DSL materialization.")
    parser.add_argument("--m29-output", default="storage/m29_visual_primitive_graph")
    parser.add_argument("--m2905-output", default="")
    parser.add_argument("--source-image", default="")
    parser.add_argument("--base-dsl", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--mode", choices=["augment-existing-dsl", "bootstrap-dsl-from-m29"], default="")
    parser.add_argument("--batch-root", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--safe-visual-text-overlap-max", type=float, default=M30Options.safe_visual_text_overlap_max)
    parser.add_argument("--safe-shape-text-overlap-max", type=float, default=M30Options.safe_shape_text_overlap_max)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
