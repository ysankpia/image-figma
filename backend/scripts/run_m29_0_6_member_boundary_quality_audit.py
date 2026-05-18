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

from app.member_boundary_quality_audit import (  # noqa: E402
    M2906Options,
    M2906SourceExpansionRefs,
    extract_member_boundary_quality_audit,
    write_batch_summary,
)


def main() -> int:
    args = parse_args()
    if args.batch_root:
        return run_batch(args)
    document, output_dir = run_single(args, Path(args.m29_output).expanduser().resolve(), explicit_input=args.input or "")
    print_single_result(document, output_dir)
    return 0


def run_batch(args: argparse.Namespace) -> int:
    batch_root = Path(args.batch_root).expanduser().resolve()
    input_root = Path(args.input_root).expanduser().resolve() if args.input_root else None
    documents = []
    for image_dir in sorted(path for path in batch_root.glob("image_*") if path.is_dir()):
        source = resolve_batch_source(image_dir, input_root)
        print(f"== {image_dir.name} == {source}")
        document, output_dir = run_single(args, image_dir, explicit_input=str(source))
        print_single_result(document, output_dir)
        documents.append((image_dir.name, document))
    write_batch_summary(documents, batch_root)
    print(f"Wrote {batch_root / 'm29_0_6_batch_summary.json'}")
    print(f"Wrote {batch_root / 'm29_0_6_batch_summary.csv'}")
    return 0


def run_single(args: argparse.Namespace, m29_output: Path, *, explicit_input: str) -> tuple[object, Path]:
    source = Path(explicit_input or args.input).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"source image not found: {source}")
    m2905_output = Path(args.m2905_output).expanduser().resolve() if args.m2905_output else resolve_latest_output(m29_output, "m29_0_5", "refined_visual_objects.json")
    m2904_output = Path(args.m2904_output).expanduser().resolve() if args.m2904_output else resolve_latest_output(m29_output, "m29_0_4", "visual_object_candidates.json")
    m2903_output = Path(args.m2903_output).expanduser().resolve() if args.m2903_output else resolve_latest_output(m29_output, "m29_0_3", "visual_evidence.json")
    m2902_output = Path(args.m2902_output).expanduser().resolve() if args.m2902_output else resolve_latest_output(m29_output, "m29_0_2", "text_masked_media_audit.json")
    m2905_json = m2905_output / "refined_visual_objects.json"
    m2904_json = m2904_output / "visual_object_candidates.json"
    m2903_json = m2903_output / "visual_evidence.json"
    m2902_json = m2902_output / "text_masked_media_audit.json"
    for path in [m2905_json, m2904_json, m2903_json, m2902_json]:
        if not path.exists():
            raise FileNotFoundError(f"required M29 input not found: {path}")
    output_dir = resolve_output_dir(m29_output / "m29_0_6", overwrite=args.overwrite)
    document = extract_member_boundary_quality_audit(
        png_data=source.read_bytes(),
        source_image=str(source),
        m2905_document=json.loads(m2905_json.read_text(encoding="utf-8")),
        m2905_refined_visual_objects_json_path=str(m2905_json),
        m2904_document=json.loads(m2904_json.read_text(encoding="utf-8")),
        m2904_visual_object_candidates_json_path=str(m2904_json),
        m2903_document=json.loads(m2903_json.read_text(encoding="utf-8")),
        m2903_visual_evidence_json_path=str(m2903_json),
        m2902_document=json.loads(m2902_json.read_text(encoding="utf-8")),
        m2902_audit_json_path=str(m2902_json),
        output_dir=output_dir,
        m2905_output_dir=m2905_output,
        source_expansion_refs=M2906SourceExpansionRefs(
            m291_group_nodes_json=str(Path(args.m291_group_nodes_json).expanduser().resolve()) if args.m291_group_nodes_json else None,
        ),
        options=M2906Options(
            max_examples_per_finding_kind=args.max_examples_per_finding_kind,
            max_duplicate_groups=args.max_duplicate_groups,
            max_examples_per_duplicate_group=args.max_examples_per_duplicate_group,
            perceptual_duplicate_hamming_max=args.perceptual_duplicate_hamming_max,
            output_preview_max_thumb=args.output_preview_max_thumb,
        ),
    )
    return document, output_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run M29.0.6 member boundary quality audit.")
    parser.add_argument("--input", default="")
    parser.add_argument("--m29-output", default="storage/m29_visual_primitive_graph")
    parser.add_argument("--batch-root", default="")
    parser.add_argument("--input-root", default="")
    parser.add_argument("--m2905-output", default="")
    parser.add_argument("--m2904-output", default="")
    parser.add_argument("--m2903-output", default="")
    parser.add_argument("--m2902-output", default="")
    parser.add_argument("--m291-group-nodes-json", default="")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--max-examples-per-finding-kind", type=int, default=M2906Options.max_examples_per_finding_kind)
    parser.add_argument("--max-duplicate-groups", type=int, default=M2906Options.max_duplicate_groups)
    parser.add_argument("--max-examples-per-duplicate-group", type=int, default=M2906Options.max_examples_per_duplicate_group)
    parser.add_argument("--perceptual-duplicate-hamming-max", type=int, default=M2906Options.perceptual_duplicate_hamming_max)
    parser.add_argument("--output-preview-max-thumb", type=int, default=M2906Options.output_preview_max_thumb)
    return parser.parse_args()


def resolve_latest_output(m29_output: Path, prefix: str, filename: str) -> Path:
    candidates = [path for path in m29_output.glob(f"{prefix}*") if path.is_dir() and (path / filename).exists()]
    if not candidates:
        raise FileNotFoundError(f"No {prefix} output found under {m29_output}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


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
    source_from_json = image_dir / "m29_0_5" / "refined_visual_objects.json"
    if source_from_json.exists():
        value = json.loads(source_from_json.read_text(encoding="utf-8")).get("sourceImage")
        if value and Path(value).exists():
            return Path(value).expanduser().resolve()
        if value and input_root is not None:
            candidate = input_root / Path(value).name
            if candidate.exists():
                return candidate.resolve()
    if input_root is not None:
        index = int(image_dir.name.split("_")[-1])
        matches = sorted(input_root.glob(f"*({index}).png"))
        if matches:
            return matches[0].resolve()
    raise FileNotFoundError(f"cannot resolve source image for {image_dir}")


def print_single_result(document: object, output_dir: Path) -> None:
    summary = document.summary
    print(f"Wrote {output_dir / 'member_boundary_quality_audit.json'}")
    print(f"Wrote {output_dir / 'preview_member_boundary_quality.png'}")
    print(
        "M29.0.6 counts: "
        f"findings={len(document.findings)} duplicateSources={len(document.duplicate_source_findings)} "
        f"duplicateAssets={len(document.duplicate_asset_findings)} "
        f"weakTextNoiseRatio={summary.get('weakTextNoiseUnresolvedRatio', 0)}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
