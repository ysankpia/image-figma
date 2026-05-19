from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.reconstruction_ui_tree import extract_m31_reconstruction_ui_tree  # noqa: E402


def main() -> int:
    args = parse_args()
    if args.batch_root:
        return run_batch(args)
    result = run_single(args)
    print_single_result(result.report, result.output_dir)
    return 0


def run_batch(args: argparse.Namespace) -> int:
    batch_root = Path(args.batch_root).expanduser().resolve()
    if not batch_root.exists():
        raise FileNotFoundError(f"batch root not found: {batch_root}")
    task_dirs = sorted(path for path in batch_root.iterdir() if path.is_dir())
    if args.limit > 0:
        task_dirs = task_dirs[: args.limit]
    completed = 0
    failures: list[dict[str, str]] = []
    for task_dir in task_dirs:
        try:
            source_image = resolve_source_image(task_dir)
            ocr_json = task_dir / "ocr" / "ocr.json"
            m29_nodes_json = task_dir / "m29" / "nodes.json"
            if not ocr_json.exists() or not m29_nodes_json.exists():
                continue
            output_dir = resolve_output_dir((Path(args.out).expanduser().resolve() / task_dir.name) if args.out else task_dir / "m31", overwrite=args.overwrite)
            result = run_m31(
                source_image=source_image,
                ocr_json=ocr_json,
                m29_nodes_json=m29_nodes_json,
                output_dir=output_dir,
                profile=args.profile,
            )
            print_single_result(result.report, result.output_dir)
            completed += 1
        except Exception as exc:  # noqa: BLE001 - batch smoke records per-task failures.
            failures.append({"taskDir": task_dir.name, "stage": "m31", "error": str(exc)})
            print(f"FAILED {task_dir.name}: {exc}")
    summary = {
        "schemaName": "M31ReconstructionUiTreeBatchSummary",
        "schemaVersion": "0.1",
        "batchRoot": str(batch_root),
        "completedTasks": completed,
        "failedTasks": len(failures),
        "failures": failures,
    }
    (batch_root / "m31_reconstruction_tree_batch_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {batch_root / 'm31_reconstruction_tree_batch_summary.json'}")
    return 0 if not failures else 1


def run_single(args: argparse.Namespace) -> object:
    missing = [flag for flag, value in [("--source-image", args.source_image), ("--ocr-json", args.ocr_json), ("--m29-nodes-json", args.m29_nodes_json)] if not value]
    if missing:
        raise ValueError(f"single M31 run requires: {', '.join(missing)}")
    source_image = Path(args.source_image).expanduser().resolve()
    ocr_json = Path(args.ocr_json).expanduser().resolve()
    m29_nodes_json = Path(args.m29_nodes_json).expanduser().resolve()
    output_dir = resolve_output_dir(Path(args.out).expanduser().resolve(), overwrite=args.overwrite)
    return run_m31(
        source_image=source_image,
        ocr_json=ocr_json,
        m29_nodes_json=m29_nodes_json,
        output_dir=output_dir,
        profile=args.profile,
    )


def run_m31(*, source_image: Path, ocr_json: Path, m29_nodes_json: Path, output_dir: Path, profile: str) -> object:
    if not source_image.exists():
        raise FileNotFoundError(f"source image not found: {source_image}")
    if not ocr_json.exists():
        raise FileNotFoundError(f"OCR JSON not found: {ocr_json}")
    if not m29_nodes_json.exists():
        raise FileNotFoundError(f"M29 nodes JSON not found: {m29_nodes_json}")
    return extract_m31_reconstruction_ui_tree(
        source_image_path=str(source_image),
        ocr_document=load_json(ocr_json),
        ocr_json_path=str(ocr_json),
        m29_document=load_json(m29_nodes_json),
        m29_nodes_json_path=str(m29_nodes_json),
        output_dir=output_dir,
        profile=profile,
    )


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


def resolve_source_image(task_dir: Path) -> Path:
    m29_json = task_dir / "m29" / "nodes.json"
    if m29_json.exists():
        source = load_json(m29_json).get("sourceImage")
        if source:
            return Path(str(source).split("#", 1)[0]).expanduser().resolve()
    raise FileNotFoundError(f"cannot resolve source image for {task_dir}")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def print_single_result(report: dict[str, Any], output_dir: Path) -> None:
    summary = report["summary"]
    print(f"Wrote {output_dir / 'm31_reconstruction_tree.json'}")
    print(f"Wrote {output_dir / 'm31_reconstruction_tree_report.json'}")
    print(
        "M31 counts: "
        f"primitiveRefs={summary['primitiveRefCount']} "
        f"units={summary['unitCount']} "
        f"ownership={summary['primitiveOwnershipRate']}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run M31 reconstruction UI tree from source PNG, OCR JSON, and M29 nodes JSON.")
    parser.add_argument("--source-image", default="")
    parser.add_argument("--ocr-json", default="")
    parser.add_argument("--m29-nodes-json", default="")
    parser.add_argument("--out", default="storage/m31_reconstruction_ui_tree")
    parser.add_argument("--profile", choices=["development", "production"], default="development")
    parser.add_argument("--batch-root", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
